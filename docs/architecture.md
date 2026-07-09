# GLPI Nagbot — Architecture

**Version:** 1.0 · **Date:** 2026-07-09 · **Status:** approved for Epics 1–3

## 1. Overview

A single container runs everything: APScheduler fires the weekday nag run and the Monday
rollup; FastAPI serves the dashboards; both share a SQLite database on a mounted volume.
GLPI is accessed read-only through its REST API once per run.

```
                ┌───────────────────────── container ─────────────────────────┐
 cron (APSched) │  execute_nag_run()                                          │
   mon-fri 8:00 │  GLPI fetch → metrics/tiers → snapshots → drop snoozed      │
        ────────▶  → group by owner → escalation streaks → digests            │
                │  → adapters (email live · teams stub · whatsapp stub) → log │
   GLPI REST ◀──┤                                                             │
                │  FastAPI: / (WIP) /ops /tickets/{id} /preview /run-now      │
                │           /healthz (auth-exempt)                            │
                │  SQLite (/data/nagbot.db, WAL)                              │
                └─────────────────────────────────────────────────────────────┘
```

**Key invariants**

- Dry-run is the hard default: effective `dry_run = env.NAGBOT_DRY_RUN OR yaml.channels.dry_run` — either source can force it on; only both agreeing turns it off.
- All datetimes are timezone-aware UTC internally; GLPI's naive strings are localized with `glpi.server_timezone` on ingest; display uses the app timezone.
- Every time-dependent function takes `now: datetime` explicitly.
- A per-digest failure is logged and skipped, never fatal to the run. `max_instances=1` + a module-level `threading.Lock` prevent cron/run-now overlap.

## 2. Repo layout

```
pyproject.toml            # hatchling; runtime: fastapi, uvicorn[standard], apscheduler,
                          # httpx, pydantic>=2, pydantic-settings, jinja2, pyyaml
                          # dev: pytest, respx, freezegun, ruff, mypy, httpx TestClient
Dockerfile                # python:3.12-slim, non-root, HEALTHCHECK /healthz
docker-compose.yml        # volumes: ./config:/config:ro, nagbot-data:/data
.env.example
config/nagbot.example.yaml
.github/workflows/ci.yml  # ruff + mypy + pytest
docs/                     # BMAD artifacts (prd, architecture, epics/, stories/)
src/nagbot/
  __init__.py             # __version__
  main.py                 # CLI: serve (default) | run-once [--live] | fetch --json | --version
  config.py               # EnvSettings + AppConfig(YAML) → RuntimeConfig
  glpi/client.py          # GlpiClient
  glpi/fields.py          # FieldMap discovery/cache/overrides
  glpi/models.py          # Ticket
  engine/aging.py         # business-day + SLA math (pure)
  engine/tiers.py         # Tier + classify (pure)
  engine/ownership.py     # Owner + resolve/group (pure)
  digest/builder.py       # Digest/Rollup view-models
  digest/renderer.py      # Jinja2 env; email_html/email_text/rollup_html/teams_card
  digest/templates/       # email_digest.html.j2, digest.txt.j2, manager_rollup.html.j2,
                          # teams_card.json.j2, _macros.j2
  channels/base.py        # ChannelAdapter protocol + SendResult
  channels/email.py       # live SMTP adapter
  channels/teams.py       # stub (E5: Power Automate Workflow POST)
  channels/whatsapp.py    # stub (E6: Meta Cloud API)
  store/db.py             # sqlite3 connect + migrations
  store/repo.py           # Store — the only module that touches SQL
  run.py                  # execute_nag_run / execute_rollup_run
  scheduler.py            # APScheduler wiring
  web/app.py              # create_app(); Basic auth middleware; routes
  web/templates/          # base/wip/ops/ticket/preview .html.j2
  web/static/style.css
tests/
  conftest.py             # fixtures: fixed now, tmp store, sample config, fake adapters
  unit/                   # aging, tiers, ownership, config
  glpi/                   # respx tests + fixtures/*.json (recorded shapes)
  golden/                 # rendered digest goldens
  integration/            # dry-run pipeline, web TestClient
```

## 3. Module contracts

### 3.1 config.py

