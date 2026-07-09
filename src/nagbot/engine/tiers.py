"""Severity tiers. Thresholds come from config — never hardcode them here."""

from __future__ import annotations

from enum import StrEnum

from nagbot.config import Thresholds
from nagbot.engine.aging import SlaStatus, TicketMetrics


class Tier(StrEnum):
    ON_FIRE = "on_fire"  # 🔴
    HOT = "hot"  # 🟠
    AGING = "aging"  # 🟡
    FRESH = "fresh"  # 🟢


# Worst first — used everywhere tickets or owners are sorted by severity.
TIER_ORDER: dict[Tier, int] = {Tier.ON_FIRE: 0, Tier.HOT: 1, Tier.AGING: 2, Tier.FRESH: 3}

TIER_EMOJI: dict[Tier, str] = {
    Tier.ON_FIRE: "🔴",
    Tier.HOT: "🟠",
    Tier.AGING: "🟡",
    Tier.FRESH: "🟢",
}

TIER_LABEL: dict[Tier, str] = {
    Tier.ON_FIRE: "On fire",
    Tier.HOT: "Hot",
    Tier.AGING: "Aging",
    Tier.FRESH: "Fresh",
}


def classify(metrics: TicketMetrics, thresholds: Thresholds) -> Tier:
    if metrics.sla_status is SlaStatus.BREACHED or metrics.stale_bd >= thresholds.on_fire_stale_bd:
        return Tier.ON_FIRE
    if metrics.sla_status is SlaStatus.DUE_SOON or metrics.stale_bd >= thresholds.hot_stale_bd:
        return Tier.HOT
    if metrics.stale_bd >= thresholds.aging_stale_bd:
        return Tier.AGING
    return Tier.FRESH
