---
baseline_commit: 2bb169fe97819000765ee47b33439ef01f00bad6
---

# E3-S6: Public embeddable WIP wallboard

Status: done

<!-- bmad create-story. Follows project story format. UX: _bmad-output/planning-artifacts/ux-designs/ux-nag-bot-2026-07-13/{DESIGN.md,EXPERIENCE.md} -->

## Story

As an **end user or an embedding portal (e.g. Zabbix)**,
I want to **see the Team WIP summary and oldest tickets on a public, no-login page that can be embedded in an iframe**,
so that **the team's live status is visible on wallboards and other apps without handing out dashboard credentials**.

## Context

- **Depends on:** E3-S2 (`build_rollup`, tier distribution + per-person + leaderboard), E2-S3 (snapshot store). Data source is `rt.store.latest_snapshot()` — **no live GLPI on load**, same as the internal board.
- **Decision (explicit, informed — see UX EXPERIENCE.md §Foundation):** the public board shows the **same data as internal, including ticket titles + ids**. The owner confirmed this twice knowing it exposes customer PII publicly and accepted the LOPDP/compliance risk. This is a deliberate product choice, recorded here so it is not mistaken for an oversight.
- **Epic-3 charter deviation:** Epic 3 is "server-rendered Jinja2 **behind HTTP Basic auth**." This story intentionally adds the **first auth-exempt** HTML route. Noted so the deviation is on record.
- **UX contracts:** `DESIGN.md` (inherits Corporativo tokens) + `EXPERIENCE.md` (chrome-less, self-contained, auto-refresh, cacheable). Spines win on conflict.

## Acceptance Criteria

- **AC1:** `GET /public` returns **200 without authentication** and is served regardless of `DASHBOARD_PASSWORD` (add `/public` to `AUTH_EXEMPT_PREFIXES`, alongside `/healthz`, `/static`). It renders from `latest_snapshot()` + `build_rollup(...)`: total open, tier distribution bar, WIP-per-person table (owner, open, per-tier chips, oldest, worst-stale), and the oldest-tickets leaderboard (tier, id→GLPI link, title, owner, age, no-update) — worst-first ordering, matching the internal board.
- **AC2:** The page is **chrome-less** — it does NOT render the app nav from `base.html.j2` (no `/ops`/`/preview`/version/login affordances) and links nowhere into authenticated areas (in particular, owner names are **not** linked to the authenticated `/wip/{owner}` drill-down).
- **AC3:** The page is **iframe-embeddable**: the response must NOT carry `X-Frame-Options: DENY`/`SAMEORIGIN`, and if any CSP is emitted its `frame-ancestors` must not block embedding. All subresources are **same-origin** (`/static/...`) and self-hosted (no external font/CDN/script), so it renders under a strict host CSP.
- **AC4:** The page **auto-refreshes** for wallboard use via `<meta http-equiv="refresh" content="60">` (no JS, CSP-safe).
- **AC5:** The response sets a short public cache header (`Cache-Control: public, max-age=30`) to blunt load from many embedding viewers.
- **AC6:** All dynamic values (ticket titles, owner names) are **HTML-escaped** (autoescape is on for the web env as of E3-S5). A title/owner containing markup must not inject live HTML on this public page.
- **AC7:** Empty state — if there is no snapshot yet, `GET /public` returns **200** with a calm "awaiting first run" message (never a 500 / stack trace).

## Tasks

- [x] `src/nagbot/web/app.py` — add `"/public"` to `AUTH_EXEMPT_PREFIXES`; add `GET /public` in `register_routes()` that loads `latest_snapshot()`, builds `build_rollup(...)`, renders `public.html.j2`, and sets `Cache-Control: public, max-age=30`. Handle `run is None` (AC1, AC3, AC5, AC7).
- [x] `src/nagbot/web/templates/public.html.j2` — NEW **standalone** template (own `<html>`, does NOT extend `base.html.j2`): self-contained `<head>` linking `/static/style.css` + `<meta http-equiv="refresh" content="60">`; eyebrow `CORPORATIVO · NAGBOT` + `TEAM WIP`; hero total + tier distribution bar; WIP-per-person table; oldest-tickets leaderboard; as-of/run + DRY-RUN + "auto-refresh 60s" footer; empty state. No nav, no owner drill-down links (AC1, AC2, AC4, AC6, AC7). Reuse the markup/classes from `wip.html.j2` minus the owner link.
- [x] `tests/integration/test_web.py` — public-route tests (see Testing) for AC1–AC7.

## Dev Notes

- **Auth exemption:** the middleware check is `request.url.path.startswith(AUTH_EXEMPT_PREFIXES)` (app.py:118). Adding `"/public"` exempts exactly this route. Keep the tuple ordering/style.
- **Chrome-less template:** do NOT `{% extends "base.html.j2" %}` (that pulls the nav + brand-home link + version). Write a minimal standalone document. It may still `<link rel="stylesheet" href="/static/style.css">` because `/static` is same-origin and auth-exempt — this satisfies "self-contained, no external CDN" while reusing the Corporativo tokens/classes. Add any wallboard-only rules inline or in `style.css`.
- **Framing:** Starlette/FastAPI does not set `X-Frame-Options` by default, so framing already works — but assert it in a test so a future security-middleware addition can't silently break embedding.
- **Reuse:** `build_rollup(snaps, now=run.started_at)` gives `total_open`, `distribution`, `per_person`, `leaderboard` — identical to the internal dashboard route; render the same data with `Tier(s.tier)` for tier display. Template globals `Tier`, `tier_emoji`, `tier_label`, `glpi_web_base`, `days`, `localdt` are available.
- **No new controls / no writes / no GLPI:** read-only GET; must not link to snooze/run-now or `/wip/{owner}`.
- **Cache header:** set on the `TemplateResponse` (e.g. `resp.headers["Cache-Control"] = "public, max-age=30"`).