```python
class EnvSettings(BaseSettings):        # secrets & endpoints — env only
    glpi_base_url: str                  # e.g. https://glpi.example.com/apirest.php
    glpi_app_token: SecretStr
    glpi_user_token: SecretStr
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    smtp_from: str | None = None
    teams_webhook_url: SecretStr | None = None
    whatsapp_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_template_name: str | None = None
    dashboard_password: SecretStr | None = None
    nagbot_config_path: Path = Path("/config/nagbot.yaml")
    nagbot_db_path: Path = Path("/data/nagbot.db")
    nagbot_dry_run: bool = True         # HARD DEFAULT
    nagbot_log_level: str = "INFO"

class AppConfig(BaseModel):             # YAML tuning
    timezone: str = "America/Guayaquil"
    schedule: ScheduleCfg               # digest_cron / rollup_cron (5-field cron)
    thresholds: Thresholds              # fresh_max_age_bd=2, aging_stale_bd=2,
                                        # hot_stale_bd=5, on_fire_stale_bd=7,
                                        # sla_due_soon_hours=24, escalation_red_days=3
    holidays: list[date] = []
    channels: ChannelsCfg               # dry_run=True, enabled=["email"]
    glpi: GlpiTuning                    # server_timezone, page_size=100, field_ids={}
    owners: dict[str, OwnerCfg] = {}    # keyed by GLPI login
    groups: dict[str, OwnerCfg] = {}    # keyed by GLPI group name
    fallback: FallbackCfg               # email, rollup_recipients

def load_config(env: EnvSettings | None = None) -> RuntimeConfig
    # merges, validates cross-cutting invariants, fails fast with readable errors:
    #  - "email" enabled  ⇒ smtp_host + smtp_from set
    #  - "teams" enabled  ⇒ teams_webhook_url set        (E5)
    #  - "whatsapp" enabled ⇒ whatsapp_* set             (E6)
    #  - effective dry_run = env OR yaml
```

### 3.2 glpi/

Endpoints (relative to `GLPI_BASE_URL`, always sending `App-Token` header):

| Purpose | Call |
|---|---|
| Open session | `POST /initSession` + `Authorization: user_token <token>` → `session_token` |
| Close session | `GET /killSession` |
| Field discovery | `GET /listSearchOptions/Ticket` |
| Search | `GET /search/Ticket?criteria[0][field]=12&criteria[0][searchtype]=equals&criteria[0][value]=notold&forcedisplay[n]=<uid>&range=a-b` |

```python
class GlpiClient:                        # context manager: __enter__ initSession, __exit__ killSession
    def __init__(self, base_url, app_token, user_token, *,
                 http: httpx.Client | None = None, page_size: int = 100,
                 server_timezone: ZoneInfo): ...
    def list_search_options(self, itemtype="Ticket") -> dict[str, dict]: ...
    def search_open_tickets(self, field_map: FieldMap) -> list[Ticket]: ...
```

- One session per run; `killSession` is best-effort.
- Pagination: request `range=start-(start+page_size-1)`; HTTP 206 + `Content-Range: 0-99/347` ⇒ more pages; 200 ⇒ last page.
- Retries: up to 3 attempts (backoff 1s/2s) on connect errors, 5xx, 429. On GLPI body `ERROR_SESSION_TOKEN_INVALID`: re-init session once and replay.
- `FieldMap` resolves logical names → search-option uids by matching `(table, field)` from `listSearchOptions`; canonical defaults `{id:2, title:1, status:12, date_opened:15, date_mod:19, tech:5, group:8, time_to_resolve:18}`; YAML `glpi.field_ids` overrides beat discovery; discovery payload cached in `field_cache` (24h TTL).
- `Ticket` (pydantic): `id, title, status, date_opened, date_mod, time_to_resolve (all aware UTC or None), tech_names: list[str], group_names: list[str], url` — search rows arrive keyed by uid strings; `FieldMap.to_ticket(row)` normalizes; multi-valued assignee cells (GLPI joins with `$#$` or returns lists) are split.
- Startup check: `GET /` on init failure paths distinguishes GLPI 11 (warn: apirest deprecated) — logged once.

### 3.3 engine/ (pure — no I/O, `now` injected)

```python
# aging.py
class SlaStatus(StrEnum): NO_SLA; OK; DUE_SOON; BREACHED
def business_days_between(start, end, tz, holidays) -> float   # fractional; weekends/holidays = 0
def compute_metrics(t: Ticket, now, thresholds, tz, holidays) -> TicketMetrics
    # age_bd, stale_bd, sla_status, sla_due

# tiers.py
class Tier(StrEnum): FRESH; AGING; HOT; ON_FIRE                # ordering worst-first via TIER_ORDER
def classify(m: TicketMetrics, th: Thresholds) -> Tier
    # ON_FIRE: BREACHED or stale_bd >= on_fire_stale_bd
    # HOT:     DUE_SOON or stale_bd >= hot_stale_bd
    # AGING:   stale_bd >= aging_stale_bd
    # FRESH:   otherwise

# ownership.py
@dataclass(frozen=True)
class Owner: key; kind; display_name; email; teams_id; whatsapp; manager_email
def resolve_owner(t: Ticket, cfg) -> tuple[Owner, list[str]]   # (owner, warnings)
def group_by_owner(scored: list[ScoredTicket], cfg) -> dict[Owner, list[ScoredTicket]]
```

### 3.4 digest/ & channels/

