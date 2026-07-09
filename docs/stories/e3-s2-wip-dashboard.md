# E3-S2: Team WIP dashboard

Status: Done

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
- [x] Store: latest_snapshot returns rows + run meta (shipped E2-S3); aggregation reuses digest.builder.build_rollup — AC1
- [x] web/templates/wip.html.j2 — AC1..AC4
- [x] route in app.py — AC1
- [x] tests: seeded snapshots render; empty state — AC1, AC3

## Dev Notes
Aggregation in Python (rows are small), not SQL gymnastics. Tier colors from the shared
badge styles. Sort persons by worst tier then WIP desc — the "leaderboard nobody wants
to top" (spec §4).

## Testing
Seed two runs; assert newest wins; person ordering; leaderboard cap; snooze marker; empty DB.

## Dev Agent Record
- No new aggregation code: the page reuses `build_rollup` (E2-S4) — per-person WIP, distribution and leaderboard are the same view-model the E4 manager email will use, so web and email can never disagree.
- Leaderboard ticket ids link to `/tickets/{id}` (nag history, E3-S3) while titles deep-link to GLPI — two link targets per row, each doing its one job.
- Distribution bar is pure CSS flex (no JS, no chart lib).

## QA Results
- AC1 ✅ `test_wip_dashboard_renders` (totals, per-person worst-first ordering, leaderboard deep link); `test_wip_newest_run_wins` (only latest run's data).
- AC2 ✅ 💤 marker asserted for the snoozed snapshot.
- AC3 ✅ `test_wip_empty_state` ("No data yet" + /ops pointer).
- AC4 ✅ freshness line ("As of … run #… DRY-RUN badge") asserted via DRY-RUN presence.
- Suite: ruff/mypy clean, 94 passed. **Gate: PASS**
