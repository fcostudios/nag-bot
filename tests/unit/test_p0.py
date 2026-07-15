"""E7-S2: configurable P0 detection rule (safe OR-of-AND evaluator) + config default."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from nagbot.config import AppConfig, EscalationCfg, P0Condition
from nagbot.engine.p0 import detect_p0s, is_p0
from nagbot.glpi.fields import FieldMap
from nagbot.glpi.models import Ticket

NOW = datetime(2026, 7, 15, tzinfo=UTC)


def tk(**kw: object) -> Ticket:
    base = dict(id=1, title="t", status=2, date_opened=NOW, date_mod=NOW)
    base.update(kw)
    return Ticket(**base)  # type: ignore[arg-type]


DEFAULT = EscalationCfg().p0_rule  # [[priority >= 5]]


def test_priority_rule_matches_5_and_6_not_3_4() -> None:
    assert is_p0(tk(priority=5), DEFAULT)
    assert is_p0(tk(priority=6), DEFAULT)
    assert not is_p0(tk(priority=3), DEFAULT)
    assert not is_p0(tk(priority=4), DEFAULT)


def test_and_within_group() -> None:
    rule = [[
        P0Condition(field="urgency", op=">=", value=4),
        P0Condition(field="impact", op=">=", value=4),
    ]]
    assert is_p0(tk(urgency=4, impact=5), rule)
    assert not is_p0(tk(urgency=4, impact=3), rule)  # AND: both required


def test_or_across_groups() -> None:
    rule = [
        [P0Condition(field="priority", op=">=", value=5)],
        [P0Condition(field="category", op="in", value=["SAP", "Bendo"])],
    ]
    assert is_p0(tk(priority=3, category="Bendo"), rule)  # 2nd group
    assert is_p0(tk(priority=5, category="other"), rule)  # 1st group
    assert not is_p0(tk(priority=3, category="other"), rule)


def test_in_operator_on_category() -> None:
    rule = [[P0Condition(field="category", op="in", value=["TECNOLOGIA > SAP"])]]
    assert is_p0(tk(category="TECNOLOGIA > SAP"), rule)
    assert not is_p0(tk(category="TECNOLOGIA > OTHER"), rule)


def test_empty_rule_matches_nothing() -> None:
    assert not is_p0(tk(priority=6), [])


def test_unknown_field_and_type_mismatch_return_false_not_raise() -> None:
    assert not is_p0(tk(priority=6), [[P0Condition(field="nonexistent", op=">=", value=5)]])
    # ">=" against a str category must not raise
    assert not is_p0(tk(category="x"), [[P0Condition(field="category", op=">=", value=5)]])


def test_detect_p0s_filters() -> None:
    tickets = [tk(id=1, priority=3), tk(id=2, priority=5), tk(id=3, priority=6)]
    ids = [t.id for t in detect_p0s(tickets, DEFAULT)]
    assert ids == [2, 3]


def test_config_default_rule_is_priority_ge_5() -> None:
    cfg = EscalationCfg()
    assert cfg.enabled is False
    assert cfg.p0_rule == [[P0Condition(field="priority", op=">=", value=5)]]


def test_appconfig_loads_without_escalation_key() -> None:
    cfg = AppConfig.model_validate({"owners": {}})
    assert cfg.escalation.enabled is False
    assert is_p0(tk(priority=5), cfg.escalation.p0_rule)


def test_to_ticket_parses_priority_urgency_impact_category() -> None:
    fm = FieldMap()  # canonical uids: priority=3, urgency=10, impact=11, category=7
    row = {
        "2": 42, "1": "SAP down", "12": 2,
        "15": "2026-07-01 09:00:00", "19": "2026-07-07 15:30:00",
        "3": 6, "10": 5, "11": 5, "7": "TECNOLOGIA > SAP",
    }
    t = fm.to_ticket(row, server_tz=ZoneInfo("America/Guayaquil"), web_base="https://g")
    assert (t.priority, t.urgency, t.impact) == (6, 5, 5)
    assert t.category == "TECNOLOGIA > SAP"
    assert is_p0(t, DEFAULT)  # priority 6 → P0

