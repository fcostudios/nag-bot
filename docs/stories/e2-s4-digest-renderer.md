# E2-S4: Digest builder, templates & goldens

Status: Draft

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
- [ ] digest/builder.py: Digest, Rollup, PersonWip, build_digests, build_rollup — AC1
- [ ] digest/templates/: _macros.j2, email_digest.html.j2, digest.txt.j2, teams_card.json.j2, manager_rollup.html.j2 — AC2..AC4
- [ ] digest/renderer.py: Renderer — AC2..AC4
- [ ] tests/golden/ + conftest --update-golden flag — AC5

## Dev Notes
Jinja2 Environment with PackageLoader("nagbot.digest"), autoescape for .html.j2 only
(teams_card is JSON — render with `tojson` filters, then json.loads to validate). Tier
badge macro shared. Dates rendered in cfg.timezone. Keep HTML table-based + inline CSS
(mail clients). One "why this matters" line at top, no fluff (spec §5).

## Testing
Golden fixture: 1 owner, 5 tickets covering all tiers + NO_SLA + escalated; frozen
now=2026-07-09T08:00-05:00. Byte-compare after newline normalization.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
