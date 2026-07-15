from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from nagbot.glpi.fields import CANONICAL, FieldMap, InMemoryCache

NOW = datetime(2026, 7, 9, 13, 0, tzinfo=UTC)

# Trimmed listSearchOptions/Ticket payload with realistic shape: option uid -> dict,
# plus a non-numeric key GLPI includes ("common") that must be skipped.
OPTIONS: dict[str, Any] = {
    "common": "Characteristics",
    "1": {"table": "glpi_tickets", "field": "name", "name": "Title"},
    "2": {"table": "glpi_tickets", "field": "id", "name": "ID"},
    "12": {"table": "glpi_tickets", "field": "status", "name": "Status"},
    "15": {"table": "glpi_tickets", "field": "date", "name": "Opening date"},
    "19": {"table": "glpi_tickets", "field": "date_mod", "name": "Last update"},
    "18": {"table": "glpi_tickets", "field": "time_to_resolve", "name": "Time to resolve"},
    # requester vs technician: same (table, field), disambiguated by linkfield
    "4": {"table": "glpi_users", "field": "name", "linkfield": "users_id", "name": "Requester"},
    "5": {
        "table": "glpi_users",
        "field": "name",
        "linkfield": "users_id_tech",
        "name": "Technician",
    },
    "8": {
        "table": "glpi_groups",
        "field": "completename",
        "linkfield": "groups_id_tech",
        "name": "Technician group",
    },
}


class FakeClient:
    def __init__(self, options: dict[str, Any] | None = None) -> None:
        self.options = options if options is not None else OPTIONS
        self.calls = 0

    def list_search_options(self, itemtype: str = "Ticket") -> dict[str, Any]:
        self.calls += 1
        return self.options


def test_discovery_matches_signatures() -> None:
    fm = FieldMap.discover(FakeClient(), now=NOW)  # type: ignore[arg-type]
    assert fm.ids == CANONICAL  # this fixture mirrors a stock install


def test_discovery_finds_p0_fields_from_options() -> None:
    # E7-S2: prove the 4 new fields resolve from listSearchOptions (not just the
    # canonical fallback) — give them NON-canonical uids so only real discovery wins.
    options = dict(OPTIONS)
    options["203"] = {"table": "glpi_tickets", "field": "priority", "name": "Priority"}
    options["210"] = {"table": "glpi_tickets", "field": "urgency", "name": "Urgency"}
    options["211"] = {"table": "glpi_tickets", "field": "impact", "name": "Impact"}
    options["207"] = {"table": "glpi_itilcategories", "field": "completename", "name": "Category"}
    fm = FieldMap.discover(FakeClient(options), now=NOW)  # type: ignore[arg-type]
    assert fm.ids["priority"] == 203
    assert fm.ids["urgency"] == 210
    assert fm.ids["impact"] == 211
    assert fm.ids["category"] == 207


def test_discovery_disambiguates_tech_by_linkfield() -> None:
    # swap uids so canonical fallback can't accidentally win
    options = dict(OPTIONS)
    options["105"] = options.pop("5")
    fm = FieldMap.discover(FakeClient(options), now=NOW)  # type: ignore[arg-type]
    assert fm.ids["tech"] == 105


def test_overrides_beat_discovery() -> None:
    fm = FieldMap.discover(
        FakeClient(),  # type: ignore[arg-type]
        overrides={"time_to_resolve": 218},
        now=NOW,
    )
    assert fm.ids["time_to_resolve"] == 218
    assert fm.ids["id"] == 2


def test_unmatched_falls_back_to_canonical(caplog: pytest.LogCaptureFixture) -> None:
    options = {k: v for k, v in OPTIONS.items() if k != "18"}  # no SLA option on instance
    with caplog.at_level("WARNING"):
        fm = FieldMap.discover(FakeClient(options), now=NOW)  # type: ignore[arg-type]
    assert fm.ids["time_to_resolve"] == CANONICAL["time_to_resolve"]
    assert any("time_to_resolve" in r.message for r in caplog.records)


def test_cache_hit_skips_fetch_within_ttl() -> None:
    cache = InMemoryCache()
    client = FakeClient()
    FieldMap.discover(client, cache=cache, now=NOW)  # type: ignore[arg-type]
    FieldMap.discover(client, cache=cache, now=NOW + timedelta(hours=23))  # type: ignore[arg-type]
    assert client.calls == 1


def test_cache_expires_after_ttl() -> None:
    cache = InMemoryCache()
    client = FakeClient()
    FieldMap.discover(client, cache=cache, now=NOW)  # type: ignore[arg-type]
    FieldMap.discover(client, cache=cache, now=NOW + timedelta(hours=25))  # type: ignore[arg-type]
    assert client.calls == 2
