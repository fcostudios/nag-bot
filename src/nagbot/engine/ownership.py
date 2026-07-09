"""Resolve each ticket to exactly one responsible owner and group tickets per owner.

Chain: first assigned technician with a YAML mapping → first mapped assigned group →
configured fallback. Unmapped names generate warnings for the run report instead of
disappearing silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from nagbot.config import AppConfig, OwnerCfg
from nagbot.engine.aging import TicketMetrics
from nagbot.engine.tiers import TIER_ORDER, Tier
from nagbot.glpi.models import Ticket

UNASSIGNED_KEY = "unassigned"


@dataclass(frozen=True)
class Owner:
    key: str  # "tech:jdoe" | "group:Networking" | "unassigned"
    kind: Literal["tech", "group", "unassigned"]
    display_name: str
    email: str | None = None
    teams_id: str | None = None
    whatsapp: str | None = None
    manager_email: str | None = None


@dataclass(frozen=True)
class ScoredTicket:
    ticket: Ticket
    metrics: TicketMetrics
    tier: Tier


@dataclass
class OwnershipResult:
    owner: Owner
    warnings: list[str] = field(default_factory=list)


def _owner_from_cfg(key: str, kind: Literal["tech", "group"], cfg_entry: OwnerCfg) -> Owner:
    return Owner(
        key=f"{kind}:{key}",
        kind=kind,
        display_name=cfg_entry.name,
        email=cfg_entry.email,
        teams_id=cfg_entry.teams_id,
        whatsapp=cfg_entry.whatsapp,
        manager_email=cfg_entry.manager,
    )


def _find_owner_key(name: str, owners: dict[str, OwnerCfg]) -> str | None:
    """Match a GLPI-reported name against YAML keys (logins) or their aliases."""
    if name in owners:
        return name
    for key, entry in owners.items():
        if name in entry.aliases:
            return key
    return None


def fallback_owner(cfg: AppConfig) -> Owner:
    return Owner(
        key=UNASSIGNED_KEY,
        kind="unassigned",
        display_name="Unassigned / unmapped",
        email=cfg.fallback.email,
    )


def resolve_owner(ticket: Ticket, cfg: AppConfig) -> OwnershipResult:
    warnings: list[str] = []
    for tech in ticket.tech_names:
        key = _find_owner_key(tech, cfg.owners)
        if key is not None:
            return OwnershipResult(_owner_from_cfg(key, "tech", cfg.owners[key]), warnings)
        warnings.append(f"ticket #{ticket.id}: technician {tech!r} not in owner map")
    for group in ticket.group_names:
        key = _find_owner_key(group, cfg.groups)
        if key is not None:
            return OwnershipResult(_owner_from_cfg(key, "group", cfg.groups[key]), warnings)
        warnings.append(f"ticket #{ticket.id}: group {group!r} not in group map")
    return OwnershipResult(fallback_owner(cfg), warnings)


def sort_scored(tickets: list[ScoredTicket]) -> list[ScoredTicket]:
    """Worst tier first, then oldest first."""
    return sorted(tickets, key=lambda s: (TIER_ORDER[s.tier], s.ticket.date_opened))


def group_by_owner(
    scored: list[ScoredTicket], cfg: AppConfig
) -> tuple[dict[Owner, list[ScoredTicket]], list[str]]:
    buckets: dict[Owner, list[ScoredTicket]] = {}
    warnings: list[str] = []
    for st in scored:
        result = resolve_owner(st.ticket, cfg)
        warnings.extend(result.warnings)
        buckets.setdefault(result.owner, []).append(st)
    return {owner: sort_scored(items) for owner, items in buckets.items()}, warnings
