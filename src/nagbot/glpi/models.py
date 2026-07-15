"""Normalized GLPI entities. All datetimes are timezone-aware UTC."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

# GLPI ticket status ids (glpi_tickets.status)
STATUS_LABELS = {
    1: "New",
    2: "Processing (assigned)",
    3: "Processing (planned)",
    4: "Pending",
    5: "Solved",
    6: "Closed",
}


class Ticket(BaseModel):
    id: int
    title: str
    status: int
    date_opened: datetime
    date_mod: datetime
    time_to_resolve: datetime | None = None
    tech_names: list[str] = []
    group_names: list[str] = []
    url: str = ""
    # E7-S2 — severity fields for P0 detection (safe defaults; often unset in GLPI)
    priority: int = 0
    urgency: int = 0
    impact: int = 0
    category: str = ""

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, f"status {self.status}")


def parse_glpi_datetime(value: str | None, server_tz: ZoneInfo) -> datetime | None:
    """GLPI returns naive 'YYYY-MM-DD HH:MM:SS' strings in the server's local time."""
    if not value:
        return None
    naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=server_tz).astimezone(UTC)
