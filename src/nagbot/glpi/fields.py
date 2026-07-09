"""Mapping of logical ticket fields to GLPI search-option uids.

E1-S3 ships the canonical defaults; E1-S4 adds discovery via listSearchOptions,
caching, and YAML overrides.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from nagbot.glpi.models import Ticket, parse_glpi_datetime

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Canonical GLPI search-option uids for Ticket (stable across stock installs).
CANONICAL: dict[str, int] = {
    "id": 2,
    "title": 1,
    "status": 12,
    "date_opened": 15,
    "date_mod": 19,
    "tech": 5,
    "group": 8,
    "time_to_resolve": 18,
}


def _as_list(value: object) -> list[str]:
    """GLPI multi-valued cells arrive as a list, or one string joined with '$#$'."""
    if value is None:
        return []
    items = [str(v) for v in value] if isinstance(value, list) else str(value).split("$#$")
    return [s.strip() for s in items if s and str(s).strip() and str(s) != "0"]


class FieldMap:
    """name -> search-option uid, plus row normalization."""

    def __init__(self, ids: dict[str, int] | None = None) -> None:
        self.ids: dict[str, int] = {**CANONICAL, **(ids or {})}

    def forcedisplay_params(self) -> dict[str, int]:
        return {
            f"forcedisplay[{i}]": uid
            for i, uid in enumerate(dict.fromkeys(self.ids.values()))
        }

    def to_ticket(self, row: dict[str, object], *, server_tz: ZoneInfo, web_base: str) -> Ticket:
        def cell(name: str) -> object:
            return row.get(str(self.ids[name]))

        ticket_id = int(str(cell("id")))
        opened = parse_glpi_datetime(str(cell("date_opened") or "") or None, server_tz)
        mod = parse_glpi_datetime(str(cell("date_mod") or "") or None, server_tz)
        if opened is None or mod is None:
            raise ValueError(f"ticket {ticket_id}: missing date_opened/date_mod")
        ttr_raw = cell("time_to_resolve")
        return Ticket(
            id=ticket_id,
            title=str(cell("title") or f"(untitled #{ticket_id})"),
            status=int(str(cell("status") or 0)),
            date_opened=opened,
            date_mod=mod,
            time_to_resolve=parse_glpi_datetime(str(ttr_raw) if ttr_raw else None, server_tz),
            tech_names=_as_list(cell("tech")),
            group_names=_as_list(cell("group")),
            url=f"{web_base}/front/ticket.form.php?id={ticket_id}",
        )
