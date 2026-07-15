"""Mapping of logical ticket fields to GLPI search-option uids.

Precedence: YAML overrides > discovered via listSearchOptions > canonical defaults.
Discovery is cached (24h TTL) behind a small CacheBackend protocol; the SQLite
backend arrives with the store in E2-S3.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol
from zoneinfo import ZoneInfo

from nagbot.glpi.models import Ticket, parse_glpi_datetime

if TYPE_CHECKING:
    from nagbot.glpi.client import GlpiClient

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
    "priority": 3,
    "urgency": 10,
    "impact": 11,
    "category": 7,
}

# (table, field) signatures used to recognize each logical field in listSearchOptions.
_SIGNATURES: dict[str, tuple[str, str]] = {
    "id": ("glpi_tickets", "id"),
    "title": ("glpi_tickets", "name"),
    "status": ("glpi_tickets", "status"),
    "date_opened": ("glpi_tickets", "date"),
    "date_mod": ("glpi_tickets", "date_mod"),
    "tech": ("glpi_users", "name"),
    "group": ("glpi_groups", "completename"),
    "time_to_resolve": ("glpi_tickets", "time_to_resolve"),
    # E7-S2 — P0-detection fields
    "priority": ("glpi_tickets", "priority"),
    "urgency": ("glpi_tickets", "urgency"),
    "impact": ("glpi_tickets", "impact"),
    "category": ("glpi_itilcategories", "completename"),
}

# Disambiguators for signatures that match several options (requester vs technician...).
_LINKFIELD_PREFERENCE: dict[str, str] = {
    "tech": "users_id_tech",
    "group": "groups_id_tech",
}

CACHE_TTL = timedelta(hours=24)


class CacheBackend(Protocol):
    def get(self, key: str) -> tuple[str, datetime] | None:
        """Return (payload, fetched_at) or None."""
        ...

    def put(self, key: str, payload: str, fetched_at: datetime) -> None: ...


class InMemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, datetime]] = {}

    def get(self, key: str) -> tuple[str, datetime] | None:
        return self._data.get(key)

    def put(self, key: str, payload: str, fetched_at: datetime) -> None:
        self._data[key] = (payload, fetched_at)


def _as_list(value: object) -> list[str]:
    """GLPI multi-valued cells arrive as a list, or one string joined with '$#$'."""
    if value is None:
        return []
    items = [str(v) for v in value] if isinstance(value, list) else str(value).split("$#$")
    return [s.strip() for s in items if s and str(s).strip() and str(s) != "0"]


def _match_options(options: dict[str, Any]) -> dict[str, int]:
    """Recognize logical fields in a listSearchOptions payload by (table, field)."""
    candidates: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for uid_str, opt in options.items():
        if not uid_str.isdigit() or not isinstance(opt, dict):
            continue  # skip non-option keys like "common"
        table, field = opt.get("table"), opt.get("field")
        for name, (sig_table, sig_field) in _SIGNATURES.items():
            if table == sig_table and (field == sig_field or (name == "group" and field == "name")):
                candidates.setdefault(name, []).append((int(uid_str), opt))

    discovered: dict[str, int] = {}
    for name, found in candidates.items():
        if len(found) == 1:
            discovered[name] = found[0][0]
            continue
        preferred_link = _LINKFIELD_PREFERENCE.get(name)
        by_link = [u for u, o in found if o.get("linkfield") == preferred_link]
        if by_link:
            discovered[name] = by_link[0]
        elif CANONICAL[name] in {u for u, _ in found}:
            discovered[name] = CANONICAL[name]
        else:
            discovered[name] = found[0][0]
    return discovered


@dataclass
class FieldMap:
    """name -> search-option uid, plus row normalization."""

    ids: dict[str, int]

    def __init__(self, ids: dict[str, int] | None = None) -> None:
        self.ids = {**CANONICAL, **(ids or {})}

    @classmethod
    def discover(
        cls,
        client: GlpiClient,
        *,
        overrides: dict[str, int] | None = None,
        cache: CacheBackend | None = None,
        now: datetime | None = None,
        itemtype: str = "Ticket",
    ) -> FieldMap:
        """Build a FieldMap from the instance's search options (cached, overridable)."""
        now = now or datetime.now(UTC)
        options: dict[str, Any] | None = None
        if cache is not None:
            hit = cache.get(itemtype)
            if hit is not None and now - hit[1] < CACHE_TTL:
                options = json.loads(hit[0])
        if options is None:
            options = client.list_search_options(itemtype)
            if cache is not None:
                cache.put(itemtype, json.dumps(options), now)

        discovered = _match_options(options)
        for name in _SIGNATURES:
            if name not in discovered:
                logger.warning(
                    "field %r not found in %s search options; using canonical uid %d",
                    name,
                    itemtype,
                    CANONICAL[name],
                )
        return cls({**discovered, **(overrides or {})})

    def forcedisplay_params(self) -> dict[str, int]:
        return {f"forcedisplay[{i}]": uid for i, uid in enumerate(dict.fromkeys(self.ids.values()))}

    def to_ticket(self, row: dict[str, object], *, server_tz: ZoneInfo, web_base: str) -> Ticket:
        def cell(name: str) -> object:
            return row.get(str(self.ids[name]))

        def cell_int(name: str) -> int:
            raw = cell(name)
            try:
                return int(str(raw)) if raw not in (None, "") else 0
            except (TypeError, ValueError):
                return 0

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
            priority=cell_int("priority"),
            urgency=cell_int("urgency"),
            impact=cell_int("impact"),
            category=str(cell("category") or ""),
        )
