# E3-S1: FastAPI app, healthz & Basic auth

Status: Done

## Story
As the operator, I want the web app skeleton with a healthcheck and Basic auth, so that
the container reports liveness and no dashboard route is ever served unprotected.

## Context
First E3 story; `serve` (E2-S6) now hosts uvicorn with the scheduler in the app lifespan.

## Acceptance Criteria
- AC1: `create_app(cfg, store, …)` factory; lifespan starts/stops the scheduler; `serve` runs uvicorn on 0.0.0.0:8080.
- AC2: `GET /healthz` (auth-exempt) returns JSON: db ok, last run (id/status/time/dry_run), scheduler running, version. Dockerfile HEALTHCHECK hits it.
- AC3: All other routes require Basic auth against `DASHBOARD_PASSWORD` (any username, constant-time compare); wrong/missing creds → 401 + WWW-Authenticate.
- AC4: `DASHBOARD_PASSWORD` unset → protected routes return 503 "set DASHBOARD_PASSWORD" (never serve unprotected).
- AC5: base.html.j2 + style.css: nav (WIP · Ops · Preview), dry-run banner block, tier badge styles shared with email macros' colors.

## Tasks
- [x] web/app.py: create_app, auth middleware, /healthz — AC1..AC4
- [x] web/templates/base.html.j2 + web/static/style.css — AC5
- [x] main.py serve wiring — AC1
- [x] tests/integration/test_web.py (auth matrix, healthz) — AC2..AC4

## Dev Notes
Pure-ASGI-friendly: use FastAPI dependencies or middleware; `secrets.compare_digest`.
Store shared with scheduler thread (Store's internal lock from E2-S3 covers it). Jinja2
via fastapi.templating with directory `web/templates`, static mounted at /static
(healthz-exempt list: /healthz, /static/*).

## Testing
TestClient: healthz 200 unauthenticated; / 401 without creds, 200 with; 503 when password
unset; lifespan scheduler start/stop (spy).

## Dev Agent Record
- `create_app(rt, with_scheduler=False)` keeps tests scheduler-free; production `serve()` runs uvicorn with the scheduler in the lifespan (replacing E2-S6's keepalive as planned).
- Web Jinja env reuses the digest renderer's filters/globals (`localdt`, `days`, tier emoji/labels) so dashboard and email semantics can't drift.
- `/static` is auth-exempt alongside `/healthz` (stylesheet must load on the 401 login prompt page).
- Auth compares only the password (any username) via `secrets.compare_digest`; malformed base64 rejected, not crashed.
- healthz returns 503 with status=degraded if the DB read fails — Docker HEALTHCHECK then restarts the container.

## QA Results
- AC1 ✅ app factory + lifespan scheduler + `serve()` uvicorn on 0.0.0.0:8080 (wired from main.py `serve`).
- AC2 ✅ `test_healthz_is_auth_exempt` (db, dry_run, last_run payload); Dockerfile HEALTHCHECK already targets /healthz (E1-S1).
- AC3 ✅ `test_routes_require_basic_auth` (401 + WWW-Authenticate, wrong password 401, right password passes).
- AC4 ✅ `test_missing_password_returns_503` (message names DASHBOARD_PASSWORD; healthz unaffected).
- AC5 ✅ base template (nav WIP·Ops·Preview, dry-run banner block) + style.css with shared tier badge colors; `test_static_is_auth_exempt`.
- Suite: ruff/mypy clean, 91 passed. **Gate: PASS**
