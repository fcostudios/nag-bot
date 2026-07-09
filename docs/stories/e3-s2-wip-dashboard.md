# E3-S2: Team WIP dashboard

Status: Draft

## Story
As the team, we want a live WIP/aging page we can keep open all day, so that aging is
visible continuously, not only at 08:00.

## Context
After E3-S1. Reads `latest_snapshot()` (E2-S3) — no live GLPI calls on page load.

## Acceptance Criteria
- AC1: `GET /` renders from the latest run's snapshots: total open + per-tier counts as a distribution bar, per-person table (WIP count, worst tier, oldest ticket age, stale-worst), oldest-tickets leaderboard (top 10, deep links to GLPI).
- AC2: Snoozed tickets shown with a 💤 marker (still WIP, visibly parked).
- AC3: Empty state (no runs yet) renders a friendly "no data — run the bot" page with a link to /ops.
- AC4: Page shows data freshness ("as of {run time}, run #{id}, DRY-RUN" badge when applicable).

## Tasks
- [ ] Store: latest_snapshot returns rows + run meta; per-person aggregation helper — AC1
- [ ] web/templates/wip.html.j2 — AC1..AC4
- [ ] route in app.py — AC1
- [ ] tests: seeded snapshots render; empty state — AC1, AC3

## Dev Notes
Aggregation in Python (rows are small), not SQL gymnastics. Tier colors from the shared
badge styles. Sort persons by worst tier then WIP desc — the "leaderboard nobody wants
to top" (spec §4).

## Testing
Seed two runs; assert newest wins; person ordering; leaderboard cap; snooze marker; empty DB.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
