from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from nagbot.engine.aging import SlaStatus, business_days_between, compute_sla_status

GYE = ZoneInfo("America/Guayaquil")  # UTC-5, no DST
NO_HOLIDAYS: frozenset = frozenset()


def gye(y: int, mo: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=GYE)


# July 2026: Wed 1, Thu 2, Fri 3, Sat 4, Sun 5, Mon 6, Tue 7, Wed 8, Thu 9 ...
@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # same business day, half a day
        (gye(2026, 7, 8, 6), gye(2026, 7, 8, 18), 0.5),
        # one full business day
        (gye(2026, 7, 7, 0), gye(2026, 7, 8, 0), 1.0),
        # Friday 17:00 -> Monday 09:00 spans a weekend: 7h Friday + 9h Monday
        (gye(2026, 7, 3, 17), gye(2026, 7, 6, 9), (7 + 9) / 24),
        # full week Mon..Mon = 5 business days
        (gye(2026, 7, 6, 0), gye(2026, 7, 13, 0), 5.0),
        # entirely inside a weekend
        (gye(2026, 7, 4, 10), gye(2026, 7, 5, 20), 0.0),
        # end before start clamps to zero
        (gye(2026, 7, 8, 12), gye(2026, 7, 8, 6), 0.0),
    ],
)
def test_business_days_between(start: datetime, end: datetime, expected: float) -> None:
    assert business_days_between(start, end, GYE, NO_HOLIDAYS) == pytest.approx(expected)


def test_holiday_contributes_nothing() -> None:
    holidays = frozenset({date(2026, 7, 7)})  # declare Tue 7th a holiday
    got = business_days_between(gye(2026, 7, 6, 0), gye(2026, 7, 9, 0), GYE, holidays)
    assert got == pytest.approx(2.0)  # Mon + Wed only


def test_tz_matters_for_weekend_boundaries() -> None:
    # 2026-07-04 02:00 UTC is still Friday 21:00 in Guayaquil — counts toward Friday.
    start = datetime(2026, 7, 3, 21, 0, tzinfo=UTC)  # Fri 16:00 GYE
    end = datetime(2026, 7, 4, 2, 0, tzinfo=UTC)  # Fri 21:00 GYE
    assert business_days_between(start, end, GYE, NO_HOLIDAYS) == pytest.approx(5 / 24)


NOW = gye(2026, 7, 9, 8, 0)


@pytest.mark.parametrize(
    ("ttr", "expected"),
    [
        (None, SlaStatus.NO_SLA),
        (gye(2026, 7, 20, 8), SlaStatus.OK),
        (gye(2026, 7, 9, 20), SlaStatus.DUE_SOON),  # 12h away
        (gye(2026, 7, 10, 8), SlaStatus.DUE_SOON),  # exactly 24h away
        (gye(2026, 7, 9, 8), SlaStatus.BREACHED),  # exactly now
        (gye(2026, 7, 1, 8), SlaStatus.BREACHED),
    ],
)
def test_sla_status(ttr: datetime | None, expected: SlaStatus) -> None:
    assert compute_sla_status(ttr, NOW, due_soon_hours=24) is expected
