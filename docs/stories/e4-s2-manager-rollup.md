# E4-S2: Monday manager rollup

Status: Draft

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
- [ ] run.py: real execute_rollup_run — AC1, AC2
- [ ] scheduler: wire rollup cron to it — AC2
- [ ] /ops rollup card — AC3
- [ ] golden already exists; add integration test — AC1, AC2

## Dev Notes
Rollup ranks by (worst tier, stale_bd desc). Uses latest_snapshot, no fresh GLPI fetch
(Monday 08:30 runs 30min after the digest run's snapshots).

## Testing
Integration: seeded snapshots → rollup sent to recipients, dry-run row; empty snapshots →
skipped with logged reason.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
