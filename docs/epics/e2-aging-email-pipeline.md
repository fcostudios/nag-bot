# Epic 2 — Aging engine, email digest & dry-run pipeline (MVP)

**Goal:** The deployable core: business-day aging + severity tiers, ownership grouping,
SQLite state, rendered per-owner digests, a live Email adapter (Teams/WhatsApp stubs
behind the same protocol), and the scheduled orchestrator — dry-run by default.

**Depends on:** E1 (config, GLPI client).

| Story | Title | Size |
|---|---|---|
| E2-S1 | Business-day aging + tier engine | M |
| E2-S2 | Ownership resolution + grouping | S |
| E2-S3 | SQLite store: migrations + Store | M |
| E2-S4 | Digest builder, templates & goldens | M |
| E2-S5 | ChannelAdapter protocol + Email live + stubs | M |
| E2-S6 | Orchestrator, scheduler, entrypoint & compose | L |

**Done when:** `docker compose up` + `python -m nagbot run-once` performs a full dry-run
cycle (snapshots + dry_run send-log rows, no SMTP traffic) and the cron fires on schedule.

## Retrospective

**Closed:** 2026-07-09 · 6/6 stories Done, all gates PASS · suite: 87 tests, ruff+mypy clean.

- **Changed vs. plan:** escalation manager-CC turned out to be ~90% "for free" in S3+S5+S6
  (streak table, CC plumbing, kind='escalation' logging all shipped and tested here);
  E4-S1 shrinks to semantics review + dashboard surfacing. Added `runtime.py` as the
  single wiring point for CLI + web.
- **Decisions recorded:** snoozed tickets don't accumulate red streaks; WhatsApp param
  order fixed as [name, open, overdue, #oldest, days]; `serve` ships as scheduler-only
  keepalive until E3-S1.
- **Deployable:** yes — dry-run email MVP works end-to-end (`run-once`, compose config
  validated); first real deploy still needs the user's GLPI/SMTP credentials and a
  `fetch --json` sanity pass (go-live checklist).
