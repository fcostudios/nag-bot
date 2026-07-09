"""The lite backend: FastAPI app factory, Basic-auth middleware, healthz, dashboards."""

from __future__ import annotations

import base64
import binascii
import logging
import secrets
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from nagbot import __version__
from nagbot.digest.builder import build_rollup
from nagbot.run import (
    _RUN_LOCK,
    build_all_digests,
    execute_nag_run,
    execute_rollup_run,
    fetch_and_score,
)
from nagbot.runtime import Runtime, build_runtime
from nagbot.scheduler import build_scheduler


def run_lock_busy() -> bool:
    return _RUN_LOCK.locked()

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent
AUTH_EXEMPT_PREFIXES = ("/healthz", "/static")


def make_jobs(rt: Runtime) -> tuple:
    def nag_job() -> None:
        execute_nag_run(
            rt.cfg, rt.store, rt.adapters, rt.glpi_factory, dry_run=rt.cfg.dry_run, trigger="cron"
        )

    def rollup_job() -> None:
        execute_rollup_run(rt.cfg, rt.store, rt.adapters, dry_run=rt.cfg.dry_run)

    return nag_job, rollup_job


def _check_basic_auth(header: str | None, password: str) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return False
    _, _, candidate = decoded.partition(":")
    return secrets.compare_digest(candidate.encode(), password.encode())


def make_templates(rt: Runtime) -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    # share the digest renderer's filters/globals so badges and dates match emails
    templates.env.filters.update(rt.renderer.env.filters)
    templates.env.globals.update(rt.renderer.env.globals)
    templates.env.globals["dry_run"] = rt.cfg.dry_run
    templates.env.globals["version"] = __version__
    return templates


def create_app(rt: Runtime | None = None, *, with_scheduler: bool = True) -> FastAPI:
    rt = rt or build_runtime()
    scheduler: BackgroundScheduler | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        nonlocal scheduler
        if with_scheduler:
            nag_job, rollup_job = make_jobs(rt)
            scheduler = build_scheduler(rt.cfg, nag_job, rollup_job)
            scheduler.start()
            logger.info(
                "scheduler running (digest: %s, dry_run: %s)",
                rt.cfg.app.schedule.digest_cron,
                rt.cfg.dry_run,
            )
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        rt.store.close()

    app = FastAPI(title="GLPI Nagbot", version=__version__, lifespan=lifespan)
    app.state.runtime = rt
    app.state.templates = make_templates(rt)
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    password = (
        rt.cfg.env.dashboard_password.get_secret_value()
        if rt.cfg.env.dashboard_password
        else None
    )

    @app.middleware("http")
    async def basic_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path.startswith(AUTH_EXEMPT_PREFIXES):
            return await call_next(request)
        if not password:
            return JSONResponse(
                {"error": "dashboard disabled: set DASHBOARD_PASSWORD"}, status_code=503
            )
        if not _check_basic_auth(request.headers.get("Authorization"), password):
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="nagbot"'},
            )
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        try:
            last = rt.store.last_run()
            db_ok = True
        except Exception:  # noqa: BLE001
            last, db_ok = None, False
        healthy = db_ok
        return JSONResponse(
            {
                "status": "ok" if healthy else "degraded",
                "version": __version__,
                "db": db_ok,
                "dry_run": rt.cfg.dry_run,
                "scheduler_running": bool(scheduler and scheduler.running),
                "last_run": {
                    "id": last.id,
                    "status": last.status,
                    "dry_run": last.dry_run,
                    "started_at": last.started_at.isoformat(),
                }
                if last
                else None,
            },
            status_code=200 if healthy else 503,
        )

    register_routes(app)
    return app


