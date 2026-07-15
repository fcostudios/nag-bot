"""The P0 escalation state machine (spine AD-1/AD-3/AD-4/AD-5/AD-8).

Pure, `now`-injected logic: given the current P0 tickets and the active escalation
rows, `escalation_tick` decides what to open, climb, hold, or stop. The runner
(`run.execute_escalation_run`) performs the side effects (send then persist), so a
crash between send and write re-sends at worst once and a send failure retries.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from zoneinfo import ZoneInfo

from nagbot.channels.base import EscalationAlert, SendResult
from nagbot.config import AppConfig
from nagbot.engine.ownership import resolve_owner
from nagbot.glpi.models import Ticket
from nagbot.store.repo import P0EscalationRow, Store


@dataclass(frozen=True)
class Recipient:
    name: str
    whatsapp: str | None


def _recipient_from_ref(ref: str, app: AppConfig) -> Recipient:
    """A default_triage ref is either an E.164 number or an owners-key."""
    if ref.startswith("+"):
        return Recipient("triage", ref)
    owner = app.owners.get(ref)
    return Recipient(owner.name, owner.whatsapp) if owner else Recipient(ref, None)


def escalation_chain(ticket: Ticket, app: AppConfig) -> list[Recipient]:
    """owner → manager → default triage. Rungs may have no whatsapp (recorded, not
    dispatched). Adjacent duplicate numbers collapse."""
    owner = resolve_owner(ticket, app).owner
    chain: list[Recipient] = [Recipient(owner.display_name, owner.whatsapp)]
    if owner.manager_email:
        mgr = next((o for o in app.owners.values() if o.email == owner.manager_email), None)
        chain.append(
            Recipient(mgr.name, mgr.whatsapp) if mgr else Recipient(owner.manager_email, None)
        )
    if app.escalation.default_triage:
        chain.append(_recipient_from_ref(app.escalation.default_triage, app))

    deduped: list[Recipient] = []
    for r in chain:
        if deduped and r.whatsapp is not None and r.whatsapp == deduped[-1].whatsapp:
            continue
        deduped.append(r)
    return deduped


def build_alert_text(ticket: Ticket, rung: int, *, is_climb: bool, tz: ZoneInfo) -> str:
    when = ticket.date_opened.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    head = f"🚨 P0 ESCALATION (rung {rung})" if is_climb else "🔴 P0"
    system = ticket.category or "system"
    lines = [
        f"{head} — {system}",
        f"Reported: {when}",
        f"Broken: #{ticket.id} {ticket.title}",
        ticket.url,
    ]
    if is_climb:
        lines.append("No acknowledgement yet — escalating up the chain.")
    return "\n".join(lines)


@dataclass(frozen=True)
class AlertToSend:
    ticket: Ticket
    recipient: Recipient
    rung: int
    is_climb: bool
    text: str
    row: P0EscalationRow  # persisted by the runner ONLY after a successful send


@dataclass
class TickResult:
    alerts: list[AlertToSend]  # send-then-persist
    upserts: list[P0EscalationRow]  # persist immediately (state change, nothing to send)
    stops: list[tuple[int, str]]  # persist immediately (ticket_id, reason)


def escalation_tick(
    *, p0_tickets: list[Ticket], active: list[P0EscalationRow], app: AppConfig, now: object
) -> TickResult:
    """One idempotent tick. `now` is a tz-aware datetime (typed loosely to stay import-light)."""
    dwell = timedelta(minutes=app.escalation.dwell_minutes)
    tz = ZoneInfo(app.timezone)
    by_id: dict[int, Ticket] = {t.id: t for t in p0_tickets}
    active_by_id = {e.ticket_id: e for e in active}
    result = TickResult([], [], [])

    # AD-5 gate: stop any active escalation whose ticket is no longer a P0 this fetch.
    for e in active:
        if e.ticket_id not in by_id:
            result.stops.append((e.ticket_id, "resolved_or_downgraded"))

    for tid, ticket in by_id.items():
        chain = escalation_chain(ticket, app)
        top = len(chain) - 1
        existing = active_by_id.get(tid)

        if existing is None:
            # Anchor the detection NOW, regardless of whether rung 0's send succeeds —
            # otherwise a failing/unreachable owner would re-open every tick, resetting
            # the dwell clock, and the ladder could never climb (the exact failure mode
            # escalation exists for).
            anchor = P0EscalationRow(ticket_id=tid, p0_detected_at=now, current_rung=0)  # type: ignore[arg-type]
            result.upserts.append(anchor)
            recipient = chain[0] if chain else Recipient("", None)
            if recipient.whatsapp:
                text = build_alert_text(ticket, 0, is_climb=False, tz=tz)
                row = replace(anchor, last_notified_at=now)  # type: ignore[arg-type]
                result.alerts.append(AlertToSend(ticket, recipient, 0, False, text, row))
            continue

        # AD-8: target rung is cumulative (catch-up), but climb at most ONE per tick.
        elapsed = now - existing.p0_detected_at  # type: ignore[operator]
        target = min(int(elapsed / dwell), top) if dwell else top
        if target > existing.current_rung:
            new_rung = existing.current_rung + 1
            row = replace(existing, current_rung=new_rung, last_notified_at=now)  # type: ignore[arg-type]
            _emit(result, ticket, chain, new_rung, is_climb=True, row=row, tz=tz)
    return result


def _emit(
    result: TickResult,
    ticket: Ticket,
    chain: list[Recipient],
    rung: int,
    *,
    is_climb: bool,
    row: P0EscalationRow,
    tz: ZoneInfo,
) -> None:
    recipient = chain[rung] if 0 <= rung < len(chain) else Recipient("", None)
    if recipient.whatsapp:
        text = build_alert_text(ticket, rung, is_climb=is_climb, tz=tz)
        result.alerts.append(AlertToSend(ticket, recipient, rung, is_climb, text, row))
    else:
        # unreachable rung — advance state now (no send) so the ladder can climb past it.
        result.upserts.append(row)


def dispatch_alerts(
    result: TickResult,
    *,
    store: Store,
    alert_adapters: list[object],
    now: object,
    dry_run: bool,
) -> int:
    """Perform the side effects: stops + no-send upserts immediately; each alert is
    SENT first, then its row persisted only on a non-failed result (AD-4/AD-8). Returns
    the number of alerts actually sent."""
    for tid, reason in result.stops:
        store.stop_p0_escalation(tid, reason=reason, now=now)  # type: ignore[arg-type]
    for row in result.upserts:
        store.upsert_p0_escalation(row)

    sent = 0
    for alert in result.alerts:
        res = _dispatch_one(alert, alert_adapters, dry_run=dry_run)
        store.log_send(
            run_id=None,
            kind="p0_alert",
            channel=res.channel,
            recipient=res.recipient,
            status=res.status,
            now=now,  # type: ignore[arg-type]
            ticket_ids=[alert.ticket.id],
            detail=f"rung {alert.rung}: {res.detail}",
        )
        if res.status in ("sent", "dry_run"):
            # Persist AFTER a successful send. A climb is a targeted rung UPDATE (never
            # INSERT OR REPLACE) so it can't clobber ack/stop columns set concurrently
            # (E7-S4); an open writes the full anchor+notified row.
            if alert.is_climb:
                stamp = alert.row.last_notified_at or now
                store.advance_p0_rung(
                    alert.row.ticket_id, rung=alert.row.current_rung, now=stamp  # type: ignore[arg-type]
                )
            else:
                store.upsert_p0_escalation(alert.row)
            sent += 1
    return sent


def _dispatch_one(alert: AlertToSend, alert_adapters: list[object], *, dry_run: bool) -> SendResult:
    """AD-3: try each alert channel; sent/dry_run stops; failed/timeout/skipped falls
    through; fail fast if no channel implements send_alert."""
    msg = EscalationAlert(recipient=alert.recipient.whatsapp or "", text=alert.text)
    last: SendResult | None = None
    implementers = 0
    for adapter in alert_adapters:
        send_alert = getattr(adapter, "send_alert", None)
        if not callable(send_alert):
            continue
        implementers += 1
        last = send_alert(msg, dry_run=dry_run)
        if last.status in ("sent", "dry_run"):
            return last
    if implementers == 0:
        raise RuntimeError("no configured alert channel implements send_alert")
    return last or SendResult("none", msg.recipient, "failed", detail="no alert channel")
