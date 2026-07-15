"""The nag-run orchestrator: fetch → score → snapshot → group → escalate → dispatch → log."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from nagbot.channels.base import ChannelAdapter, SendResult, begin_run
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
# E7-S3: the escalation loop serializes on its OWN lock (AD-1), never _RUN_LOCK.
_ESCALATION_LOCK = threading.Lock()

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


def build_alert_adapters(cfg: RuntimeConfig) -> list[object]:
    """Adapters for the escalation alert channels (AD-3). OpenWA only for now;
    Teams is added in E7-S5."""
    from nagbot.channels.openwa import OpenWaAdapter

    adapters: list[object] = []
    for name in cfg.app.escalation.alert_channels:
        if name == "openwa":
            adapters.append(OpenWaAdapter.from_config(cfg))
    return adapters


def _drain_acks(
    cfg: RuntimeConfig, store: Store, tickets_by_id: Mapping[int, object], now: datetime
) -> None:
    """AD-7: an inbound reply from a roster number acks every active, un-acked
    escalation whose current chain includes that number. Writes only ack columns."""
    from nagbot.engine.escalation import escalation_chain

    acks = store.unprocessed_acks()
    if not acks:
        return
    ack_id_by_sender: dict[str, int] = {}
    for a in acks:  # first ack id per sender
        ack_id_by_sender.setdefault(a.sender, a.id)
    senders = set(ack_id_by_sender)

    applied: set[int] = set()
    for esc in store.active_p0_escalations():
        if esc.acknowledged_at is not None:
            continue
        ticket = tickets_by_id.get(esc.ticket_id)
        if ticket is None:
            continue
        chain_numbers = {r.whatsapp for r in escalation_chain(ticket, cfg.app) if r.whatsapp}  # type: ignore[arg-type]
        matched = senders & chain_numbers
        if matched:
            sender = next(iter(matched))
            store.set_p0_acknowledged(esc.ticket_id, by=sender, now=now)
            applied.add(ack_id_by_sender[sender])

    # Only consume acks that were applied; RETAIN unmatched ones for a later tick (an ack
    # can arrive before its escalation is anchored) — but sweep anything older than the TTL
    # so the inbox can't grow unbounded.
    ttl = timedelta(minutes=cfg.app.escalation.ack_ttl_minutes)
    aged = {a.id for a in acks if now - a.received_at > ttl}
    store.mark_acks_processed(sorted(applied | aged), now=now)


def _revalidate_alerts(
    cfg: RuntimeConfig, glpi_factory: GlpiFactory, store: Store, result: object, now: datetime
) -> None:
    """AD-6: re-fetch each alert's ticket right before dispatch. Not-P0 → stop; a
    fetch failure is NEVER a stop (drop the alert this tick, retry next)."""
    from nagbot.engine.p0 import is_p0

    alerts = result.alerts  # type: ignore[attr-defined]
    if not alerts:
        return
    rule = cfg.app.escalation.p0_rule
    validated: list[object] = []
    try:
        with glpi_factory() as client:
            field_map = FieldMap.discover(
                client, overrides=cfg.app.glpi.field_ids, cache=store, now=now
            )
            for alert in alerts:
                try:
                    fresh = client.get_ticket(alert.ticket.id, field_map)
                except Exception:  # noqa: BLE001 - blind fetch failure must not stop a P0
                    logger.exception(
                        "revalidate get_ticket %d failed; skip dispatch", alert.ticket.id
                    )
                    continue
                if fresh is None or not is_p0(fresh, rule):
                    store.stop_p0_escalation(alert.ticket.id, reason="revalidated_not_p0", now=now)
                    continue
                validated.append(alert)
    except Exception:  # noqa: BLE001 - GLPI session down: drop dispatch this tick, no stops
        logger.exception("revalidate session failed; skipping dispatch this tick")
        result.alerts = []  # type: ignore[attr-defined]
        return
    result.alerts = validated  # type: ignore[attr-defined]


def execute_escalation_run(
    cfg: RuntimeConfig,
    store: Store,
    glpi_factory: GlpiFactory,
    *,
    dry_run: bool,
    now: datetime | None = None,
    alert_adapters: list[object] | None = None,
) -> int:
    """One escalation tick (AD-1): fetch → detect P0s → tick → send-then-persist.
    No-op unless escalation is enabled. Returns the number of alerts sent."""
    if not cfg.app.escalation.enabled:
        return 0
    if not _ESCALATION_LOCK.acquire(blocking=False):
        logger.info("escalation tick skipped: previous tick still running")
        return 0
    try:
        from nagbot.engine.escalation import (
            dispatch_alerts,
            escalation_tick,
            persist_tick_state,
        )
        from nagbot.engine.p0 import detect_p0s

        now = now or datetime.now(cfg.tz)
        scored = fetch_and_score(cfg, glpi_factory, store, now)
        tickets_by_id = {s.ticket.id: s.ticket for s in scored}
        p0 = detect_p0s(list(tickets_by_id.values()), cfg.app.escalation.p0_rule)
        _drain_acks(cfg, store, tickets_by_id, now)  # AD-7
        active = store.active_p0_escalations()
        result = escalation_tick(p0_tickets=p0, active=active, app=cfg.app, now=now)
        persist_tick_state(result, store=store, now=now)  # anchors/stops BEFORE re-validate
        _revalidate_alerts(cfg, glpi_factory, store, result, now)  # AD-6
        adapters = alert_adapters if alert_adapters is not None else build_alert_adapters(cfg)
        sent = dispatch_alerts(
            result, store=store, alert_adapters=adapters, now=now, dry_run=dry_run
        )
        logger.info(
            "escalation tick: %d P0(s), %d alert(s) sent, %d stop(s)",
            len(p0),
            sent,
            len(result.stops),
        )
        return sent
    finally:
        _ESCALATION_LOCK.release()


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
            s.ticket.id for s in scored if s.tier is Tier.ON_FIRE and s.ticket.id not in snoozed_ids
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
        begin_run(adapters)  # reset per-run adapter state (rate caps)
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
