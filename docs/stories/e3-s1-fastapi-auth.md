# E3-S1: FastAPI app, healthz & Basic auth

Status: Draft

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
- [ ] web/app.py: create_app, auth middleware, /healthz — AC1..AC4
- [ ] web/templates/base.html.j2 + web/static/style.css — AC5
- [ ] main.py serve wiring — AC1
- [ ] tests/integration/test_web.py (auth matrix, healthz) — AC2..AC4

## Dev Notes
Pure-ASGI-friendly: use FastAPI dependencies or middleware; `secrets.compare_digest`.
Store shared with scheduler thread (Store's internal lock from E2-S3 covers it). Jinja2
via fastapi.templating with directory `web/templates`, static mounted at /static
(healthz-exempt list: /healthz, /static/*).

## Testing
TestClient: healthz 200 unauthenticated; / 401 without creds, 200 with; 503 when password
unset; lifespan scheduler start/stop (spy).

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
