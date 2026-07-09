import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from tests.conftest import GoldenComparer

from nagbot.digest.builder import build_digests, build_rollup
from nagbot.digest.renderer import Renderer
from nagbot.engine.aging import SlaStatus, TicketMetrics
from nagbot.engine.ownership import Owner, ScoredTicket
from nagbot.engine.tiers import Tier
from nagbot.glpi.models import Ticket
from nagbot.store.repo import SnapshotRow

GYE = ZoneInfo("America/Guayaquil")
NOW = datetime(2026, 7, 9, 8, 0, tzinfo=GYE)

OWNER = Owner(
    key="tech:jdoe",
    kind="tech",
    display_name="Juan Doe",
    email="jdoe@example.com",
    manager_email="boss@example.com",
)


def scored(
    tid: int,
    tier: Tier,
    *,
    age: float,
    stale: float,
    sla: SlaStatus = SlaStatus.NO_SLA,
    sla_due: datetime | None = None,
    title: str | None = None,
) -> ScoredTicket:
    ticket = Ticket(
        id=tid,
        title=title or f"Sample ticket {tid}",
        status=2,
        date_opened=NOW - timedelta(days=age * 1.4),
        date_mod=NOW - timedelta(days=stale * 1.4),
        time_to_resolve=sla_due,
        url=f"https://glpi.example.com/front/ticket.form.php?id={tid}",
    )
    return ScoredTicket(
        ticket=ticket,
        metrics=TicketMetrics(age_bd=age, stale_bd=stale, sla_status=sla, sla_due=sla_due),
        tier=tier,
    )


def fixture_digest() -> "list":
    tickets = [
        scored(
            4821,
            Tier.ON_FIRE,
            age=12,
            stale=8,
            sla=SlaStatus.BREACHED,
            sla_due=NOW - timedelta(days=2),
            title="Printer on fire (literally)",
        ),
        scored(4890, Tier.ON_FIRE, age=9, stale=7.5),
        scored(
            4930,
            Tier.HOT,
            age=6,
            stale=5.2,
            sla=SlaStatus.DUE_SOON,
            sla_due=NOW + timedelta(hours=20),
        ),
        scored(4999, Tier.AGING, age=3, stale=2.5),
        scored(5012, Tier.FRESH, age=0.5, stale=0.2),
    ]
    return build_digests({OWNER: tickets}, escalated_ids={4821}, now=NOW)


def make_renderer() -> Renderer:
    return Renderer(GYE, glpi_web_base="https://glpi.example.com")


def test_digest_build_shape() -> None:
    (digest,) = fixture_digest()
    assert digest.ticket_ids == [4821, 4890, 4930, 4999, 5012]  # worst first, then oldest
    assert digest.counts[Tier.ON_FIRE] == 2
    assert [s.ticket.id for s in digest.escalated] == [4821]
    assert digest.breached_count == 1
    assert digest.has_sla_tickets


def test_email_subject() -> None:
    (digest,) = fixture_digest()
    assert (
        make_renderer().email_subject(digest)
        == "⏰ 5 open tickets — 1 OVERDUE, oldest 12d (please act)"
    )


def test_email_html_golden(golden: "GoldenComparer") -> None:
    (digest,) = fixture_digest()
    golden.check("email_digest.html", make_renderer().email_html(digest))


def test_email_text_golden(golden: "GoldenComparer") -> None:
    (digest,) = fixture_digest()
    golden.check("digest.txt", make_renderer().email_text(digest))


def test_teams_card_golden(golden: "GoldenComparer") -> None:
    (digest,) = fixture_digest()
    card = make_renderer().teams_card(digest)
    assert card["type"] == "AdaptiveCard" and card["version"] == "1.4"
    golden.check("teams_card.json", json.dumps(card, indent=2, ensure_ascii=False))


def snapshot(tid: int, owner: str, name: str, tier: str, age: float, stale: float) -> SnapshotRow:
    return SnapshotRow(
        run_id=1,
        ticket_id=tid,
        title=f"Sample ticket {tid}",
        status=2,
        date_opened=NOW.astimezone(UTC) - timedelta(days=age),
        date_mod=NOW.astimezone(UTC) - timedelta(days=stale),
        sla_due=None,
        owner_key=owner,
        owner_name=name,
        tier=tier,
        age_bd=age,
        stale_bd=stale,
        sla_status="no_sla",
    )


def test_rollup_golden(golden: "GoldenComparer") -> None:
    snaps = [
        snapshot(1, "tech:jdoe", "Juan Doe", "on_fire", 12, 8),
        snapshot(2, "tech:jdoe", "Juan Doe", "fresh", 1, 0.1),
        snapshot(3, "tech:asmith", "Ana Smith", "hot", 6, 5),
        snapshot(4, "group:net", "Net Team", "aging", 3, 2.5),
        snapshot(5, "tech:asmith", "Ana Smith", "aging", 4, 2.2),
    ]
    rollup = build_rollup(snaps, now=NOW)
    assert rollup.total_open == 5
    assert rollup.per_person[0].owner_key == "tech:jdoe"  # has the only on_fire
    assert rollup.leaderboard[0].ticket_id == 1
    renderer = make_renderer()
    assert renderer.rollup_subject(rollup) == "📊 Weekly WIP rollup — 5 open, 1 on fire"
    golden.check("manager_rollup.html", renderer.rollup_html(rollup))
