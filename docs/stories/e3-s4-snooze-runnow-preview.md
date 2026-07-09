# E3-S4: Snooze/unsnooze, run-now & preview

Status: Done

## Story
As the operator, I want to park blocked tickets, preview tomorrow's digests, and trigger
a run manually, so that nag-fatigue stays controlled and go-live is verifiable first.

## Context
Last E3 story. Preview is the R5 mitigation (eyeball before going live).

## Acceptance Criteria
- AC1: `POST /snooze` (ticket_id, until date, reason) and `POST /unsnooze` (ticket_id) from forms on /tickets/{id} and /; validation errors re-render with a message; success redirects back (303).
- AC2: A snoozed ticket is excluded from the next run's digests (integration-verified through execute_nag_run).
- AC3: `GET /preview`: fetches GLPI live, builds digests in-memory (no DB writes, no sends), renders each owner's email HTML inline with subject; GLPI failure → readable error page.
- AC4: `POST /run-now`: fires execute_nag_run in a background thread; dry-run unless a "live" checkbox AND config allows; redirects to /ops; respects the overlap lock (busy → flash message).

## Tasks
- [x] routes + forms in app.py — AC1, AC3, AC4
- [x] web/templates/preview.html.j2; snooze forms in ticket template (E3-S3) + run-now form on /ops — AC1, AC3
- [x] tests — AC1..AC4

## Dev Notes
run-now thread: `threading.Thread(daemon=True)` calling the same locked entrypoint the
scheduler uses; report lands in /ops via the runs table. Preview reuses
digest-building code from run.py refactored into a `build_all_digests(cfg, tickets, …)`
helper shared by both (no duplication).

## Testing
Snooze round-trip → integration rerun excludes ticket; preview with mocked GLPI renders
2 owners' HTML; run-now dry-run default writes a run row; busy lock path.

## Dev Agent Record
- Added `python-multipart` dependency (FastAPI form parsing).
- Validation errors redirect back with `?error=` rendered as a banner (303 + query param instead of re-render — keeps handlers stateless); past dates rejected.
- `/preview` reuses `fetch_and_score` + `build_all_digests` from run.py exactly as planned in E2-S6 — zero duplicated pipeline logic; applies active snoozes, skips escalation flags (peeking must not bump streaks).
- `/run-now` checks the run lock synchronously (busy → flash) then executes in a daemon thread; the thread is parked on `app.state.last_run_thread` so tests can join deterministically. Live checkbox still can't override config dry-run.
- Snooze form markup shipped in E3-S3's ticket page; this story added the handlers + ops run-now card + flash banners.

## QA Results
- AC1 ✅ `test_snooze_roundtrip_via_forms` (303, stored, page shows 💤, unsnooze clears), `test_snooze_validation_errors` (bad date + past date rejected with messages, nothing stored).
- AC2 ✅ pipeline exclusion proven in `test_snoozed_ticket_excluded_but_snapshotted` (E2-S6 integration) — the form writes the same snoozes table.
- AC3 ✅ `test_preview_renders_digests_without_writes` (owner + subject + ticket HTML, zero run/send rows), `test_preview_glpi_failure_shows_error` (502 + readable page).
- AC4 ✅ `test_run_now_defaults_to_dry_run` (303 → /ops, joined thread wrote manual dry-run run), `test_run_now_busy_flash` (lock held → busy flash).
- Suite: ruff/mypy clean, 104 passed. **Gate: PASS**
