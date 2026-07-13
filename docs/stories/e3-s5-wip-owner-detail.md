---
baseline_commit: 703d9e046ca2a3664b458d199551660ed0d878f0
---

# E3-S5: WIP per-person ticket detail

Status: done

<!-- Created via bmad-create-story. Follows the project story format (see e3-s2-wip-dashboard.md). -->

## Story

As a **team lead viewing the Team WIP dashboard**,
I want to **click a person and see the full list of their open tickets with per-ticket detail (id, title, tier, age, staleness, SLA, GLPI link)**,
so that **I can drill from the per-person summary into the actual work without opening the email digest or GLPI first**.

## Context

- **Depends on:** E3-S1 (FastAPI app + Basic auth), E3-S2 (WIP dashboard, `PersonWip` rollup, `wip.html.j2`), E2-S3 (snapshot store).
- **Data source:** `rt.store.latest_snapshot()` → `(RunRow | None, list[SnapshotRow])` — the **same source the dashboard already uses**. No live GLPI on page load (architecture §1; only `/preview` and `/run-now` fetch live).
- **Key enabler:** `SnapshotRow` already persists everything a detail view needs — `ticket_id`, `title`, `owner_key`, `owner_name`, `tier`, `age_bd`, `stale_bd`, `sla_status`, `sla_due`, `snoozed` (`src/nagbot/store/repo.py:42-56`). So the detail view is a pure filter+render of existing snapshot data; **no store schema change, no new GLPI call**.
- **Relationship to siblings:** `/tickets/{id}` (E3-S3) is per-*ticket* history; `/preview` (E3-S4) is a live per-owner email simulation. This story fills the gap: a per-*owner* view of the current snapshot, reached by drilling down from the dashboard's "WIP per person" table.
- **New route (decided with owner):** `GET /wip/{owner_key}`.

## Acceptance Criteria

- **AC1:** `GET /wip/{owner_key}` renders, from the **latest** run's snapshots, only the tickets whose `owner_key` matches the path param. Each ticket row shows: tier badge (emoji + label), ticket id linking to GLPI (`{glpi_web_base}/front/ticket.form.php?id={ticket_id}`), title, age (`age_bd|days`), staleness (`stale_bd|days`), and SLA status. The page header shows the owner's display name (`owner_name`) and the run metadata ("As of {run.started_at} — run #{n}" + DRY-RUN badge), mirroring the dashboard header.
- **AC2:** Ticket rows are ordered worst-first: by tier severity (ON_FIRE → HOT → AGING → FRESH), then oldest `age_bd` first — consistent with the digest ordering (`sort_scored` in `ownership.py`).
- **AC3:** Snoozed tickets in the list are marked with a 💤 marker (same convention as the dashboard / `wip.html.j2`).
- **AC4:** On the WIP dashboard (`wip.html.j2`), each person's name cell is a link to `/wip/{owner_key}`, with the `owner_key` URL-encoded so keys containing `:` or spaces (e.g. `tech:jdoe`, `group:Service Desk`, `unassigned`) produce valid, correctly-routed links. The route receives the decoded key and matches snapshots exactly.
- **AC5:** If `owner_key` has no tickets in the latest snapshot (unknown/typo owner, or an owner whose queue is now empty), or if there is no snapshot yet (`run is None`), the page renders a friendly empty state ("No open tickets for this owner as of the latest run" / "No runs recorded yet") with HTTP 200 and a link back to the dashboard — it must not raise a 500.
- **AC6:** The route is protected by the existing Basic-auth middleware (no per-route auth code needed); `/wip/{owner_key}` is **not** added to `AUTH_EXEMPT_PREFIXES`. Unauthenticated requests get 401; missing `DASHBOARD_PASSWORD` yields 503 — same as sibling routes.
- **AC7:** A "← Back to WIP" link returns to `/`.

## Tasks

