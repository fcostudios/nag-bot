# E2-S4: Digest builder, templates & goldens

Status: Done

## Story
As a technician, I want a short, scannable digest — worst first, every row deep-linking to
GLPI — so that acting on my stale pile takes one click, not archaeology.

## Context
After E2-S1/S2. Rollup template ships here (used by E4); Teams card template ships here
(used by stub now, live in E5).

## Acceptance Criteria
- AC1: `build_digests(scored, cfg, escalated_ids, now)` → one `Digest` per owner: tickets worst-tier-first then oldest, per-tier counts, `escalated` subset flagged.
- AC2: `Renderer.email_subject(d)` nags with numbers: "⏰ {n} open tickets — {overdue} OVERDUE, oldest {days}d"; overdue segment omitted when zero.
- AC3: `email_html` renders a tight table (tier badge, id link, title, age, stale, SLA), inline-styled, 🔴 rows first; SLA column/language only for tickets with an SLA (NFR9); `email_text` mirrors it in plain text.
- AC4: `teams_card(d)` returns valid Adaptive Card JSON (schema 1.4) with the same content; `rollup_html(r)` renders per-person WIP, tier distribution, top-10 leaderboard.
- AC5: Golden tests cover all four outputs at a frozen timestamp; `pytest --update-golden` regenerates.

## Tasks
- [x] digest/builder.py: Digest, Rollup, PersonWip, build_digests, build_rollup — AC1
- [x] digest/templates/: _macros.j2, email_digest.html.j2, digest.txt.j2, teams_card.json.j2, manager_rollup.html.j2 — AC2..AC4
- [x] digest/renderer.py: Renderer — AC2..AC4
- [x] tests/golden/ + conftest --update-golden flag — AC5

## Dev Notes
Jinja2 Environment with PackageLoader("nagbot.digest"), autoescape for .html.j2 only
(teams_card is JSON — render with `tojson` filters, then json.loads to validate). Tier
badge macro shared. Dates rendered in cfg.timezone. Keep HTML table-based + inline CSS
(mail clients). One "why this matters" line at top, no fluff (spec §5).

## Testing
Golden fixture: 1 owner, 5 tickets covering all tiers + NO_SLA + escalated; frozen
now=2026-07-09T08:00-05:00. Byte-compare after newline normalization.

## Dev Agent Record
- Subject shows "{b} OVERDUE" only when SLAs are actually breached, else "{r} on fire" for red-by-staleness — keeps NFR9's adaptive language in the subject line too.
- Autoescape is a filename lambda (`*.html.j2` only): the Teams card template emits JSON via `tojson` filters and is `json.loads`-validated at render time, so a malformed card fails in tests, not in Teams.
- Digest gains convenience properties (ticket_ids, breached_count, oldest, has_sla_tickets) used by subject, adapters and send-logging.
- Digests sorted worst-owner-first for deterministic dispatch order; rollup leaderboard ranks by (tier, stale desc, age desc).
- Golden harness is a small `GoldenComparer` fixture in tests/conftest.py (newline-normalized compare; `--update-golden` regenerates).

## QA Results
- AC1 ✅ `test_digest_build_shape` (worst-first order [4821,4890,4930,4999,5012], counts, escalated subset).
- AC2 ✅ `test_email_subject` == "⏰ 5 open tickets — 1 OVERDUE, oldest 12d (please act)".
- AC3 ✅ email_digest.html golden: inline-styled table, 🔴 first, SLA column present only because fixture has SLA tickets (has_sla_tickets gate); digest.txt mirrors.
- AC4 ✅ teams_card.json golden validates as AdaptiveCard 1.4; manager_rollup.html golden covers per-person WIP + distribution + top-10 leaderboard.
- AC5 ✅ four goldens committed under tests/golden/files/; regenerated via `pytest --update-golden`.
- Suite: ruff/mypy clean, 73 passed. **Gate: PASS**
