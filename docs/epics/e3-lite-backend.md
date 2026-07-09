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

**Closed:** 2026-07-09 · 4/4 stories Done, all gates PASS · suite: 104 tests, ruff+mypy clean.

- **Changed vs. plan:** the WIP page needed zero new aggregation code (reused
  `build_rollup` from E2-S4); snooze form markup landed one story early (S3's ticket
  page); `python-multipart` added as a dependency for form posts.
- **Decisions recorded:** validation errors via 303 + `?error=` banner (stateless
  handlers); `/preview` never bumps escalation streaks; run-now thread parked on
  `app.state` for deterministic test joins.
- **Carry-overs to E4:** /ops could show current escalation streaks (E4-S1 AC4) and the
  last rollup card (E4-S2 AC3) — both have Store accessors ready (`escalations()`).