- [x] `src/nagbot/web/app.py` — add `GET /wip/{owner_key}` inside `register_routes()` (after `wip_dashboard`, ~line 181). Load `rt.store.latest_snapshot()`, filter `snaps` by `owner_key`, sort worst-first (AC2), compute `snoozes = {s.ticket_id for s in owner_snaps if s.snoozed}`, and render `wip_detail.html.j2`. Handle `run is None` and empty-owner cases (AC1, AC2, AC3, AC5, AC6).
- [x] `src/nagbot/web/templates/wip_detail.html.j2` — NEW template extending `base.html.j2`: header (owner_name + run metadata + DRY-RUN badge), per-ticket table reusing the snapshot-row markup style from `ticket.html.j2`/`wip.html.j2` (tier badge via `tier_emoji`/`tier_label`, GLPI id link via `glpi_web_base`, title, `age_bd|days`, `stale_bd|days`, SLA, 💤 marker), empty state, and "← Back to WIP" link (AC1, AC3, AC5, AC7).
- [x] `src/nagbot/web/templates/wip.html.j2` — wrap the per-person name cell (line ~35) in `<a href="/wip/{{ p.owner_key|urlencode }}">{{ p.owner_name }}</a>` (AC4).
- [x] `tests/integration/test_web.py` — add integration tests (see Testing) covering AC1–AC5 (AC6 already covered by the generic auth tests; add one explicit assertion).

## Dev Notes

- **Tier type mismatch:** `SnapshotRow.tier` is a **`str`** (e.g. `"on_fire"`), while template globals `tier_emoji`/`tier_label` are keyed by the **`Tier` enum**. Convert with `Tier(s.tier)` in the route (or a small helper) before passing to the template, OR render via a helper that tolerates the string — mirror however `wip.html.j2`/`ticket.html.j2` currently resolve tier display. Do not assume the enum is directly indexable by the string.
- **Sorting:** reuse the existing severity ordering. `builder.build_rollup` already groups snapshots by `owner_key` (builder.py:92) and there is a tier-severity sort for `per_person`; for per-ticket ordering follow the digest's `sort_scored` semantics (ownership.py). A local sort key `(tier_severity, -age_bd)` is acceptable if it matches the digest order — keep it in one place.
- **Reuse, don't reinvent:** the digest macro `_macros.j2::ticket_row_html` operates on a `ScoredTicket` (`.ticket.url`, `.metrics.age_bd`, …), NOT on a flat `SnapshotRow`. Do **not** try to force `SnapshotRow` through it. The snapshot-row table in `ticket.html.j2` is the correct pattern to mirror.
- **Templates env:** routes render through `make_templates()` (app.py:69-76); `Tier`, `tier_emoji`, `tier_label`, `glpi_web_base`, `dry_run`, `version`, and the `days`/`localdt` filters are already available in template context.
- **URL encoding:** FastAPI decodes path params automatically, so the route sees `group:Service Desk` decoded. The encoding responsibility is on the **link** in `wip.html.j2` (`|urlencode`). Verify a key with a space round-trips.
- **No writes:** this is a read-only GET. It must not write to the store, must not call GLPI, and must not affect escalation streaks.

### Project Structure Notes

- New route lives in the existing `register_routes()` — no new module. New template joins the others under `src/nagbot/web/templates/`. Naming `wip_detail.html.j2` parallels `wip.html.j2`.
- No change to `store/repo.py`, `digest/builder.py`, or the snapshot schema.

### References

- [Source: docs/epics/e3-lite-backend.md] — Epic 3 scope: server-rendered Jinja2 behind Basic auth, snapshot-driven pages.
- [Source: docs/stories/e3-s2-wip-dashboard.md] — dashboard + `PersonWip` rollup + `wip.html.j2` this drills down from.
- [Source: src/nagbot/store/repo.py:42-56] — `SnapshotRow` fields (title/owner_name/tier/age_bd/stale_bd/sla_status/snoozed).
- [Source: src/nagbot/store/repo.py:196] — `latest_snapshot()`.
- [Source: src/nagbot/web/app.py:157-322] — `register_routes()`; auth middleware app.py:43,111-124; templates app.py:69-76.
- [Source: src/nagbot/web/templates/ticket.html.j2] — snapshot-row rendering pattern to mirror.
- [Source: docs/architecture.md §1, §3.6] — no live GLPI on page load; Basic-auth model.

## Testing

Framework: `pytest` + FastAPI `TestClient` in `tests/integration/test_web.py`, using the existing `make_runtime`/`rt`/`client` fixtures, `seed_snapshots(store)` helper, and `AUTH` constant. No GLPI mocking needed (snapshot-only route).

