---
name: Nagbot Public WIP Wallboard
status: final
updated: 2026-07-13
inherits: Corporativo design system (src/nagbot/web/static/brand/brand.css, style.css; design_system/)
colors:
  # Inherited Corporativo tokens — do NOT redefine; reference by CSS var.
  accent: "var(--qph-orange)"          # #e7851a
  ink: "var(--qph-ink)"                # #3d3d3d dark surface (wallboard bg option)
  text-strong: "var(--qph-gray-700)"   # #595756
  text-muted: "var(--qph-gray-300)"    # #949394
  surface-page: "var(--qph-white)"
  surface-card: "var(--qph-white)"
  border: "var(--qph-border)"          # #e3e2e2
  tier-on_fire: "var(--tier-on_fire)"  # red   #d64545
  tier-hot: "var(--tier-hot)"          # orange #e7851a
  tier-aging: "var(--tier-aging)"      # yellow #f9c021
  tier-fresh: "var(--tier-fresh)"      # teal  #15c0af
typography:
  display: "Barlow, system-ui, sans-serif"   # self-hosted woff2, already bundled under /static/brand/fonts
  body: "Barlow, system-ui, sans-serif"
  numeral-scale: "clamp(2.5rem, 6vw, 5rem)"   # the big open-count number, wallboard-legible
rounded: "16px"        # cards (--qph-radius-lg)
spacing: "4px base scale (--qph-space-*)"
components: [eyebrow, kpi-number, tier-distribution-bar, wip-person-table, oldest-tickets-table, asof-badge, refresh-indicator]
---

# Nagbot Public WIP Wallboard — DESIGN.md

**Spine wins on conflict with any mock.** This surface *inherits* the Corporativo design system already implemented in `brand.css` / `style.css`. It defines only the deltas needed for a **public, embedded status wallboard**. Never introduce new brand colors, fonts, or CDN assets.

## Brand & Style

Corporativo, in "operations status board" register: calm, factual, glanceable from across a room. It is not a marketing page — it is a NOC wallboard embedded in Zabbix. The brand signature (UPPERCASE Barlow Black eyebrows, orange accent over corporate grays) carries the identity; everything else recedes so the **numbers and the tier colors** do the talking. Motion is minimal (a quiet refresh tick), never decorative.

## Colors

Reuse the tokens in the frontmatter verbatim — they already exist in `style.css`. Tier semantics are fixed and must match the engine (`tiers.py`) and the internal board:

- **on_fire** → `--tier-on_fire` (red) · **hot** → `--tier-hot` (orange) · **aging** → `--tier-aging` (yellow, needs dark text `--on-yellow`) · **fresh** → `--tier-fresh` (teal).
- Page background: `--qph-white` (light, matches internal board) — **[ASSUMPTION]** light theme for parity; a dark `--qph-ink` variant is a possible follow-up for dim NOC walls.
- Never encode tier by color alone — always pair with emoji + label + count (accessibility floor, see EXPERIENCE.md).

## Typography

Barlow for everything (already self-hosted at `/static/brand/fonts/*.woff2` — critical: **no Google Fonts / external CDN**, so the page renders inside a strict iframe CSP). Signature heading style: an UPPERCASE eyebrow (`CORPORATIVO · NAGBOT`) over a bold section title (`TEAM WIP`). The hero open-ticket count uses `numeral-scale` (frontmatter) — deliberately oversized for wallboard legibility.

## Layout & Spacing

- **Full-bleed, chrome-less.** No app nav, no footer links, no login affordance — the page is meant to live inside someone else's frame. A centered `--qph-container-max` (1200px) column with generous `--qph-space-*` insets; collapses gracefully in a narrow iframe.
- Vertical order top→bottom: **eyebrow/header → hero KPIs (total + tier distribution bar) → WIP per person → oldest tickets → as-of/refresh footer strip.**
- Wide, low-density tables so rows are readable at a glance; tables scroll horizontally inside their own container on narrow frames (never break the page layout).

## Elevation & Depth

Soft, gray-tinted shadows only (`--qph-shadow-sm/md`), never pure black. Cards on a subtle page. Flat, quiet — depth communicates grouping, not drama.

## Shapes

Cards `--qph-radius-lg` (16px); pills/badges `--qph-radius-pill`. Tier chips are the existing `.badge.{tier}` pills.

## Components

- **eyebrow** — uppercase Barlow, gray section + orange title, brand bar separator.
- **kpi-number** — the hero total open count at `numeral-scale`, with a one-word caption.
- **tier-distribution-bar** — the existing horizontal proportional bar (red/orange/yellow/teal segments sized by count), each segment labeled with emoji + count.
- **wip-person-table** — owner, open count, per-tier chips, oldest age, worst-stale. Mirrors the internal board's "WIP per person".
- **oldest-tickets-table** — tier dot, ticket id (GLPI link), title, owner, age, no-update. Mirrors the internal "leaderboard".
- **asof-badge** — "As of {timestamp} — run #N", plus a DRY-RUN pill when applicable.
- **refresh-indicator** — a subtle "auto-refreshing every 60s" line; the only moving element.

## Do's and Don'ts

- **Do** keep it 100% self-contained (inline or `/static` CSS + self-hosted fonts) so it survives a restrictive embedding CSP.
- **Do** keep it read-only — no forms, no buttons, no snooze/run-now controls (those stay on the authenticated app).
- **Do** maximize contrast and font size for at-a-distance reading.
- **Don't** add the app `<nav>` / brand link-to-home / version chrome from `base.html.j2`.
- **Don't** pull any external resource (font, script, image) — it will break inside the Zabbix iframe.
- **Don't** invent new colors; every color is a Corporativo token.
