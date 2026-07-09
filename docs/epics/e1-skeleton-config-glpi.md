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

**Closed:** 2026-07-09 · 4/4 stories Done, all gates PASS · suite: 28 tests, ruff+mypy clean.

- **Changed vs. plan:** GLPI-11 version warning (S4-AC4) landed early in S3 — the
  `X-GLPI-Version` initSession header made a separate probe pointless. S2 absorbed two
  config fields from later epics (`aliases`, `whatsapp_max_per_run`) to avoid YAML churn.
- **Environment finding:** the dev sandbox blocks Docker registry CDNs, so image builds
  are CI-verified only (recorded in S1). No impact on code.
- **Carry-overs:** `fetch --json` manual run against the real GLPI instance needs the
  user's credentials — moved to the go-live checklist (README, E2-S6). SQLite-backed
  field cache lands in E2-S3 as planned.