def register_routes(app: FastAPI) -> None:
    rt: Runtime = app.state.runtime
    templates: Jinja2Templates = app.state.templates

    @app.get("/")
    def wip_dashboard(request: Request) -> Response:
        run, snaps = rt.store.latest_snapshot()
        if run is None:
            return templates.TemplateResponse(
                request, "wip.html.j2", {"run": None, "rollup": None, "snoozes": {}}
            )
        rollup = build_rollup(snaps, now=run.started_at)
        return templates.TemplateResponse(
            request,
            "wip.html.j2",
            {
                "run": run,
                "rollup": rollup,
                "snapshots": snaps,
                "snoozes": {s.ticket_id for s in snaps if s.snoozed},
                "escalated": {
                    e.ticket_id for e in rt.store.escalations() if e.escalated_at
                },
            },
        )

    @app.get("/ops")
    def ops_dashboard(
        request: Request, channel: str = "", status: str = ""
    ) -> Response:
        runs = rt.store.recent_runs(limit=50)
        sends = rt.store.recent_sends(
            limit=200, channel=channel or None, status=status or None
        )
        latest_warnings = next((r.warnings for r in runs if r.warnings), [])
        return templates.TemplateResponse(
            request,
            "ops.html.j2",
            {
                "runs": runs,
                "sends": sends,
                "channel": channel,
                "status": status,
                "warnings": latest_warnings,
                "channels": rt.cfg.app.channels.enabled,
                "escalations": rt.store.escalations(),
                "red_threshold": rt.cfg.app.thresholds.escalation_red_days,
            },
        )

    @app.post("/snooze")
    def snooze(
        ticket_id: Annotated[int, Form()],
        until: Annotated[str, Form()],
        reason: Annotated[str, Form()] = "",
    ) -> Response:
        try:
            until_date = date.fromisoformat(until)
        except ValueError:
            return RedirectResponse(
                f"/tickets/{ticket_id}?error=invalid+date", status_code=303
            )
        now = datetime.now(rt.cfg.tz)
        if until_date < now.date():
            return RedirectResponse(
                f"/tickets/{ticket_id}?error=date+is+in+the+past", status_code=303
            )
        rt.store.snooze(
            ticket_id, until=until_date, now=now, reason=reason or None, created_by="dashboard"
        )
        return RedirectResponse(f"/tickets/{ticket_id}", status_code=303)

    @app.post("/unsnooze")
    def unsnooze(ticket_id: Annotated[int, Form()]) -> Response:
        rt.store.unsnooze(ticket_id)
        return RedirectResponse(f"/tickets/{ticket_id}", status_code=303)

    @app.get("/preview")
    def preview(request: Request) -> Response:
        now = datetime.now(rt.cfg.tz)
        try:
            scored = fetch_and_score(rt.cfg, rt.glpi_factory, rt.store, now)
        except Exception as exc:  # noqa: BLE001 - GLPI down must render, not crash
            logger.exception("preview fetch failed")
            return templates.TemplateResponse(
                request,
                "preview.html.j2",
                {"error": str(exc), "previews": []},
                status_code=502,
            )
        digests, warnings = build_all_digests(
            rt.cfg,
            scored,
            snoozed_ids=set(rt.store.active_snoozes(now)),
            escalated_ids=set(),
            now=now,
        )
        previews = [
            {
                "owner": d.owner,
                "subject": rt.renderer.email_subject(d),
                "html": rt.renderer.email_html(d),
                "ticket_count": len(d.tickets),
            }
            for d in digests
        ]
        return templates.TemplateResponse(
            request,
            "preview.html.j2",
            {"error": None, "previews": previews, "warnings": warnings, "now": now},
        )

    @app.post("/run-now")
    def run_now(live: Annotated[str, Form()] = "") -> Response:
        if run_lock_busy():
            return RedirectResponse("/ops?flash=busy", status_code=303)
        dry_run = not live or rt.cfg.dry_run
        thread = threading.Thread(
            target=execute_nag_run,
            args=(rt.cfg, rt.store, rt.adapters, rt.glpi_factory),
            kwargs={"dry_run": dry_run, "trigger": "manual"},
            daemon=True,
        )
        thread.start()
        app.state.last_run_thread = thread
        return RedirectResponse("/ops?flash=run+started", status_code=303)

    @app.get("/tickets/{ticket_id}")
    def ticket_history(request: Request, ticket_id: int) -> Response:
        history = rt.store.ticket_history(ticket_id)
        if not history:
            return templates.TemplateResponse(
                request, "ticket.html.j2", {"ticket_id": ticket_id, "history": []},
                status_code=404,
            )
        return templates.TemplateResponse(
            request,
            "ticket.html.j2",
            {
                "ticket_id": ticket_id,
                "history": history,
                "sends": rt.store.sends_for_ticket(ticket_id),
                "snooze": rt.store.snooze_for(ticket_id),
                "latest": history[0],
            },
        )


def serve() -> int:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8080, log_config=None)  # noqa: S104
    return 0
