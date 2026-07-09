# E3-S3: Ops dashboard + ticket history

Status: Done

## Story
As the operator, I want to audit every run and every send, and see any ticket's full nag
history, so that "did Juan get nagged about #4821?" takes ten seconds to answer.

## Context
After E3-S2. Reads recent_runs/recent_sends/ticket_history (E2-S3).

## Acceptance Criteria
- AC1: `GET /ops`: run history table (id, trigger, dry-run badge, status, counts, error) + send log (time, kind, channel, recipient, cc, status, detail), newest first, limit 200.
- AC2: Send log filterable by channel and status via query params; dry_run rows visibly badged.
- AC3: Ownership warnings from the latest run (unmapped techs/groups) shown as a callout.
- AC4: `GET /tickets/{id}`: snapshot timeline (per run: tier, age, stale, owner) + every send that included this ticket + current snooze state.

## Tasks
- [x] Store: recent_runs/recent_sends filters, ticket_history join, run warnings persistence (add `warnings` JSON column to runs via migration 002) — AC1..AC4
- [x] web/templates/ops.html.j2, ticket.html.j2 — AC1..AC4
- [x] routes — AC1, AC4
- [x] tests — AC1..AC4

## Dev Notes
send_log.ticket_ids JSON → history lookup uses `EXISTS (SELECT 1 FROM json_each(...))`.
Filters as plain `<select>` + GET form, no JS. Migration 002 shows the migration runner
actually running >1 migration.

## Testing
Seed runs+sends; filter combinations; ticket page for id present in two runs and one
send; unknown ticket id → 404 page.

## Dev Agent Record
- Migration 002 (`runs.warnings` JSON) proves the runner handles >1 migration; the idempotency test now derives expected versions from len(MIGRATIONS) instead of hardcoding.
- run.py now persists ownership warnings via finish_run; /ops shows the latest run's warnings as the "unmapped owners" callout with a config fix hint.
- Ticket page includes the snooze/unsnooze forms (markup only — POST handlers land in E3-S4 as planned); snooze-inclusive semantics documented in the form label per E2-S3's decision.
- 404 for unknown tickets renders a friendly page, not bare JSON.

## QA Results
- AC1 ✅ `test_ops_dashboard_lists_runs_and_sends` (runs table with DRY-RUN badge + ok status, send log rows).
- AC2 ✅ `test_ops_send_log_filters` (channel=teams and status=sent GET filters).
- AC3 ✅ warnings callout asserted ("Unmapped owners" + 'ghost').
- AC4 ✅ `test_ticket_history_page` (snapshot timeline + escalation send + snooze form), `test_unknown_ticket_404`.
- Suite: ruff/mypy clean, 98 passed. **Gate: PASS**
