from datetime import UTC, datetime

from nagbot.config import AppConfig
from nagbot.engine.aging import SlaStatus, TicketMetrics
from nagbot.engine.ownership import ScoredTicket, group_by_owner, resolve_owner
from nagbot.engine.tiers import Tier
from nagbot.glpi.models import Ticket

CFG = AppConfig.model_validate(
    {
        "owners": {
            "jdoe": {"name": "Juan Doe", "email": "jdoe@x.com", "manager": "boss@x.com"},
            "asmith": {"name": "Ana Smith", "email": "ana@x.com", "aliases": ["Ana Smith"]},
        },
        "groups": {"Networking": {"name": "Net Team", "email": "net@x.com"}},
        "fallback": {"email": "lead@x.com"},
    }
)


def ticket(tid: int, techs: list[str] | None = None, groups: list[str] | None = None) -> Ticket:
    return Ticket(
        id=tid,
        title=f"T{tid}",
        status=2,
        date_opened=datetime(2026, 7, tid, tzinfo=UTC),
        date_mod=datetime(2026, 7, 8, tzinfo=UTC),
        tech_names=techs or [],
        group_names=groups or [],
    )


def scored(t: Ticket, tier: Tier = Tier.FRESH) -> ScoredTicket:
    m = TicketMetrics(age_bd=1, stale_bd=0, sla_status=SlaStatus.NO_SLA, sla_due=None)
    return ScoredTicket(ticket=t, metrics=m, tier=tier)


def test_mapped_tech_wins() -> None:
    r = resolve_owner(ticket(1, techs=["jdoe"], groups=["Networking"]), CFG)
    assert r.owner.key == "tech:jdoe"
    assert r.owner.manager_email == "boss@x.com"
    assert r.warnings == []


def test_alias_matches_display_name() -> None:
    r = resolve_owner(ticket(2, techs=["Ana Smith"]), CFG)
    assert r.owner.key == "tech:asmith"


def test_unmapped_tech_falls_to_group_with_warning() -> None:
    r = resolve_owner(ticket(3, techs=["ghost"], groups=["Networking"]), CFG)
    assert r.owner.key == "group:Networking"
    assert any("'ghost'" in w for w in r.warnings)


def test_nothing_mapped_falls_back() -> None:
    r = resolve_owner(ticket(4, techs=["ghost"], groups=["Phantom"]), CFG)
    assert r.owner.key == "unassigned"
    assert r.owner.email == "lead@x.com"
    assert len(r.warnings) == 2


def test_group_by_owner_buckets_and_sorts() -> None:
    old_fire = scored(ticket(1, techs=["jdoe"]), Tier.ON_FIRE)
    new_fire = scored(ticket(5, techs=["jdoe"]), Tier.ON_FIRE)
    fresh = scored(ticket(3, techs=["jdoe"]), Tier.FRESH)
    other = scored(ticket(2, techs=["Ana Smith"]), Tier.AGING)
    buckets, warnings = group_by_owner([fresh, new_fire, other, old_fire], CFG)
    assert warnings == []
    keys = {o.key for o in buckets}
    assert keys == {"tech:jdoe", "tech:asmith"}
    jdoe = next(v for o, v in buckets.items() if o.key == "tech:jdoe")
    # worst tier first, then oldest
    assert [s.ticket.id for s in jdoe] == [1, 5, 3]


def test_owner_is_hashable_dict_key() -> None:
    r1 = resolve_owner(ticket(1, techs=["jdoe"]), CFG)
    r2 = resolve_owner(ticket(2, techs=["jdoe"]), CFG)
    assert r1.owner == r2.owner
    assert len({r1.owner, r2.owner}) == 1
