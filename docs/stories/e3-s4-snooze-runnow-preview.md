# E3-S4: Snooze/unsnooze, run-now & preview

Status: Draft

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
- [ ] routes + forms in app.py — AC1, AC3, AC4
- [ ] web/templates/preview.html.j2; snooze forms into ticket/wip templates — AC1, AC3
- [ ] tests — AC1..AC4

## Dev Notes
run-now thread: `threading.Thread(daemon=True)` calling the same locked entrypoint the
scheduler uses; report lands in /ops via the runs table. Preview reuses
digest-building code from run.py refactored into a `build_all_digests(cfg, tickets, …)`
helper shared by both (no duplication).

## Testing
Snooze round-trip → integration rerun excludes ticket; preview with mocked GLPI renders
2 owners' HTML; run-now dry-run default writes a run row; busy lock path.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