### Project Structure Notes

- No new module. New standalone template alongside the others. No store/schema change.

### References

- [Source: _bmad-output/planning-artifacts/ux-designs/ux-nag-bot-2026-07-13/DESIGN.md] — visual identity (Corporativo tokens, wallboard register).
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-nag-bot-2026-07-13/EXPERIENCE.md] — IA, states, embedding/exposure, auto-refresh, key flow.
- [Source: src/nagbot/web/app.py:44,111-125,161-181] — `AUTH_EXEMPT_PREFIXES`, auth middleware, `wip_dashboard` (pattern to mirror).
- [Source: src/nagbot/web/templates/wip.html.j2] — markup to reuse (drop the owner drill-down link for AC2).
- [Source: src/nagbot/digest/builder.py] — `build_rollup` / `Rollup` fields.

## Testing

`pytest` + FastAPI `TestClient` in `tests/integration/test_web.py`, reusing `make_runtime`/`client`/`seed_snapshots`/`AUTH`.

- **test_public_dashboard_no_auth (AC1):** `GET /public` with NO auth → 200; seeded data → total + owner names + a ticket title present.
- **test_public_dashboard_public_when_password_unset (AC1):** with `password=None`, `GET /public` → 200 (internal routes 503, public still serves).
- **test_public_dashboard_is_chromeless (AC2):** rendered HTML does NOT contain the nav links (`href="/ops"`, `href="/preview"`) nor a `/wip/` owner drill-down link.
- **test_public_dashboard_framing_allowed (AC3):** response has no `X-Frame-Options` header (or not `DENY`/`SAMEORIGIN`).
- **test_public_dashboard_autorefresh_and_cache (AC4, AC5):** body contains `http-equiv="refresh"`; `Cache-Control` header contains `max-age`.
- **test_public_dashboard_escapes_html (AC6):** seed a ticket title with `<img onerror>` → escaped (`&lt;img`) in the public page, raw markup absent.
- **test_public_dashboard_empty_state (AC7):** fresh store → 200 + "awaiting"/"no data" text, not 500.

Run `python -m pytest tests/integration/test_web.py -q` then the full suite; a security review (bmad-code-review / security-review) is required before merge given public exposure.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (bmad-dev-story)

### Debug Log References

- RED: 5 public-route tests failed (route absent → 401). GREEN after route+template+exempt-prefix.
- Full suite: 149 passed (was 142); ruff clean.

### Completion Notes List

- `GET /public` added to `AUTH_EXEMPT_PREFIXES` and `register_routes()`; reuses `latest_snapshot()` + `build_rollup(...)` (same data as internal board, no live GLPI). Sets `Cache-Control: public, max-age=30`.
- New standalone `public.html.j2` — own `<html>`, no `base.html.j2` nav (chrome-less), `<meta http-equiv=refresh 60>`, links same-origin `/static/style.css` + self-hosted fonts (CSP-safe). No owner drill-down link (AC2).
- Escaping inherited from the E3-S5 autoescape fix; verified by `test_public_dashboard_escapes_html`.
- Wallboard styles (`.eyebrow`, `.hero`, `.table-wrap`, `body.public`, `.refresh-note`) appended to `style.css` per DESIGN.md.
- Framing intentionally allowed (no `X-Frame-Options`); asserted by test so a future security header can't silently break embedding.

### File List

- `src/nagbot/web/app.py` (modified — `/public` exempt + route)
- `src/nagbot/web/templates/public.html.j2` (new, standalone)
- `src/nagbot/web/static/style.css` (modified — wallboard styles)
- `tests/integration/test_web.py` (modified — 7 E3-S6 tests)
- `_bmad-output/planning-artifacts/ux-designs/ux-nag-bot-2026-07-13/{DESIGN,EXPERIENCE}.md` (UX spines)

## QA Results

**Review method:** focused adversarial **security review** (public-exposure attack surface) + full AC audit vs baseline `2bb169f`.

**AC verdicts:** AC1–AC7 all SATISFIED and tested (7 integration tests).

**Security findings & resolutions:**
- **[LOW] Bare-`startswith` auth exemption** — `path.startswith(("/healthz","/static","/public"))` would silently exempt a future sibling route (`/publish`, `/public-api/...`). No exploit today (no such route exists; `../` isn't collapsed by ASGI). **Fixed:** `is_auth_exempt()` now matches exact path or true sub-path (`p` or `p + "/"`). Regression test `test_auth_exemption_is_not_bare_prefix` (`/publicfoo`→401, `/healthzz`→401, `/public`→200, `/static/style.css`→200).
- **[LOW] Out-of-enum `tier` → 500** — `Tier(s.tier)` in `build_rollup`/template can 500 the board on a data-drift tier value. Confirmed **no stack-trace disclosure** (debug off → bare "Internal Server Error"); unreachable in normal operation (`classify()` only writes valid tiers). **Deferred** (consistent with E3-S5) as a shared `build_rollup` hardening item — see memory `nagbot-web-followups`. Now also affects `/public` (availability only).
- **Clean:** info disclosure (only WIP aggregate exposed — no secrets/config/traces), XSS (autoescape on; `test_public_dashboard_escapes_html`), DoS/caching (`Cache-Control: public, max-age=30`, bounded work), open-redirect/header-injection/CSRF (N/A read-only GET).
- **Accepted by design:** public PII exposure (owner's informed decision) and iframe framing (embedding requirement).

**Suite:** 150 passed (was 142 at baseline), ruff clean.

**Gate:** ✅ PASS — no Critical/High/Medium; both Lows resolved or explicitly deferred. Approved for merge.
