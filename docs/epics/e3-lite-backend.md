# Epic 3 — Lite backend (WIP + ops dashboards)

**Goal:** The container's web face: live team WIP dashboard, ops dashboard (runs + send
log), per-ticket nag history, snooze controls, digest preview, and manual run-now — all
server-rendered Jinja2 behind HTTP Basic auth; `/healthz` for the container healthcheck.

**Depends on:** E2 (store, pipeline, renderer).

| Story | Title | Size |
|---|---|---|
| E3-S1 | FastAPI app, healthz & Basic auth | S |
| E3-S2 | Team WIP dashboard | M |
| E3-S3 | Ops dashboard + ticket history | M |
| E3-S4 | Snooze/unsnooze, run-now & preview | M |

**Done when:** all routes render from a dry run's data behind Basic auth; Docker
HEALTHCHECK passes; snoozing a ticket visibly removes it from the next digest.

## Retrospective

_(appended when the epic closes)_
