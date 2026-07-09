# GLPI Nagbot — Product Requirements Document (PRD)

**Version:** 1.0 · **Date:** 2026-07-09 · **Owner:** Francisco (fcostudios)
**Source:** `docs/source/glpi-nagbot-strategy.md` (original strategy doc)

## 1. Goals & Background

Dev-support ticket WIP and aging in GLPI must become *visible and unavoidable*. GLPI's
native notifications are event-based (ticket created, SLA level reached) — there is no
"every morning, send each tech a digest of their aging tickets." The Nagbot is a small
scheduled service that fills that gap: every weekday morning it pulls open tickets from
the GLPI REST API, computes aging and severity tiers, groups tickets by responsible
person, and sends each person a short, pointed digest — escalating tone and audience the
longer a ticket stalls.

**Goals:**

- G1: Every responsible person receives a daily, scannable digest of their open/aging tickets.
- G2: Stalled tickets escalate automatically (manager CC, leaderboard) so nothing rots silently.
- G3: The team can see WIP/aging state all day on a live dashboard, and ops can audit exactly what was sent to whom.
- G4: Nag fatigue is prevented by tiering (no pressure on fresh tickets), snooze, and one digest per day instead of many pings.

## 2. Requirements

### Functional

- **FR1** — The system runs a nag cycle on a configurable cron schedule (default weekdays 08:00 `America/Guayaquil`).
- **FR2** — Each cycle authenticates to the GLPI REST API (`apirest.php`, App-Token + user token) and fetches all tickets that are not solved/closed, with pagination.
- **FR3** — GLPI search-option field IDs are discovered automatically via `listSearchOptions/Ticket`, cached, and overridable in config.
- **FR4** — For each ticket the system computes: age (business days since opened), stale days (business days since last update), and SLA status (none / ok / due soon / breached) from `time_to_resolve`.
- **FR5** — Each ticket is classified into a tier using configurable thresholds: 🟢 Fresh, 🟡 Aging (stale ≥ 2 bd), 🟠 Hot (stale ≥ 5 bd or SLA due < 24h), 🔴 On fire (stale ≥ 7 bd or SLA breached).
- **FR6** — Tickets are grouped by responsible owner: assigned technician first, else assigned group, else a configured fallback owner. Owner contact details (email, Teams id, WhatsApp, manager) come from the YAML owner map; unmapped owners are flagged in the run report and routed to the fallback.
- **FR7** — Per owner, a digest is rendered (worst tier first, then oldest), with deep links to each ticket in GLPI, and dispatched through every enabled channel adapter.
- **FR8** — Channel adapters: Email via SMTP (live in MVP); Microsoft Teams via Power Automate Workflow webhook posting an Adaptive Card (stub in MVP, live in Epic 5); WhatsApp via Meta Cloud API utility template (stub in MVP, live in Epic 6).
- **FR9** — Every send (or skip/dry-run/failure) is logged with run id, channel, recipient, CC, ticket ids, status, and detail.
- **FR10** — Tickets can be snoozed until a date; snoozed tickets are excluded from digests (but still snapshotted) until the snooze expires.
- **FR11** — A ticket that stays 🔴 for N consecutive run-days (default 3) triggers a manager CC on the owner's digest; the escalation streak resets when the ticket leaves 🔴.
- **FR12** — Every Monday a manager rollup is sent: WIP per person, tier/aging distribution, worst-offenders leaderboard (Epic 4).
- **FR13** — Dry-run mode renders and logs everything but sends nothing. **Dry-run is the default**; going live requires an explicit setting in *both* the environment and the YAML config.
- **FR14** — Lite backend (same container) serves: a live team WIP dashboard (`/`), an ops dashboard with run history and send log (`/ops`), per-ticket nag history (`/tickets/{id}`), snooze/unsnooze forms, a preview of the next digests (`/preview`), and a manual run-now trigger (dry-run by default).
- **FR15** — A `/healthz` endpoint reports DB reachability, last run status, and scheduler liveness for the container healthcheck.

### Non-functional

- **NFR1** — Python 3.11+ single container (FastAPI + APScheduler); no PHP anywhere.
- **NFR2** — All GLPI access is read-only; a full cycle issues only a handful of paginated queries.
- **NFR3** — Secrets/endpoints via environment variables; tuning via a mounted YAML file; state on a mounted SQLite volume. No secrets in the repo or the DB.
- **NFR4** — Dashboard protected by HTTP Basic auth (`DASHBOARD_PASSWORD`); `/healthz` exempt.
- **NFR5** — A failed send for one owner/channel must not abort the rest of the run.
- **NFR6** — Business-day math is timezone-aware (`America/Guayaquil`) and respects a configurable holiday list.
- **NFR7** — Startup fails fast with a readable error when config is inconsistent (e.g. email enabled without SMTP settings).
- **NFR8** — All time-dependent logic takes `now` as an argument (testable with frozen time); CI runs lint (ruff), types (mypy), and tests (pytest) on every push.
- **NFR9** — SLA display is adaptive: tickets without `time_to_resolve` never show "overdue" language; staleness is the tiering backbone.

## 3. Epics

| Epic | Goal | Cycle |
|---|---|---|
| **E1** Skeleton, config & GLPI client | Runnable scaffold with CI; validated config; read tickets from GLPI reliably | this cycle |
| **E2** Aging engine, email digest & dry-run pipeline | The deployable MVP: tiers, digests, email, scheduler, dry-run | this cycle |
| **E3** Lite backend | WIP + ops dashboards, snooze, preview, run-now behind Basic auth | this cycle |
| **E4** Escalation & manager rollup | Red-streak manager CC; Monday rollup with leaderboard | later |
| **E5** Teams live | Adaptive Cards via Power Automate Workflow, mentions, deep links | later |
| **E6** WhatsApp live | Meta Cloud API utility template, rate cap, opt-out | later |

## 4. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | GLPI 11 deprecates `apirest.php` | Startup version check logs a warning; all GLPI I/O isolated in `src/nagbot/glpi/` |
| R2 | GLPI returns naive datetimes in the server's tz; misconfig skews every age | `glpi.server_timezone` config + startup sanity check comparing a fresh `date_mod` to now |
| R3 | Owner map keyed by GLPI login but API may return display names | Fetch both; verify matching manually during E1-S3 against the real instance |
| R4 | Nag fatigue → people mute it | Tiering, snooze, single daily digest (FR5, FR10, G4) |
| R5 | Wrong owner gets nagged on day one | Dry-run default (FR13); `/preview` before going live |
| R6 | Email deliverability (spam) | SPF/DKIM for the sender is ops homework outside this repo; documented in README |
| R7 | WhatsApp template approval lead time | Start Meta approval before E6 development |
| R8 | Holiday list goes stale | YAML-maintained; yearly upkeep noted in README |
| R9 | Teams legacy webhooks retiring (~May 2026) | E5 builds on Power Automate Workflows only |

## 5. Out of scope

- Writing anything back to GLPI (comments, status changes).
- True 1:1 Teams DMs (needs Graph API; channel @mentions suffice).
- Multi-instance/HA deployment; one container with a volume is the design point.
- User management on the dashboard (single shared Basic-auth credential).
