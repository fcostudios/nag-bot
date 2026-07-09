# E4-S2: Monday manager rollup

Status: Done

## Story
As a manager, I want a Monday summary of WIP per person, aging distribution and the
worst offenders, so that I see systemic rot without reading every daily digest.

## Context
Later cycle. Template + Rollup model shipped in E2-S4; rollup cron placeholder in E2-S6.

## Acceptance Criteria
- AC1: `execute_rollup_run` builds Rollup from the latest snapshots: per-person WIP + tier counts, distribution totals, top-10 oldest/stalest leaderboard.
- AC2: Sent via enabled adapters to `fallback.rollup_recipients` on `rollup_cron`; dry-run respected; send_log `kind='rollup'`.
- AC3: Rollup visible at /ops (last rollup card) — same data as the email.

## Tasks
- [x] run.py: real execute_rollup_run — AC1, AC2
- [x] scheduler: rollup cron already wired (E2-S6 make_jobs) — AC2
- [x] /ops rollup card + GET /rollup view — AC3
- [x] golden already exists; add integration test — AC1, AC2

## Dev Notes
Rollup ranks by (worst tier, stale_bd desc). Uses latest_snapshot, no fresh GLPI fetch
(Monday 08:30 runs 30min after the digest run's snapshots).

## Testing
Integration: seeded snapshots → rollup sent to recipients, dry-run row; empty snapshots →
skipped with logged reason.

## Dev Agent Record
- execute_rollup_run mirrors the digest pipeline's failure isolation (adapter crash → failed send row, run continues); leaderboard ticket ids recorded on the `kind='rollup'` send row for /tickets cross-linking.
- No snapshots → returns `skipped` without writing a run row (Monday before any digest run has ever completed).
- AC3 interpreted as: /ops card (recipients + last-sent status) linking to a dedicated `GET /rollup` page that renders the exact rollup HTML the email carries — same `build_rollup` + `rollup_html` path, so page and email cannot diverge.
- Store.recent_sends grew a `kind` filter for the last-rollup lookup.
- EmailAdapter.send_rollup was already implemented in E2-S5; scheduler wiring already in place from E2-S6 — this story just made execute_rollup_run real.

## QA Results
- AC1 ✅ `test_rollup_sends_to_recipients` (built from latest snapshots after a digest run; per-person + leaderboard content via rollup_html golden from E2-S4).
- AC2 ✅ same test: To = both rollup_recipients, subject "Weekly WIP rollup", kind='rollup' row status sent, run row trigger='rollup'; `test_rollup_respects_dry_run` (SMTP untouched, dry_run row); cron wiring asserted by `test_scheduler_registers_both_crons` (E2-S6).
- AC3 ✅ `test_rollup_view_renders`, `test_rollup_view_empty_state`, `test_ops_rollup_card` (last-sent badge).
- Edge ✅ `test_rollup_skips_without_snapshots`.
- Suite: ruff/mypy clean, 114 passed. **Gate: PASS**
