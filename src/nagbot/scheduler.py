"""APScheduler wiring: digest cron + rollup cron from the YAML config."""

from __future__ import annotations

from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from nagbot.config import RuntimeConfig


def build_scheduler(
    cfg: RuntimeConfig,
    nag_job: Callable[[], object],
    rollup_job: Callable[[], object],
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=cfg.app.timezone)
    common = {"coalesce": True, "misfire_grace_time": 3600, "max_instances": 1}
    scheduler.add_job(
        nag_job,
        CronTrigger.from_crontab(cfg.app.schedule.digest_cron, timezone=cfg.app.timezone),
        id="digest",
        name="daily nag digest",
        **common,
    )
    scheduler.add_job(
        rollup_job,
        CronTrigger.from_crontab(cfg.app.schedule.rollup_cron, timezone=cfg.app.timezone),
        id="rollup",
        name="weekly manager rollup",
        **common,
    )
    return scheduler
