"""E7-S4: ack inbox store, tick-holds-on-ack, and AD-6 re-validation in the runner."""

from datetime import timedelta

from nagbot.engine.escalation import escalation_tick
from nagbot.glpi.models import Ticket
from nagbot.run import execute_escalation_run
from nagbot.store.repo import P0EscalationRow, Store

# reuse the runtime/fakes/helpers from the escalation test module
from tests.unit.test_escalation import APP, NOW, FakeAdapter, _FakeGlpi, _runtime, tk


def test_ack_inbox_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "ack.db")
    store.append_ack(sender="+593999999991", text="on it", now=NOW)
    acks = store.unprocessed_acks()
    assert len(acks) == 1 and acks[0].sender == "+593999999991"
    store.mark_acks_processed([acks[0].id], now=NOW)
    assert store.unprocessed_acks() == []


def test_set_acknowledged_targeted(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "ack2.db")
    store.upsert_p0_escalation(P0EscalationRow(ticket_id=1, p0_detected_at=NOW, current_rung=2))
    store.set_p0_acknowledged(1, by="+593999999992", now=NOW)
    row = store.active_p0_escalations()[0]
    assert row.acknowledged_by == "+593999999992" and row.current_rung == 2  # rung untouched


def test_tick_holds_acked_escalation() -> None:
    active = [
        P0EscalationRow(
            ticket_id=1,
            p0_detected_at=NOW - timedelta(minutes=20),
            current_rung=0,
            acknowledged_at=NOW - timedelta(minutes=10),
        )
    ]
    res = escalation_tick(p0_tickets=[tk(1)], active=active, app=APP, now=NOW)
    assert res.alerts == []  # acked → no climb despite dwell elapsed


def test_tick_stops_acked_ticket_when_resolved() -> None:
    active = [P0EscalationRow(ticket_id=1, p0_detected_at=NOW, current_rung=0, acknowledged_at=NOW)]
    res = escalation_tick(p0_tickets=[], active=active, app=APP, now=NOW)  # ticket gone
    assert res.stops == [(1, "resolved_or_downgraded")]


class _FakeGlpiDowngrade(_FakeGlpi):
    """search returns the P0, but the re-fetch (get_ticket) returns a downgraded ticket."""

    def get_ticket(self, ticket_id: int, field_map: object) -> Ticket | None:
        return tk(ticket_id, priority=3)  # no longer P0


def test_revalidate_drops_and_stops_non_p0(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "rv.db")
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True),
        store,
        lambda: _FakeGlpiDowngrade([tk(1)]),
        dry_run=False,
        now=NOW,
        alert_adapters=[adapter],
    )
    assert sent == 0 and adapter.calls == 0  # alert dropped on re-validate
    assert store.active_p0_escalations() == []  # escalation stopped


class _FakeGlpiRaises(_FakeGlpi):
    def get_ticket(self, ticket_id: int, field_map: object) -> Ticket | None:
        raise RuntimeError("glpi down")


def test_revalidate_fetch_error_is_never_a_stop(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "rv2.db")
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True),
        store,
        lambda: _FakeGlpiRaises([tk(1)]),
        dry_run=False,
        now=NOW,
        alert_adapters=[adapter],
    )
    assert sent == 0 and adapter.calls == 0  # dropped this tick...
    # ...but the anchor persisted (open) and NOT stopped → retries next tick
    active = store.active_p0_escalations()
    assert len(active) == 1 and active[0].stopped_reason is None


def test_ack_drain_halts_climb(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "drain.db")
    # an escalation past dwell that WOULD climb
    store.upsert_p0_escalation(
        P0EscalationRow(ticket_id=1, p0_detected_at=NOW - timedelta(minutes=6), current_rung=0)
    )
    store.append_ack(sender="+593999999991", text="on it", now=NOW)  # owner replies
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True),
        store,
        lambda: _FakeGlpi([tk(1)]),
        dry_run=False,
        now=NOW,
        alert_adapters=[adapter],
    )
    assert sent == 0  # acked → no climb this tick
    row = store.active_p0_escalations()[0]
    assert row.acknowledged_by == "+593999999991" and row.current_rung == 0
    assert store.unprocessed_acks() == []  # ack consumed


def test_ack_retained_until_escalation_exists(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """An ack arriving before its escalation is anchored must NOT be lost (HIGH fix)."""
    store = Store(tmp_path / "ret.db")
    store.append_ack(sender="+593999999991", text="on it", now=NOW)
    # tick 1: drain runs before the escalation exists → ack retained; tick then opens it
    execute_escalation_run(
        _runtime(enabled=True), store, lambda: _FakeGlpi([tk(1)]),
        dry_run=False, now=NOW, alert_adapters=[FakeAdapter()],
    )
    assert len(store.unprocessed_acks()) == 1  # retained, not dropped
    assert len(store.active_p0_escalations()) == 1
    # tick 2: escalation now exists → the retained ack applies
    execute_escalation_run(
        _runtime(enabled=True), store, lambda: _FakeGlpi([tk(1)]),
        dry_run=False, now=NOW + timedelta(minutes=1), alert_adapters=[FakeAdapter()],
    )
    assert store.unprocessed_acks() == []
    assert store.active_p0_escalations()[0].acknowledged_by == "+593999999991"


class _FakeGlpiGone(_FakeGlpi):
    """search shows the P0, but the re-fetch finds it solved/closed (get_ticket → None)."""
    def get_ticket(self, ticket_id: int, field_map: object) -> Ticket | None:
        return None


def test_revalidate_stops_when_ticket_solved(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "solved.db")
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True), store, lambda: _FakeGlpiGone([tk(1)]),
        dry_run=False, now=NOW, alert_adapters=[adapter],
    )
    assert sent == 0 and adapter.calls == 0
    assert store.active_p0_escalations() == []  # solved on re-fetch → stopped
