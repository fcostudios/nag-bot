"""Serve entrypoint. E3-S1 replaces this scheduler-only keepalive with FastAPI + uvicorn."""

from __future__ import annotations

import logging
import threading

from nagbot.run import execute_nag_run, execute_rollup_run
from nagbot.runtime import Runtime, build_runtime
from nagbot.scheduler import build_scheduler

logger = logging.getLogger(__name__)


def make_jobs(rt: Runtime) -> tuple:
    def nag_job() -> None:
        execute_nag_run(
            rt.cfg, rt.store, rt.adapters, rt.glpi_factory, dry_run=rt.cfg.dry_run, trigger="cron"
        )

    def rollup_job() -> None:
        execute_rollup_run(rt.cfg, rt.store, rt.adapters, dry_run=rt.cfg.dry_run)

    return nag_job, rollup_job


def serve() -> int:
    rt = build_runtime()
    nag_job, rollup_job = make_jobs(rt)
    scheduler = build_scheduler(rt.cfg, nag_job, rollup_job)
    scheduler.start()
    logger.info(
        "nagbot scheduler running (digest: %s, rollup: %s, tz: %s, dry_run: %s) — "
        "web dashboard lands in Epic 3",
        rt.cfg.app.schedule.digest_cron,
        rt.cfg.app.schedule.rollup_cron,
        rt.cfg.app.timezone,
        rt.cfg.dry_run,
    )
    try:
        threading.Event().wait()  # block forever; container stops us with SIGTERM
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=False)
        rt.store.close()
    return 0