```python
@dataclass class ScoredTicket: ticket; metrics; tier; owner
@dataclass class Digest: owner; generated_at; tickets (worst-first, then oldest);
                         counts: dict[Tier, int]; escalated: list[ScoredTicket]
@dataclass class Rollup: generated_at; per_person: list[PersonWip]; leaderboard; distribution

class Renderer:                          # one Jinja2 Environment (autoescape html)
    def email_html(d) -> str; email_text(d) -> str
    def email_subject(d) -> str          # "⏰ 6 open tickets — 2 OVERDUE, oldest 12d"
    def rollup_html(r) -> str; teams_card(d) -> dict

# channels/base.py
@dataclass class SendResult: channel; recipient; status: "sent|failed|skipped|dry_run"; detail=""
class ChannelAdapter(Protocol):
    name: str
    def send_digest(self, digest, *, dry_run: bool) -> SendResult
    def send_rollup(self, rollup, *, dry_run: bool) -> SendResult

def build_adapters(cfg) -> list[ChannelAdapter]   # from channels.enabled
```

EmailAdapter: multipart/alternative (text+html), `To=owner.email`, `Cc=manager` when
`digest.escalated`; constructor takes `smtp_factory: Callable[[], smtplib.SMTP]` for tests;
dry-run renders fully (render errors surface) but never opens SMTP. Teams/WhatsApp stubs
render/log their payloads and return `dry_run`/`skipped`.

### 3.5 store/

`db.py`: `connect(path)` (WAL, foreign_keys ON), `migrate(conn)` applying `MIGRATIONS:
list[str]` by index; `schema_migrations` records applied versions. `repo.py`: single
`Store` class — `start_run/finish_run`, `save_snapshots`, `log_send`, `active_snoozes(now)`,
`snooze/unsnooze`, `bump_red_streaks(red_ids, run_date) -> list[int]` (ids crossing the
threshold today; resets streaks for non-red), `ticket_history`, `latest_snapshot`,
`recent_runs`, `recent_sends`, `field_cache_get/put`. Dataclasses in/out, no ORM.

Schema (migration 001):

```sql
runs(id PK, started_at, finished_at, trigger, dry_run, status, tickets_seen,
     digests_built, sends_attempted, error)
ticket_snapshots(run_id FK, ticket_id, title, status, date_opened, date_mod, sla_due,
     owner_key, owner_name, tier, age_bd, stale_bd, sla_status, PK(run_id, ticket_id))
send_log(id PK, run_id FK, kind, channel, recipient, cc, owner_key, ticket_ids JSON,
     status, detail, sent_at)
snoozes(ticket_id PK, until, reason, created_by, created_at)
escalations(ticket_id PK, consecutive_red_days, first_red_at, last_red_date, escalated_at)
field_cache(itemtype PK, payload, fetched_at)
schema_migrations(version PK, applied_at)
```

### 3.6 run.py, scheduler.py, web/

```python
def execute_nag_run(cfg, store, adapters, glpi_factory, *, dry_run, trigger,
                    now=None) -> RunReport
def execute_rollup_run(cfg, store, adapters, *, dry_run, now=None) -> RunReport   # E4
def build_scheduler(cfg, nag_job, rollup_job) -> BackgroundScheduler
    # CronTrigger.from_crontab(cfg.schedule.digest_cron, timezone=cfg.timezone)
    # coalesce=True, misfire_grace_time=3600, max_instances=1
```

Web routes (server-rendered Jinja2 unless JSON): `GET /healthz` (JSON, auth-exempt) ·
`GET /` WIP dashboard · `GET /ops` · `GET /tickets/{id}` · `POST /snooze` ·
`POST /unsnooze` · `GET /preview` · `POST /run-now`. Basic auth middleware compares
against `DASHBOARD_PASSWORD` (any username); if the var is unset, non-healthz routes
return 503 with a "set DASHBOARD_PASSWORD" message rather than serving unprotected.

## 4. Coding standards

- Python ≥ 3.11; `ruff check` (rules: E,F,W,I,UP,B,SIM) and `mypy src` clean at all times.
- No module-level clock reads in business logic; `now` flows in from the edge.
- SQL only in `store/`; HTTP only in `glpi/` and `channels/`; templates only via `Renderer`.
- Tests accompany every story; golden files regenerate with `pytest --update-golden`.
- Conventional commit subjects `E{n}-S{m}: {title}` — one commit per story.

## 5. Testing strategy

| Layer | Approach |
|---|---|
| engine/ | Pure-function tables: weekend/holiday spans, exact threshold boundaries, NO_SLA, breach-beats-staleness |
| glpi/ | respx-mocked httpx with recorded JSON shapes: pagination (206→200), re-auth replay, retry on 500/429, discovery matching + cache TTL + override precedence |
| digest/ | Golden files for email HTML/text, teams card, rollup at a frozen timestamp |
| channels/ | Fake `smtp_factory` records; dry-run asserts SMTP never constructed |
| pipeline | tmp SQLite + mocked GLPI + fake SMTP: dry-run rows, live MIME To/CC, snooze exclusion, escalation bumps |
| web | FastAPI TestClient: auth (401/exempt healthz), dashboards from seeded snapshots, snooze round-trip, run-now dry-run default |
