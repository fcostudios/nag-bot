---
name: Nagbot Public WIP Wallboard
status: final
updated: 2026-07-13
design_ref: ./DESIGN.md
---

# Nagbot Public WIP Wallboard — EXPERIENCE.md

**Spine wins on conflict.** Owns *how it works*; visual tokens live in `{DESIGN.md}`. This is a **public, unauthenticated, iframe-embeddable** status board rendered server-side (Jinja2), showing the same snapshot data as the internal WIP dashboard.

## Foundation

- **Form factor:** web page, server-rendered, no client framework. Designed to be embedded via `<iframe>` (Zabbix portal) and also viewable standalone.
- **UI system:** inherits the Corporativo design system already in `style.css` (see `{DESIGN.md}`). Reuses the internal board's aggregate logic (`build_rollup`) and snapshot source (`store.latest_snapshot()`) — **no live GLPI on load**.
- **Access:** no auth. The route is added to the app's `AUTH_EXEMPT_PREFIXES` (like `/healthz`, `/static`). Framing is explicitly allowed (do not emit `X-Frame-Options: DENY`; if a CSP is set, `frame-ancestors` must permit the embedding origins).
- **Data scope (confirmed, informed decision):** identical to internal — includes ticket titles + ids. Owner accepted the PII/LOPDP exposure; EXPERIENCE and the story must record this as an explicit choice, not an oversight.

## Information Architecture

Single screen, one scroll, top→bottom:
1. **Header** — eyebrow `CORPORATIVO · NAGBOT` + title `TEAM WIP`.
2. **Hero KPIs** — big total-open count + tier **distribution bar**.
3. **WIP per person** — table of owners (worst-first).
4. **Oldest tickets** — the leaderboard (worst-first), ticket id links to GLPI.
5. **Footer strip** — as-of timestamp + run #, DRY-RUN pill when applicable, auto-refresh notice.

IA closes: the stated need ("public view of Team WIP + oldest tickets, embeddable") is delivered entirely by this one surface; no navigation, no secondary screens.

## Voice and Tone

Terse, factual, operational. English labels (parity with the internal board; ticket titles remain in their original language). No marketing copy, no calls to action. Numbers first.

## Component Patterns (behavioral)

- **tier-distribution-bar** — proportional segments by tier count; a tier with 0 is omitted (no empty segment). Purely presentational; not interactive.
- **wip-person-table / oldest-tickets-table** — static, read-only. Ordering is worst-first (tier severity, then age) — same as the digest/internal board.
- **ticket id link** — points at the GLPI ticket (`{glpi_web_base}/front/...`). External viewers won't be authenticated into GLPI; the link is harmless (their GLPI will challenge/deny). Titles are shown as text.
- **No controls** — no snooze, no run-now, no filters, no drill-down link (the `/wip/{owner}` drill-down is authenticated and must not be linked from the public board).

## State Patterns

- **Populated** — the normal wallboard.
- **No data** — if `latest_snapshot()` returns no run, show a calm empty state ("Awaiting the first run") rather than an error; HTTP 200.
- **Stale data** — if the latest run is old, the as-of timestamp is the honest signal; **[ASSUMPTION]** optionally muted/greyed when older than a threshold (nice-to-have, not required for v1).
- **No loading/error spinner** — fully server-rendered; if the store read fails the page should still return a minimal safe shell, never a stack trace.

## Interaction Primitives

- **Auto-refresh** — the page reloads its data every ~60s so a wall-mounted screen stays current. Prefer `<meta http-equiv="refresh" content="60">` (zero JS, survives strict CSP) over a scripted reload. **[ASSUMPTION]** 60s cadence; make it a query param or config later if needed.
- No hover/click behaviors beyond the plain ticket links.

## Accessibility Floor

- Tier is conveyed by **emoji + label + count**, never color alone.
- Semantic `<table>` markup with header cells; the distribution bar carries text labels, not just colored blocks.
- Contrast: aging (yellow) uses dark text (`--on-yellow`); all text meets the internal board's contrast (already Corporativo-compliant).
- Font sizes err large for wallboard distance.

## Responsive & Platform

- Fluid from a narrow embedded frame (~360px) to a large NOC display. Container maxes at 1200px and centers on big screens.
- Tables wrap in an `overflow-x:auto` container so a narrow iframe scrolls the table, never the whole page.
- Must render correctly with the app's other chrome absent (this page does **not** extend the nav `base.html.j2`; it uses a minimal standalone base or its own `<head>`).

## Embedding & Exposure (product-specific)

- Route is `GET /public` (or `/public/wip`) — auth-exempt, read-only.
- No secrets, no auth affordance, no links back into authenticated areas.
- Self-contained assets only (see `{DESIGN.md}` Do's/Don'ts) so it renders under a strict host CSP.
- Response is cacheable for a short TTL (e.g. `Cache-Control: public, max-age=30`) to blunt load from many embedding viewers, aligned with the ~60s refresh.

## Key Flow — Andrés at the NOC wall

1. The Zabbix portal on the ops-room wall embeds `/public` in a panel.
2. Andrés walks in at 8:00 and glances up — no login, it's just there.
3. The hero reads **161 open**; the distribution bar is dominated by a wide **red** segment: **46 on fire**.
4. His eye drops to WIP-per-person — the top row shows one owner carrying **20 on-fire** tickets. **← climax: the bottleneck is visible in two seconds, from across the room.**
5. He turns to the team; the board refreshes itself 60 seconds later without anyone touching it.
