"""The nag-run orchestrator: fetch → score → snapshot → group → escalate → dispatch → log."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from nagbot.channels.base import ChannelAdapter, SendResult
from nagbot.config import RuntimeConfig
from nagbot.digest.builder import Digest, build_digests, build_rollup
from nagbot.engine.aging import compute_metrics
from nagbot.engine.ownership import ScoredTicket, group_by_owner
from nagbot.engine.tiers import Tier, classify
from nagbot.glpi.client import GlpiClient
from nagbot.glpi.fields import FieldMap
from nagbot.store.repo import SnapshotRow, Store

logger = logging.getLogger(__name__)

# One nag run at a time, shared by cron and dashboard run-now.
_RUN_LOCK = threading.Lock()

GlpiFactory = Callable[[], GlpiClient]


@dataclass
class RunReport:
    run_id: int
    trigger: str
    dry_run: bool
    status: str  # ok | failed | busy | skipped
    tickets_seen: int = 0
    digests_built: int = 0
    sends: list[SendResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def summary(self) -> str:
        return (
            f"run #{self.run_id} [{self.trigger}] {self.status}"
            f"{' DRY-RUN' if self.dry_run else ''}: {self.tickets_seen} tickets, "
            f"{self.digests_built} digests, {len(self.sends)} sends, "
            f"{len(self.warnings)} warnings"
        )


def fetch_and_score(
    cfg: RuntimeConfig, glpi_factory: GlpiFactory, store: Store | None, now: datetime
) -> list[ScoredTicket]:
    """Pull open tickets and compute metrics + tier for each (shared with /preview)."""
    with glpi_factory() as client:
        field_map = FieldMap.discover(
            client, overrides=cfg.app.glpi.field_ids, cache=store, now=now
        )
        tickets = client.search_open_tickets(field_map)
    holidays = frozenset(cfg.app.holidays)
    scored = []
    for ticket in tickets:
        metrics = compute_metrics(ticket, now, cfg.app.thresholds, cfg.tz, holidays)
        scored.append(
            ScoredTicket(ticket=ticket, metrics=metrics, tier=classify(metrics, cfg.app.thresholds))
        )
    return scored


def build_all_digests(
    cfg: RuntimeConfig,
    scored: list[ScoredTicket],
    *,
    snoozed_ids: set[int],
    escalated_ids: set[int],
    now: datetime,
) -> tuple[list[Digest], list[str]]:
    """Group non-snoozed tickets by owner and build digests (shared with /preview)."""
    active = [s for s in scored if s.ticket.id not in snoozed_ids]
    grouped, warnings = group_by_owner(active, cfg.app)
    return build_digests(grouped, escalated_ids=escalated_ids, now=now), warnings


def execute_nag_run(
    cfg: RuntimeConfig,
    store: Store,
    adapters: list[ChannelAdapter],
    glpi_factory: GlpiFactory,
    *,
    dry_run: bool,
    trigger: str,
    now: datetime | None = None,
) -> RunReport:
    if not _RUN_LOCK.acquire(blocking=False):
        logger.warning("nag run requested while another is in progress — skipping")
        return RunReport(run_id=-1, trigger=trigger, dry_run=dry_run, status="busy")
    try:
        return _execute_locked(cfg, store, adapters, glpi_factory, dry_run, trigger, now)
    finally:
        _RUN_LOCK.release()


def _execute_locked(
    cfg: RuntimeConfig,
    store: Store,
    adapters: list[ChannelAdapter],
    glpi_factory: GlpiFactory,
    dry_run: bool,
    trigger: str,
    now: datetime | None,
) -> RunReport:
    now = now or datetime.now(cfg.tz)
    run_id = store.start_run(trigger=trigger, dry_run=dry_run, now=now)
    report = RunReport(run_id=run_id, trigger=trigger, dry_run=dry_run, status="ok")
    try:
        scored = fetch_and_score(cfg, glpi_factory, store, now)
        report.tickets_seen = len(scored)
        snoozed_ids = set(store.active_snoozes(now))

        # snapshot everything (snoozed included, flagged) — feeds dashboards/history
        grouped_all, _ = group_by_owner(scored, cfg.app)
        snapshots = [
            SnapshotRow(
                run_id=run_id,
                ticket_id=s.ticket.id,
                title=s.ticket.title,
                status=s.ticket.status,
                date_opened=s.ticket.date_opened,
                date_mod=s.ticket.date_mod,
                sla_due=s.metrics.sla_due,
                owner_key=owner.key,
                owner_name=owner.display_name,
                tier=s.tier.value,
                age_bd=s.metrics.age_bd,
                stale_bd=s.metrics.stale_bd,
                sla_status=s.metrics.sla_status.value,
                snoozed=s.ticket.id in snoozed_ids,
            )
            for owner, tickets in grouped_all.items()
            for s in tickets
        ]
        store.save_snapshots(snapshots)

        # escalation streaks: only active (non-snoozed) red tickets keep their streak
        red_ids = {
            s.ticket.id
            for s in scored
            if s.tier is Tier.ON_FIRE and s.ticket.id not in snoozed_ids
        }
        newly_escalated = store.bump_red_streaks(
            red_ids,
            run_date=now.astimezone(cfg.tz).date(),
            threshold=cfg.app.thresholds.escalation_red_days,
            now=now,
        )

        digests, warnings = build_all_digests(
            cfg, scored, snoozed_ids=snoozed_ids, escalated_ids=set(newly_escalated), now=now
        )
        report.digests_built = len(digests)
        report.warnings = warnings
        for warning in warnings:
            logger.warning("ownership: %s", warning)

        for digest in digests:
            for adapter in adapters:
                result = _safe_send(adapter, digest, dry_run)
                report.sends.append(result)
                store.log_send(
                    run_id=run_id,
                    kind="digest",
                    channel=result.channel,
                    recipient=result.recipient,
                    cc=result.cc,
                    owner_key=digest.owner.key,
                    ticket_ids=digest.ticket_ids,
                    status=result.status,
                    detail=result.detail,
                    now=now,
                )
                if digest.escalated and result.cc:
                    store.log_send(
                        run_id=run_id,
                        kind="escalation",
                        channel=result.channel,
                        recipient=result.cc,
                        owner_key=digest.owner.key,
                        ticket_ids=[s.ticket.id for s in digest.escalated],
                        status=result.status,
                        detail=f"manager CC for {digest.owner.display_name}",
                        now=now,
                    )

        store.finish_run(
            run_id,
            status="ok",
            now=datetime.now(cfg.tz),
            tickets_seen=report.tickets_seen,
            digests_built=report.digests_built,
            sends_attempted=len(report.sends),
            warnings=report.warnings,
        )
    except Exception as exc:  # noqa: BLE001 - record the failure, don't crash the scheduler
        logger.exception("nag run %d failed", run_id)
        report.status = "failed"
        report.error = str(exc)
        store.finish_run(run_id, status="failed", now=datetime.now(cfg.tz), error=str(exc))
    logger.info("%s", report.summary())
    return report


def _safe_send(adapter: ChannelAdapter, digest: Digest, dry_run: bool) -> SendResult:
    try:
        return adapter.send_digest(digest, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001 - one adapter failure must not kill the run
        logger.exception("%s adapter crashed for %s", adapter.name, digest.owner.key)
        return SendResult(adapter.name, digest.owner.key, "failed", detail=str(exc))


def execute_rollup_run(
    cfg: RuntimeConfig,
    store: Store,
    adapters: list[ChannelAdapter],
    *,
    dry_run: bool,
    now: datetime | None = None,
) -> RunReport:
    """Monday manager rollup: WIP per person, tier distribution, worst-offender leaderboard.

    Built from the latest snapshots (the 08:00 digest run refreshed them 30 minutes
    earlier) — no fresh GLPI fetch.
    """
    now = now or datetime.now(cfg.tz)
    _, snapshots = store.latest_snapshot()
    if not snapshots:
        logger.info("rollup skipped: no snapshots yet (no digest run has completed)")
        return RunReport(run_id=-1, trigger="rollup", dry_run=dry_run, status="skipped")

    run_id = store.start_run(trigger="rollup", dry_run=dry_run, now=now)
    report = RunReport(run_id=run_id, trigger="rollup", dry_run=dry_run, status="ok")
    report.tickets_seen = len(snapshots)
    try:
        rollup = build_rollup(snapshots, now=now)
        for adapter in adapters:
            try:
                result = adapter.send_rollup(rollup, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001 - mirror digest-path isolation
                logger.exception("%s rollup send crashed", adapter.name)
                result = SendResult(adapter.name, "-", "failed", detail=str(exc))
            report.sends.append(result)
            store.log_send(
                run_id=run_id,
                kind="rollup",
                channel=result.channel,
                recipient=result.recipient,
                status=result.status,
                detail=result.detail,
                ticket_ids=[s.ticket_id for s in rollup.leaderboard],
                now=now,
            )
        store.finish_run(
            run_id,
            status="ok",
            now=datetime.now(cfg.tz),
            tickets_seen=report.tickets_seen,
            sends_attempted=len(report.sends),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("rollup run %d failed", run_id)
        report.status = "failed"
        report.error = str(exc)
        store.finish_run(run_id, status="failed", now=datetime.now(cfg.tz), error=str(exc))
    logger.info("%s", report.summary())
    return report
