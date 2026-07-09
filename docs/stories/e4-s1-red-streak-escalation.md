# E4-S1: Red-streak escalation (manager CC)

Status: Draft

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
- [ ] Verify/extend bump_red_streaks semantics per AC1/AC2 with multi-day tests
- [ ] Digest/renderer escalation marker — AC3
- [ ] /ops escalations section — AC4

## Dev Notes
All hooks exist; this story is mostly semantics tests + UI surfacing. Confirmed with
user: business-day (run-day) counting, not calendar.

## Testing
Simulated 10-run sequence: red/red/red→CC, stays red→no second CC, green→reset,
red×3→CC again; weekend gap tolerated.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
