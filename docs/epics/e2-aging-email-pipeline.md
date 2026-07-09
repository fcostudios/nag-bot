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

_(appended when the epic closes)_
