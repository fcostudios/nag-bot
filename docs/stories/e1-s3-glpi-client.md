# E1-S3: GLPI session + ticket search

Status: Draft

## Story
As the nagbot, I want a GLPI REST client with session lifecycle, pagination and retries,
so that every run reliably reads the full open-ticket list without hand-holding.

## Context
After E1-S2 (config supplies base_url/tokens/page_size/server_timezone). Uses canonical
hardcoded field uids until E1-S4 adds discovery.

## Acceptance Criteria
- AC1: `GlpiClient` as context manager: `__enter__` POSTs `/initSession` (App-Token header + `Authorization: user_token …`), `__exit__` GETs `/killSession` best-effort.
- AC2: `search_open_tickets()` queries `/search/Ticket` with `criteria[0]` field 12 equals `notold`, forcedisplay for id/title/status/date_opened/date_mod/tech/group/time_to_resolve, and paginates: 206 + Content-Range → next `range`, 200 → stop; result spans all pages.
- AC3: Transport errors/5xx/429 retried up to 3 attempts with backoff; `ERROR_SESSION_TOKEN_INVALID` body triggers one re-initSession + replay.
- AC4: Rows normalize to `Ticket` (aware UTC datetimes from `glpi.server_timezone`; multi-assignee cells split; `url` = `{web_base}/front/ticket.form.php?id={id}`).
- AC5: `python -m nagbot fetch --json` prints normalized tickets as JSON (manual verification path against the real instance).

## Tasks
- [ ] src/nagbot/glpi/models.py: Ticket — AC4
- [ ] src/nagbot/glpi/client.py: GlpiClient (_request with retry/re-auth, initSession/killSession, search_open_tickets) — AC1..AC3
- [ ] src/nagbot/glpi/fields.py: FieldMap with CANONICAL defaults + to_ticket(row) (discovery added in E1-S4) — AC2, AC4
- [ ] main.py: `fetch --json` subcommand — AC5
- [ ] tests/glpi/test_client.py + fixtures — AC1..AC4

## Dev Notes
httpx.Client injectable for respx. Canonical uids: id 2, title 1, status 12, date_opened
15, date_mod 19, tech 5, group 8, time_to_resolve 18. Search rows key by uid string:
`{"2": 4821, "1": "…", "5": "jdoe" | ["jdoe","asmith"]}`. GLPI datetimes are naive
`"YYYY-MM-DD HH:MM:SS"` in server tz. `web_base` derived from base_url minus
`/apirest.php`. Page size from config (default 100). Backoff 1s/2s (sleep injectable).

## Testing
respx fixtures: initSession 200; search 206 (`Content-Range: 0-1/3`) then 200; 500→200
retry; 401 `ERROR_SESSION_TOKEN_INVALID` → re-auth replay; multi-assignee row; naive
datetime conversion assert.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