- **test_wip_detail_lists_only_that_owner (AC1, AC2):** seed snapshots for `tech:jdoe` (≥2 tickets across tiers) and a second owner. `GET /wip/tech:jdoe` (with AUTH) → 200; asserts both jdoe ticket titles and their GLPI deep links appear, the other owner's ticket does NOT, and the worst tier (on_fire) row appears before a fresher row (index ordering assertion).
- **test_wip_detail_shows_snooze_marker (AC3):** seed a snoozed ticket for the owner → response contains 💤.
- **test_wip_dashboard_links_to_detail (AC4):** `GET /` → HTML contains `href="/wip/tech:jdoe"`; include an owner key with a space (e.g. `group:Service Desk`) and assert the link is URL-encoded and that `GET` on the encoded path resolves to that owner's tickets.
- **test_wip_detail_unknown_owner_empty_state (AC5):** `GET /wip/tech:nobody` → 200 and contains the empty-state text (no 500). Also cover `run is None` (fresh store, no snapshots) → 200 empty state.
- **test_wip_detail_requires_auth (AC6):** `GET /wip/tech:jdoe` without auth → 401 with `WWW-Authenticate: Basic realm="nagbot"`.

Coverage summary: AC1–AC7 each mapped to at least one assertion above; run `python -m pytest tests/integration/test_web.py -q` and the full suite before marking done.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (bmad-dev-story)

### Debug Log References

- RED: 6 new tests failed as expected (`/wip/{owner_key}` → 404, dashboard link absent).
- GREEN: after route + template + link, all 7 E3-S5 tests pass.
- Full suite: 141 passed (was 134); `ruff check` clean.

### Completion Notes List

- Implemented `GET /wip/{owner_key}` as a **snapshot-only** read (no GLPI, no writes), reusing `rt.store.latest_snapshot()` — same source as the dashboard. Confirmed `SnapshotRow` already carries `title`/`owner_name`, so no schema change was needed.
- Worst-first ordering uses the shared `TIER_ORDER` map from `engine/tiers.py` (`key=(TIER_ORDER[Tier(s.tier)], -age_bd)`), matching digest severity order.
- New `wip_detail.html.j2` mirrors the existing leaderboard snapshot-row markup (tier emoji via `Tier(s.tier)`, GLPI deep link, 💤 / ⚠️ markers) and adds an SLA column + empty state + "← Back to WIP".
- Dashboard owner cell now links with `|urlencode` so keys with `:` / spaces (e.g. `group:Service Desk`) route correctly; verified round-trip in tests.
- AC1–AC7 all covered; empty-owner and no-snapshot cases render 200 (not 404/500) per AC5.

### File List

- `src/nagbot/web/app.py` (modified — import `TIER_ORDER`/`Tier`; new `wip_detail` route; **autoescape fix** in `make_templates`)
- `src/nagbot/web/templates/wip_detail.html.j2` (new; tier emoji **+ label**)
- `src/nagbot/web/templates/wip.html.j2` (modified — owner cell links to detail)
- `tests/integration/test_web.py` (modified — 7 E3-S5 tests + 1 XSS regression test)

## QA Results

**Review method:** bmad-code-review — 3 parallel adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) vs baseline `703d9e0`. Findings triaged and empirically verified before acting.

**AC verdicts:** AC2–AC7 SATISFIED and tested. AC1 raised as PARTIAL (tier label missing) — now fixed.

**Findings & resolutions:**
- **[HIGH] Stored + reflected XSS** — web templates render `.html.j2`, which Starlette's `select_autoescape()` does **not** autoescape, so GLPI ticket titles, owner names, and the reflected `owner_key` path param were emitted unescaped. Proven end-to-end. **Fixed:** `templates.env.autoescape = True` in `make_templates()` (root-cause; trusted pre-rendered HTML in `/preview` & `/rollup` already used `|safe`, so no double-escaping). Regression test `test_wip_detail_escapes_html_xss` added. This also closes the same latent gap in the sibling web templates.
- **[LOW] AC1 tier "emoji + label"** — template showed emoji only. **Fixed:** added `tier_label`.
- **[LOW] Unknown `tier` string → 500** (`Tier(s.tier)`) — NOT fixed: unreachable in normal operation (`classify()` only emits valid tiers) and identical to the pre-existing pattern on `/`, `ticket.html.j2`, `build_rollup`. Logged as a pre-existing, app-wide defensive-handling follow-up rather than a scoped patch here.
- **[LOW] ⚠️ escalation marker / id→`/tickets` link** — kept intentionally; both match the established dashboard convention.

**Suite:** 142 passed (was 134 at baseline), ruff clean.

**Gate:** ✅ PASS — approved for merge.
