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

**Channels:** Email (live) · Microsoft Teams (Epic 5) · WhatsApp (Epic 6)

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

## Roadmap

- **E4** — manager escalation hardening + Monday rollup email (leaderboard included)
- **E5** — Teams Adaptive Cards via Power Automate Workflow (with @mentions)
- **E6** — WhatsApp Cloud API utility template (start Meta template approval early!)
