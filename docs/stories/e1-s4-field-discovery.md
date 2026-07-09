# E1-S4: Field discovery, cache & version check

Status: Done

## Story
As the nagbot, I want search-option uids discovered from the instance (with cache and
manual overrides), so that non-canonical GLPI installs still map fields correctly.

## Context
After E1-S3. Replaces the CANONICAL-only FieldMap with discovery → override → canonical
precedence. Store's `field_cache` table lands in E2-S3; until then cache lives behind an
injectable `CacheBackend` protocol with an in-memory default (wired to SQLite in E2-S3).

## Acceptance Criteria
- AC1: `FieldMap.discover(client, overrides, cache)` builds name→uid from `GET /listSearchOptions/Ticket` by matching `(table, field)` pairs; unmatched names fall back to canonical uids with a warning.
- AC2: YAML `glpi.field_ids` overrides beat discovery; discovery beats canonical.
- AC3: Discovery payload cached 24h (TTL respected; expiry refetches).
- AC4: Startup logs one warning when the instance reports GLPI 11.x (apirest.php deprecated) — via initSession response or `GET /` probe; never fatal.

## Tasks
- [x] fields.py: discovery matching, precedence, CacheBackend protocol + InMemoryCache — AC1..AC3
- [x] client.py: capture glpi version hint; log warning once — AC4 (landed in E1-S3)
- [x] tests/glpi/test_fields.py + listSearchOptions fixture — AC1..AC3
- [x] test for version warning — AC4 (in test_client.py)

## Dev Notes
listSearchOptions payload: `{"2": {"table":"glpi_tickets","field":"id",...}, ...}` (uid →
option dict; some keys non-numeric — skip those). Match table+field:
date_opened=(glpi_tickets,date), date_mod=(glpi_tickets,date_mod),
tech=(glpi_users,name) with users_id_tech joinparams when disambiguation needed,
group=(glpi_groups,completename|name), time_to_resolve=(glpi_tickets,time_to_resolve).

## Testing
Trimmed real-shaped listSearchOptions fixture; override precedence table; TTL test with
injected clock; GLPI-11 version string triggers exactly one warning.

## Dev Agent Record
- AC4 (GLPI-11 warning) was already implemented in E1-S3 via the `X-GLPI-Version` initSession header; no extra probe needed — recorded there, tested in test_client.py.
- Tech/group disambiguation uses `linkfield` (`users_id_tech`/`groups_id_tech`) since requester shares the (glpi_users, name) signature; canonical uid is the tie-break, first candidate the last resort.
- `group` signature accepts both `completename` and `name` (varies across GLPI versions).
- `fetch` CLI now discovers on every invocation (one-shot process, no cache); the scheduled pipeline gets the SQLite-backed cache in E2-S3.

## QA Results
- AC1 ✅ `test_discovery_matches_signatures`, `test_discovery_disambiguates_tech_by_linkfield` (moved uid 5→105 proves linkfield wins), `test_unmatched_falls_back_to_canonical` (warning asserted).
- AC2 ✅ `test_overrides_beat_discovery`.
- AC3 ✅ `test_cache_hit_skips_fetch_within_ttl` (23h), `test_cache_expires_after_ttl` (25h).
- AC4 ✅ `test_glpi11_version_warning` (test_client.py).
- Suite: ruff/mypy clean, 28 passed. **Gate: PASS**
