# Epic 1 — Skeleton, config & GLPI client

**Goal:** A runnable, CI-guarded scaffold; validated env+YAML configuration with dry-run
defaulting on; a GLPI REST client that reliably reads open tickets (session lifecycle,
pagination, retries, field discovery).

**Depends on:** nothing (first epic).

| Story | Title | Size |
|---|---|---|
| E1-S1 | Project scaffold + CI | S |
| E1-S2 | Config loading (env + YAML) | M |
| E1-S3 | GLPI session + ticket search | M |
| E1-S4 | Field discovery, cache & version check | M |

**Done when:** `python -m nagbot fetch --json` prints normalized open tickets against a
real GLPI instance (manual), and CI (ruff, mypy, pytest, docker build) is green.

## Retrospective

_(appended when the epic closes)_
