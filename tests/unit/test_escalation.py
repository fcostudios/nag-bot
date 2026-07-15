"""E7-S3: escalation ladder — roster, pure tick engine, alert text, store, dispatch."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from nagbot.channels.base import SendResult
from nagbot.config import AppConfig
from nagbot.engine.escalation import (
    build_alert_text,
    dispatch_alerts,
    escalation_chain,
    escalation_tick,
    persist_tick_state,
)
from nagbot.glpi.models import Ticket
from nagbot.store.repo import P0EscalationRow, Store

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
GYE = "America/Guayaquil"

APP = AppConfig.model_validate(
    {
        "timezone": GYE,
        "escalation": {"enabled": True, "dwell_minutes": 5, "default_triage": "triage"},
        "owners": {
            "jdoe": {
                "name": "Juan Doe",
                "email": "jdoe@x.com",
                "whatsapp": "+593999999991",
                "manager": "boss@x.com",
            },
            "boss": {"name": "Boss", "email": "boss@x.com", "whatsapp": "+593999999992"},
            "triage": {"name": "Triage", "email": "t@x.com", "whatsapp": "+593999999993"},
        },
    }
)


def tk(tid: int = 1, tech: str = "jdoe", priority: int = 6, title: str = "Payments down") -> Ticket:
    return Ticket(
        id=tid,
        title=title,
        status=2,
        date_opened=NOW,
        date_mod=NOW,
        tech_names=[tech],
        priority=priority,
        category="TECNOLOGIA > SAP",
        url=f"https://glpi/front/ticket.form.php?id={tid}",
    )


# --- roster -------------------------------------------------------------------


def test_escalation_chain_owner_manager_triage() -> None:
    chain = escalation_chain(tk(), APP)
    assert [r.whatsapp for r in chain] == ["+593999999991", "+593999999992", "+593999999993"]
    assert [r.name for r in chain] == ["Juan Doe", "Boss", "Triage"]


def test_chain_triage_as_e164_and_missing_manager() -> None:
    app = AppConfig.model_validate(
        {
            "timezone": GYE,
            "escalation": {"enabled": True, "default_triage": "+593911111111"},
            "owners": {"jdoe": {"name": "Juan", "whatsapp": "+593999999991"}},  # no manager
        }
    )
    chain = escalation_chain(tk(), app)
    assert [r.whatsapp for r in chain] == ["+593999999991", "+593911111111"]


# --- pure tick engine ---------------------------------------------------------


def test_open_new_p0_alerts_rung0() -> None:
    res = escalation_tick(p0_tickets=[tk(1)], active=[], app=APP, now=NOW)
    assert len(res.alerts) == 1 and res.stops == []
    a = res.alerts[0]
    assert a.rung == 0 and a.is_climb is False and a.recipient.whatsapp == "+593999999991"
    assert a.row.current_rung == 0


def test_climb_one_rung_after_dwell() -> None:
    active = [
        P0EscalationRow(ticket_id=1, p0_detected_at=NOW - timedelta(minutes=6), current_rung=0)
    ]
    res = escalation_tick(p0_tickets=[tk(1)], active=active, app=APP, now=NOW)
    assert len(res.alerts) == 1
    a = res.alerts[0]
    assert a.rung == 1 and a.is_climb is True and a.recipient.name == "Boss"
    assert a.row.current_rung == 1


def test_climb_at_most_one_rung_per_tick_even_after_long_gap() -> None:
    # 12 min elapsed at rung 0 → target rung 2, but must climb only to rung 1
    active = [
        P0EscalationRow(ticket_id=1, p0_detected_at=NOW - timedelta(minutes=12), current_rung=0)
    ]
    res = escalation_tick(p0_tickets=[tk(1)], active=active, app=APP, now=NOW)
    assert len(res.alerts) == 1 and res.alerts[0].rung == 1


def test_hold_at_top_rung() -> None:
    active = [
        P0EscalationRow(ticket_id=1, p0_detected_at=NOW - timedelta(minutes=30), current_rung=2)
    ]
    res = escalation_tick(p0_tickets=[tk(1)], active=active, app=APP, now=NOW)
    assert res.alerts == []  # top rung is 2 → nothing to climb


def test_stop_when_ticket_no_longer_p0() -> None:
    active = [
        P0EscalationRow(ticket_id=99, p0_detected_at=NOW - timedelta(minutes=1), current_rung=0)
    ]
    res = escalation_tick(p0_tickets=[], active=active, app=APP, now=NOW)
    assert res.stops == [(99, "resolved_or_downgraded")] and res.alerts == []


def test_unreachable_rung_advances_state_without_alert() -> None:
    # an owner with no whatsapp → rung 0 can't dispatch, but state opens so it can climb
    app = AppConfig.model_validate(
        {
            "timezone": GYE,
            "escalation": {"enabled": True},
            "owners": {"jdoe": {"name": "Juan"}},  # no whatsapp
        }
    )
    res = escalation_tick(p0_tickets=[tk(1)], active=[], app=app, now=NOW)
    assert res.alerts == [] and len(res.upserts) == 1 and res.upserts[0].current_rung == 0


def test_alert_text_has_system_time_title_link_and_marker() -> None:
    text = build_alert_text(tk(7, title="SAP broken"), rung=1, is_climb=True, tz=ZoneInfo(GYE))
    assert "SAP" in text and "#7" in text and "SAP broken" in text
    assert "id=7" in text and "ESCALATION" in text and "escalating" in text.lower()


# --- store round-trip ---------------------------------------------------------


def test_p0_escalation_store_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "e.db")
    store.upsert_p0_escalation(P0EscalationRow(ticket_id=1, p0_detected_at=NOW, current_rung=1))
    active = store.active_p0_escalations()
    assert len(active) == 1 and active[0].current_rung == 1
    store.stop_p0_escalation(1, reason="resolved_or_downgraded", now=NOW)
    assert store.active_p0_escalations() == []


# --- dispatch: send-then-persist ----------------------------------------------


class FakeAdapter:
    def __init__(self, status: str = "sent", name: str = "openwa") -> None:
        self.status = status
        self.name = name
        self.calls = 0

    def send_alert(self, alert: object, *, dry_run: bool) -> SendResult:
        self.calls += 1
        st = "dry_run" if dry_run else self.status
        return SendResult(self.name, "x", st)  # type: ignore[arg-type]


def _tick_with_one_alert() -> object:
    return escalation_tick(p0_tickets=[tk(1)], active=[], app=APP, now=NOW)


def test_dispatch_persists_row_on_sent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "d.db")
    res = _tick_with_one_alert()
    sent = dispatch_alerts(
        res, store=store, alert_adapters=[FakeAdapter("sent")], now=NOW, dry_run=False
    )
    assert sent == 1
    assert len(store.active_p0_escalations()) == 1  # row persisted after successful send


def test_dispatch_failed_climb_does_not_advance_rung(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "d2.db")
    # anchored at rung 0 with dwell elapsed → tick wants to climb to rung 1
    store.upsert_p0_escalation(
        P0EscalationRow(ticket_id=1, p0_detected_at=NOW - timedelta(minutes=6), current_rung=0)
    )
    res = escalation_tick(
        p0_tickets=[tk(1)], active=store.active_p0_escalations(), app=APP, now=NOW
    )
    sent = dispatch_alerts(
        res, store=store, alert_adapters=[FakeAdapter("failed")], now=NOW, dry_run=False
    )
    assert sent == 0
    assert store.active_p0_escalations()[0].current_rung == 0  # failed climb → not advanced


def test_dispatch_dry_run_persists(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "d3.db")
    res = _tick_with_one_alert()
    adapter = FakeAdapter("sent")
    dispatch_alerts(res, store=store, alert_adapters=[adapter], now=NOW, dry_run=True)
    assert len(store.active_p0_escalations()) == 1


def test_dispatch_fails_fast_without_send_alert_channel(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "d4.db")
    res = _tick_with_one_alert()

    class NoAlert:
        name = "x"

    with pytest.raises(RuntimeError):
        dispatch_alerts(res, store=store, alert_adapters=[NoAlert()], now=NOW, dry_run=False)


# --- Finding 1 regression: open anchors the clock even when rung-0 send fails ---


def test_open_anchors_clock_even_on_failed_send(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "anc.db")
    res = escalation_tick(p0_tickets=[tk(1)], active=[], app=APP, now=NOW)
    persist_tick_state(res, store=store, now=NOW)  # anchor persists regardless of send
    dispatch_alerts(
        res, store=store, alert_adapters=[FakeAdapter("failed")], now=NOW, dry_run=False
    )
    active = store.active_p0_escalations()
    assert len(active) == 1  # anchor persisted despite the failed rung-0 send
    assert active[0].p0_detected_at == NOW and active[0].current_rung == 0
    assert active[0].last_notified_at is None  # not notified → retries rung 0 next tick


# --- runner (execute_escalation_run) end-to-end with fakes (AC6/AC7) ------------

from pathlib import Path  # noqa: E402

from nagbot.config import EnvSettings, RuntimeConfig  # noqa: E402
from nagbot.run import execute_escalation_run  # noqa: E402

_OWNERS = {
    "jdoe": {
        "name": "Juan Doe",
        "email": "jdoe@x.com",
        "whatsapp": "+593999999991",
        "manager": "boss@x.com",
    },
    "boss": {"name": "Boss", "email": "boss@x.com", "whatsapp": "+593999999992"},
    "triage": {"name": "Triage", "email": "t@x.com", "whatsapp": "+593999999993"},
}


def _runtime(*, enabled: bool, notice: bool = True) -> RuntimeConfig:
    env = EnvSettings(
        glpi_base_url="https://x/apirest.php",
        glpi_app_token="a",  # noqa: S106
        glpi_user_token="u",
        nagbot_config_path=Path("/nonexistent"),  # noqa: S106
    )
    app = AppConfig.model_validate(
        {
            "timezone": GYE,
            "escalation": {
                "enabled": enabled,
                "transparency_notice_given": notice,
                "dwell_minutes": 5,
                "default_triage": "triage",
            },
            "owners": _OWNERS,
        }
    )
    return RuntimeConfig(env=env, app=app, dry_run=False)


class _FakeGlpi:
    def __init__(self, tickets: list[Ticket]) -> None:
        self.tickets = tickets

    def __enter__(self) -> "_FakeGlpi":
        return self

    def __exit__(self, *a: object) -> bool:
        return False

    def list_search_options(self, itemtype: str = "Ticket") -> dict[str, object]:
        return {}

    def search_open_tickets(self, field_map: object) -> list[Ticket]:
        return self.tickets

    def get_ticket(self, ticket_id: int, field_map: object) -> Ticket | None:
        return next((t for t in self.tickets if t.id == ticket_id), None)


def _factory(tickets: list[Ticket]):  # type: ignore[no-untyped-def]
    def make() -> _FakeGlpi:
        return _FakeGlpi(tickets)

    return make


def test_execute_escalation_run_noop_when_disabled(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "r0.db")
    sent = execute_escalation_run(
        _runtime(enabled=False),
        store,
        _factory([tk(1)]),
        dry_run=True,
        alert_adapters=[FakeAdapter()],
    )
    assert sent == 0 and store.active_p0_escalations() == []


def test_execute_escalation_run_happy_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "r1.db")
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True),
        store,
        _factory([tk(1)]),
        dry_run=False,
        now=NOW,
        alert_adapters=[adapter],
    )
    assert sent == 1 and adapter.calls == 1
    assert len(store.active_p0_escalations()) == 1


def test_bad_alert_channels_rejected_at_load() -> None:
    with pytest.raises(ValidationError):  # unknown channel → fail loud at load
        AppConfig.model_validate({"escalation": {"alert_channels": ["sms"]}})


# --- E7-S5: Teams fallback -----------------------------------------------------

def test_dispatch_falls_through_to_teams_when_openwa_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "fb.db")
    res = _tick_with_one_alert()
    persist_tick_state(res, store=store, now=NOW)
    openwa = FakeAdapter("failed", name="openwa")
    teams = FakeAdapter("sent", name="teams")
    sent = dispatch_alerts(res, store=store, alert_adapters=[openwa, teams], now=NOW, dry_run=False)
    assert sent == 1 and openwa.calls == 1 and teams.calls == 1  # fell through to Teams


def test_alert_channels_accepts_openwa_and_teams() -> None:
    cfg = AppConfig.model_validate({"escalation": {"alert_channels": ["openwa", "teams"]}})
    assert cfg.escalation.alert_channels == ["openwa", "teams"]


def test_build_alert_adapters_wires_teams() -> None:
    from nagbot.channels.teams import TeamsAdapter
    from nagbot.run import build_alert_adapters

    cfg = _runtime(enabled=True)
    cfg.app.escalation.alert_channels[:] = ["openwa", "teams"]
    adapters = build_alert_adapters(cfg, renderer=None)
    assert [a.name for a in adapters] == ["openwa", "teams"]
    assert isinstance(adapters[1], TeamsAdapter)


def test_openwa_from_config_uses_alert_timeout() -> None:
    from nagbot.channels.openwa import OpenWaAdapter

    cfg = _runtime(enabled=True)
    cfg.app.escalation.alert_send_timeout = 7
    adapter = OpenWaAdapter.from_config(cfg)
    assert adapter._http.timeout.read == 7  # hung OpenWA fails fast → Teams fallback


def test_dispatch_both_channels_fail_no_persist(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "bf.db")
    res = _tick_with_one_alert()
    persist_tick_state(res, store=store, now=NOW)
    o, t = FakeAdapter("failed", name="openwa"), FakeAdapter("failed", name="teams")
    sent = dispatch_alerts(res, store=store, alert_adapters=[o, t], now=NOW, dry_run=False)
    assert sent == 0 and o.calls == 1 and t.calls == 1
    # anchor stays (open), rung not notified → retries next tick
    assert store.active_p0_escalations()[0].last_notified_at is None


def test_dispatch_stops_at_first_sent_channel(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "ord.db")
    res = _tick_with_one_alert()
    first, second = FakeAdapter("sent", name="teams"), FakeAdapter("sent", name="openwa")
    sent = dispatch_alerts(res, store=store, alert_adapters=[first, second], now=NOW, dry_run=False)
    assert sent == 1 and first.calls == 1 and second.calls == 0  # order honored, stop on first sent


# --- E7-S6: transparency-notice compliance gate --------------------------------

def test_no_escalation_without_transparency_notice(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "tn.db")
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True, notice=False), store, lambda: _FakeGlpi([tk(1)]),
        dry_run=False, now=NOW, alert_adapters=[adapter],
    )
    assert sent == 0 and adapter.calls == 0
    assert store.active_p0_escalations() == []  # nothing paged, nothing written


def test_escalates_when_notice_given(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = Store(tmp_path / "tn2.db")
    adapter = FakeAdapter("sent")
    sent = execute_escalation_run(
        _runtime(enabled=True, notice=True), store, lambda: _FakeGlpi([tk(1)]),
        dry_run=False, now=NOW, alert_adapters=[adapter],
    )
    assert sent == 1 and len(store.active_p0_escalations()) == 1


def test_runbook_has_notice_and_golive_steps() -> None:
    from pathlib import Path as _P
    text = _P("docs/e7-escalation-runbook.md").read_text()
    assert "transparency_notice_given" in text
    assert "5 or 6" in text and "OPENWA_WEBHOOK_SECRET" in text
