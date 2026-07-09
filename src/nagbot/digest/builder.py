"""View-models for per-owner digests and the manager rollup."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from nagbot.engine.ownership import Owner, ScoredTicket, sort_scored
from nagbot.engine.tiers import TIER_ORDER, Tier
from nagbot.store.repo import SnapshotRow


@dataclass(frozen=True)
class Digest:
    owner: Owner
    generated_at: datetime
    tickets: list[ScoredTicket]  # worst tier first, then oldest
    counts: dict[Tier, int]
    escalated: list[ScoredTicket] = field(default_factory=list)

    @property
    def ticket_ids(self) -> list[int]:
        return [s.ticket.id for s in self.tickets]

    @property
    def breached_count(self) -> int:
        return sum(1 for s in self.tickets if s.metrics.sla_status == "breached")

    @property
    def oldest(self) -> ScoredTicket | None:
        return max(self.tickets, key=lambda s: s.metrics.age_bd, default=None)

    @property
    def has_sla_tickets(self) -> bool:
        return any(s.metrics.sla_due is not None for s in self.tickets)


@dataclass(frozen=True)
class PersonWip:
    owner_key: str
    owner_name: str
    total: int
    counts: dict[Tier, int]
    oldest_age_bd: float
    worst_stale_bd: float


@dataclass(frozen=True)
class Rollup:
    generated_at: datetime
    total_open: int
    distribution: dict[Tier, int]
    per_person: list[PersonWip]  # worst first
    leaderboard: list[SnapshotRow]  # top N oldest/stalest


def _tier_counts(tiers: list[Tier]) -> dict[Tier, int]:
    return {tier: sum(1 for t in tiers if t is tier) for tier in Tier}


def build_digests(
    grouped: dict[Owner, list[ScoredTicket]],
    *,
    escalated_ids: set[int],
    now: datetime,
) -> list[Digest]:
    """One digest per owner; owners with zero tickets get none (no empty nags)."""
    digests = []
    for owner, tickets in grouped.items():
        if not tickets:
            continue
        ordered = sort_scored(tickets)
        digests.append(
            Digest(
                owner=owner,
                generated_at=now,
                tickets=ordered,
                counts=_tier_counts([s.tier for s in ordered]),
                escalated=[s for s in ordered if s.ticket.id in escalated_ids],
            )
        )
    # deterministic order: worst owners first (most on-fire, then most tickets)
    digests.sort(
        key=lambda d: (-d.counts[Tier.ON_FIRE], -d.counts[Tier.HOT], -len(d.tickets))
    )
    return digests


def build_rollup(
    snapshots: list[SnapshotRow], *, now: datetime, leaderboard_size: int = 10
) -> Rollup:
    by_person: dict[str, list[SnapshotRow]] = {}
    for snap in snapshots:
        by_person.setdefault(snap.owner_key, []).append(snap)

    per_person = [
        PersonWip(
            owner_key=key,
            owner_name=rows[0].owner_name or key,
            total=len(rows),
            counts=_tier_counts([Tier(r.tier) for r in rows]),
            oldest_age_bd=max(r.age_bd for r in rows),
            worst_stale_bd=max(r.stale_bd for r in rows),
        )
        for key, rows in by_person.items()
    ]
    per_person.sort(
        key=lambda p: (-p.counts[Tier.ON_FIRE], -p.counts[Tier.HOT], -p.total)
    )

    leaderboard = sorted(
        snapshots, key=lambda s: (TIER_ORDER[Tier(s.tier)], -s.stale_bd, -s.age_bd)
    )[:leaderboard_size]

    return Rollup(
        generated_at=now,
        total_open=len(snapshots),
        distribution=_tier_counts([Tier(s.tier) for s in snapshots]),
        per_person=per_person,
        leaderboard=leaderboard,
    )
