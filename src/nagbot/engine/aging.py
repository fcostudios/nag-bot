"""Business-day aging and SLA math. Pure functions — no I/O, `now` always injected.

Business days are computed in the team's timezone: weekends and configured holidays
contribute nothing, partial days count fractionally (a ticket opened Friday 17:00 is
not "3 days old" on Monday 09:00 — it's ~0.67 business days old).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from nagbot.config import Thresholds
from nagbot.glpi.models import Ticket

_DAY_SECONDS = 86_400.0


class SlaStatus(StrEnum):
    NO_SLA = "no_sla"
    OK = "ok"
    DUE_SOON = "due_soon"
    BREACHED = "breached"


@dataclass(frozen=True)
class TicketMetrics:
    age_bd: float
    stale_bd: float
    sla_status: SlaStatus
    sla_due: datetime | None


def business_days_between(
    start: datetime,
    end: datetime,
    tz: ZoneInfo,
    holidays: frozenset,
) -> float:
    """Fractional business days between two aware datetimes, evaluated in ``tz``."""
    if end <= start:
        return 0.0
    start_local = start.astimezone(tz)
    end_local = end.astimezone(tz)
    total = 0.0
    day = start_local.date()
    while day <= end_local.date():
        if day.weekday() < 5 and day not in holidays:
            day_begin = datetime.combine(day, time.min, tzinfo=tz)
            day_end = day_begin + timedelta(days=1)
            overlap_begin = max(start_local, day_begin)
            overlap_end = min(end_local, day_end)
            if overlap_end > overlap_begin:
                total += (overlap_end - overlap_begin).total_seconds() / _DAY_SECONDS
        day += timedelta(days=1)
    return total


def compute_sla_status(
    time_to_resolve: datetime | None, now: datetime, due_soon_hours: float
) -> SlaStatus:
    if time_to_resolve is None:
        return SlaStatus.NO_SLA
    if now >= time_to_resolve:
        return SlaStatus.BREACHED
    if time_to_resolve - now <= timedelta(hours=due_soon_hours):
        return SlaStatus.DUE_SOON
    return SlaStatus.OK


def compute_metrics(
    ticket: Ticket,
    now: datetime,
    thresholds: Thresholds,
    tz: ZoneInfo,
    holidays: frozenset,
) -> TicketMetrics:
    return TicketMetrics(
        age_bd=business_days_between(ticket.date_opened, now, tz, holidays),
        stale_bd=business_days_between(ticket.date_mod, now, tz, holidays),
        sla_status=compute_sla_status(
            ticket.time_to_resolve, now, thresholds.sla_due_soon_hours
        ),
        sla_due=ticket.time_to_resolve,
    )
