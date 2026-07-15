# GLPI Nagbot ⏰

> Simple annoying bot to disturb your non-service-desk attention zen.

Makes dev-support ticket WIP and aging *visible and unavoidable*. Every weekday morning
it pulls open tickets from the GLPI REST API, computes business-day aging and severity
tiers, groups tickets by responsible person, and sends each person a short, pointed
digest — escalating to their manager when tickets stall. A built-in web dashboard shows
live WIP and a full audit log of every nag sent.

```
🔴 On fire   SLA breached or no update in 7+ business days  → manager CC after 3 red days
🟠 Hot       SLA due < 24h or no update in 5+ days
🟡 Aging     no update in 2+ days
🟢 Fresh     listed, no pressure
```

**Channels:** Email · Microsoft Teams (Adaptive Cards with @mentions, see
`docs/teams-setup.md`) · WhatsApp (Meta Cloud API utility template, rate-capped)

For **critical incidents that can't wait for tomorrow's digest**, a separate urgent-P0
escalation loop pages the owner on WhatsApp within a minute and climbs the chain until
someone acknowledges — see **[P0 escalation](#p0-escalation-epic-7)** below.

## Quick start (Docker)

```bash
cp .env.example .env                        # fill in GLPI + SMTP secrets
cp config/nagbot.example.yaml config/nagbot.yaml   # tune thresholds + owner map
docker compose up -d --build
curl -s localhost:8080/healthz | jq         # container health
open http://localhost:8080                  # dashboards (Basic auth: any user + DASHBOARD_PASSWORD)
```

The bot starts in **dry-run mode**: it fetches, scores, renders and logs everything but
sends nothing. That's deliberate.

## Go-live checklist

1. **GLPI API**: enable the REST API (Setup → General → API), create an API client
   (check its IP range!) and a read-only service account; put its App-Token + user
   token in `.env`.
2. **Sanity-check the connection**:
   `docker compose exec nagbot python -m nagbot fetch --json` — verify tickets appear
   and assignee names match the keys you'll use in the `owners:` map (use `aliases:` if
   GLPI returns display names instead of logins).
3. **Map owners** in `config/nagbot.yaml` (`owners:`, `groups:`, `fallback:`).
4. **Dry-run for a few days**: watch `/preview` and `/ops` — right people, right
   tickets, no unmapped-owner warnings.
5. **Deliverability**: make sure SPF/DKIM allow `SMTP_FROM` to send, or the naggy
   subject lines will land in spam.
6. **Flip the switch**: set `NAGBOT_DRY_RUN=false` in `.env` **and**
   `channels.dry_run: false` in the YAML (both are required), then
   `docker compose up -d`.

## Dashboards

| Route | What it shows |
|---|---|
| `/` | Live team WIP: tier distribution, per-person WIP, oldest-tickets leaderboard |
| `/ops` | Run history, send log (filterable), unmapped-owner warnings, manual **Run now** |
| `/tickets/{id}` | Per-ticket nag history + snooze/unsnooze |
| `/preview` | Renders the exact digests the next run would send (nothing stored/sent) |
| `/rollup` | The current Monday manager rollup, exactly as the email renders it |
| `/healthz` | JSON health (auth-exempt; used by the Docker healthcheck) |

Snooze legitimately-blocked tickets from the ticket page — they stay on the WIP board
(marked 💤) but skip digests and don't accumulate escalation streaks until the date
passes.

## Configuration

- **Secrets & endpoints** → environment variables (see `.env.example`).
- **Tuning** → `config/nagbot.yaml` (see `config/nagbot.example.yaml`): schedule crons,
  tier thresholds, holiday list (update yearly!), channels, owner/group maps, fallback.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e .[dev]
.venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest
```

Docs-driven: see `docs/prd.md`, `docs/architecture.md`, and the BMAD epics/stories under
`docs/epics/` and `docs/stories/` — every story carries its acceptance criteria, dev
record and QA gate. Golden files regenerate with `pytest --update-golden`.

## Channel setup

- **Email** — SMTP env vars; live out of the box once dry-run is disabled.
- **Teams** — create a Power Automate Workflow and set `TEAMS_WEBHOOK_URL`
  (step-by-step + curl test in `docs/teams-setup.md`); set each owner's `teams_id`
  (Microsoft 365 UPN) to get @mentions. Add `teams` to `channels.enabled`.
- **WhatsApp** — Meta Business account + registered number
  (`WHATSAPP_PHONE_NUMBER_ID`), access token (`WHATSAPP_TOKEN`), and an **approved
  utility template** (`WHATSAPP_TEMPLATE_NAME`; draft text in
  `docs/epics/e6-whatsapp-live.md` — Meta approval takes days, start early). Owner
  numbers must be E.164. Sends are capped per run (`channels.whatsapp_max_per_run`,
  default 20, worst offenders first) and owners without a number are simply skipped.

## P0 escalation (Epic 7)

A second, faster scheduler loop (every ~60s, its own lock) handles genuine **P0 incidents**
— it does not touch the daily digest pipeline. When a ticket is marked P0 in GLPI, nagbot
pages the owner on WhatsApp (via a self-hosted **OpenWA** sidecar), and if nobody replies
"on it" it climbs owner → manager → triage on a dwell cadence, re-checking the live ticket
before every page so it stops the instant the incident is resolved. Its whole design goal
is **"trust instrument — never cry wolf"**: it errs toward *not* paging, never toward
silently dropping a real P0.

- Ships **disabled and safe**: gated behind `escalation.enabled` **and**
  `escalation.transparency_notice_given` (a LOPDP transparency notice must reach staff
  first), and the default rule (`priority >= 5`) escalates nothing until a real P0 is marked.
- WhatsApp down/banned → **falls through to Teams** automatically. Sends are rate-capped
  per tick (ban-avoidance on the unofficial channel). A stale "on it" re-arms after
  `ack_grace_minutes`.
- Inbound acks arrive at `POST /webhooks/openwa` (authenticated with `OPENWA_WEBHOOK_SECRET`).

**Turning it on:** [`docs/e7-escalation-runbook.md`](docs/e7-escalation-runbook.md) (go-live
checklist + the staff notice text). **How it works, every knob, failure modes:**
[`docs/e7-escalation.md`](docs/e7-escalation.md).

## Roadmap

All seven epics are implemented: email digests, dashboards, escalation + Monday rollup,
Teams cards, WhatsApp digests, and urgent P0 escalation (Epic 7). Deferred within Epic 7:
the phone-**call** rung (needs the official Cloud API / Twilio — OpenWA can't call),
per-tier SLA-configurable dwell, and false-positive/ack-time stats. Ideas beyond the spec:
1:1 Teams DMs via Graph API, GLPI 11 high-level-API client, per-team digest channels.
