# E4-S1: Red-streak escalation (manager CC)

Status: Done

## Story
As a team lead, I want tickets that stay 🔴 for N consecutive run-days to CC me
automatically, so that chronic stalls become my problem before the customer makes them so.

## Context
Later cycle. E2-S3 shipped `escalations` table + bump_red_streaks; E2-S5 shipped CC
plumbing; E2-S6 calls bump_red_streaks. This story hardens semantics + surfaces state.

## Acceptance Criteria
- AC1: Streak = consecutive *run-days* (business days, since cron is weekday-only); same-day repeat runs don't double-count; missed days don't reset (streak counts red observations, gap-tolerant to weekends).
- AC2: On crossing `escalation_red_days`, the owner's digest CCs the manager and a `kind='escalation'` send_log row is written; repeat CC only fires again after the ticket leaves red and re-streaks.
- AC3: Escalated tickets get a "manager CC'd" marker in email + dashboards.
- AC4: /ops shows current streaks (escalations table view).

## Tasks
- [x] Verify/extend bump_red_streaks semantics per AC1/AC2 with multi-day tests
- [x] Digest/renderer escalation marker (shipped E2-S4) + WIP leaderboard ⚠️ marker — AC3
- [x] /ops escalations section — AC4

## Dev Notes
All hooks exist; this story is mostly semantics tests + UI surfacing. Confirmed with
user: business-day (run-day) counting, not calendar.

## Testing
Simulated 10-run sequence: red/red/red→CC, stays red→no second CC, green→reset,
red×3→CC again; weekend gap tolerated.

## Dev Agent Record
- Core semantics were already shipped and tested in E2-S3/S6 (streak table, one bump per run_date, escalate-once stamp, reset on leaving red, snoozed tickets excluded from streaks). This story added the missing proofs and UI: weekend-gap test (Fri→Mon→Tue = 3 consecutive run-days), /ops "Escalation streaks" table (streak, first red, last red day, CC'd timestamp), ⚠️ marker on WIP leaderboard rows for escalated tickets.
- Email marker (manager-CC callout box) exists since E2-S4 and is covered by the email goldens.
- Decision reconfirmed: streaks count *run-days* (weekday cron), gap-tolerant across weekends/holidays because only distinct run_dates bump the counter.

## QA Results
- AC1 ✅ `test_red_streak_tolerates_weekend_gaps` (Fri/Mon/Tue → escalate day 3); same-day double-run no-op already covered by `test_red_streaks_escalate_once_and_reset`.
- AC2 ✅ escalate-exactly-once + re-streak cycle covered in store test; pipeline CC + `kind='escalation'` row covered by `test_escalation_ccs_manager_after_streak` (E2-S6).
- AC3 ✅ email callout in `email_digest.html` golden; WIP ⚠️ via `test_wip_marks_escalated_tickets`.
- AC4 ✅ `test_ops_shows_escalation_streaks` (+ hidden-when-empty case).
- Suite: ruff/mypy clean, 108 passed. **Gate: PASS**
