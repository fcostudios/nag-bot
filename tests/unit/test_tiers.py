import pytest

from nagbot.config import Thresholds
from nagbot.engine.aging import SlaStatus, TicketMetrics
from nagbot.engine.tiers import TIER_ORDER, Tier, classify

TH = Thresholds()  # defaults: aging 2, hot 5, on_fire 7


def metrics(
    stale_bd: float = 0.0, sla: SlaStatus = SlaStatus.NO_SLA, age_bd: float = 10.0
) -> TicketMetrics:
    return TicketMetrics(age_bd=age_bd, stale_bd=stale_bd, sla_status=sla, sla_due=None)


@pytest.mark.parametrize(
    ("stale_bd", "sla", "expected"),
    [
        (0.5, SlaStatus.NO_SLA, Tier.FRESH),
        (1.99, SlaStatus.OK, Tier.FRESH),
        (2.0, SlaStatus.NO_SLA, Tier.AGING),  # boundary -> higher tier
        (4.9, SlaStatus.NO_SLA, Tier.AGING),
        (5.0, SlaStatus.NO_SLA, Tier.HOT),  # boundary
        (0.1, SlaStatus.DUE_SOON, Tier.HOT),  # SLA due soon beats freshness
        (6.9, SlaStatus.OK, Tier.HOT),
        (7.0, SlaStatus.NO_SLA, Tier.ON_FIRE),  # boundary
        (0.003, SlaStatus.BREACHED, Tier.ON_FIRE),  # breach beats "updated 5 minutes ago"
        (12.0, SlaStatus.BREACHED, Tier.ON_FIRE),
    ],
)
def test_classify(stale_bd: float, sla: SlaStatus, expected: Tier) -> None:
    assert classify(metrics(stale_bd, sla), TH) is expected


def test_thresholds_come_from_config() -> None:
    strict = Thresholds(aging_stale_bd=0.5, hot_stale_bd=1, on_fire_stale_bd=2)
    assert classify(metrics(0.6), strict) is Tier.AGING
    assert classify(metrics(1.5), strict) is Tier.HOT
    assert classify(metrics(2.0), strict) is Tier.ON_FIRE


def test_tier_order_is_worst_first() -> None:
    ordered = sorted(Tier, key=lambda t: TIER_ORDER[t])
    assert ordered == [Tier.ON_FIRE, Tier.HOT, Tier.AGING, Tier.FRESH]
