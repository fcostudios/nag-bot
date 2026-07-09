"""The lite backend: FastAPI app factory, Basic-auth middleware, healthz, dashboards."""

from __future__ import annotations

import base64
import binascii
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from nagbot import __version__
from nagbot.digest.builder import build_rollup
from nagbot.run import execute_nag_run, execute_rollup_run
from nagbot.runtime import Runtime, build_runtime
from nagbot.scheduler import build_scheduler

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
            },
        )


def serve() -> int:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8080, log_config=None)  # noqa: S104
    return 0
