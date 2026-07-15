# Reality-Check Review — Epic 7 Urgent P0 Escalation Spine

**Reviewer role:** reality-check (verify every committed decision was checked against the ACTUAL codebase and current tech, not asserted from training data)
**Spine:** `_bmad-output/planning-artifacts/architecture/architecture-e7-urgent-p0-escalation/ARCHITECTURE-SPINE.md`
**Codebase:** `src/nagbot/`
**Date:** 2026-07-14

---

## Verdict

**PASS with minor gaps.** Every architectural decision was reality-checked against the real code seams — the spine's descriptions of the code match what is actually there, the "absent today" claims (Ticket priority fields, single-ticket fetch) are literally true, and the named OpenWA sidecar tech is real and current. Two low-severity gaps: one wrong inherited-invariant attribution and an unstated assumption about GLPI search-field discoverability for the new priority/urgency/impact fields.

---

## 1. Brownfield ratification — AD-by-AD against real files

Each claim below was verified against the cited file with line evidence.

### `channels/base.py` — ChannelAdapter / SendResult / begin_run — CONFIRMED
- `SendResult(channel, recipient, status, detail="", cc=None)` frozen dataclass — matches spine's inherited-invariant table exactly (`base.py:16-22`).
- `SendStatus = Literal["sent", "failed", "skipped", "dry_run"]` — matches AD "reuse SendResult statuses" convention (`base.py:13`).
- `ChannelAdapter` Protocol with `send_digest` / `send_rollup`; `begin_run` is a **free function using `getattr(adapter, "begin_run", None)`** (`base.py:33-38`) — a duck-typed optional capability. AD-3's claim that `send_alert` is "optional, like `begin_run`" is **accurate**: the codebase genuinely implements optional capabilities via runtime `getattr`, not via the Protocol. Good reality-check.

### `store/repo.py` + `store/db.py` — escalations table + EscalationRow pattern — CONFIRMED
- `CREATE TABLE escalations (ticket_id PK, consecutive_red_days, first_red_at, last_red_date, escalated_at)` (`db.py:66-72`). The new `p0_escalations` shape in AD-4 (`ticket_id` PK + timestamp columns) genuinely **mirrors** this pattern.
- `@dataclass(frozen=True) EscalationRow` (`repo.py:83-89`) — the frozen `*Row` convention the spine cites is real.
- Migrations are a plain numbered `MIGRATIONS: list[str]` runner, no Alembic (`db.py:9-84`, `95-109`). AD-4's new table slots into this exactly; adding a "003" migration is the real mechanism. Not spelled out in the spine but consistent with it.
- **Single-writer note is aspirational, not enforced:** the store is a shared `Store` with a `threading.Lock` (`repo.py:95`); nothing in the code prevents the digest run from writing `p0_escalations`. AD-4's "only `engine/escalation.py` writes it" is a *convention to uphold*, correctly flagged as a Consistency Convention rather than a code-enforced guarantee. Honest.

### `glpi/models.py` — Ticket has NO priority/urgency/impact — CONFIRMED (literally true)
- `Ticket` fields are `id, title, status, date_opened, date_mod, time_to_resolve, tech_names, group_names, url` (`models.py:21-30`). **No priority, urgency, or impact.** AD-5's "absent today" and the source-tree "+priority/urgency/impact" are accurate.
- `STATUS_LABELS` maps 1..6 (New/Processing/Pending/Solved/Closed) (`models.py:11-18`) — AD-6's "resolved/closed" re-validation has real status semantics to check against (5=Solved, 6=Closed), and AD-7's "auto-move status" has a real target space. Reality-checked.

### `glpi/client.py` — batch-only, no get_ticket — CONFIRMED (literally true)
- Only ticket-fetch method is `search_open_tickets(field_map)` doing paginated `/search/Ticket` (`client.py:164-195`). **There is no `get_ticket(id)` / no `/Ticket/{id}` GET.** AD-6's "client is batch-only today" and the new-method claim are accurate.
- Client is explicitly **"Read-only by design. One session per nag run — the client is a context manager"** (`client.py:1-4`, `__enter__`/`__exit__` at `59-77`). This is a **real design tension the spine under-states** (see finding F3): AD-6 wants a fresh single-fetch immediately before *every* rung dispatch inside a 1-min loop, but the client opens+kills a GLPI session per `with` block. Cheap-per-call but a session churn pattern not present today.

### `config.py` — EnvSettings vs AppConfig split, Thresholds pattern — CONFIRMED
- `EnvSettings(BaseSettings)` holds secrets/endpoints (`glpi_*`, `smtp_*`, `teams_webhook_url`, `whatsapp_*`) (`config.py:26-53`); `AppConfig(BaseModel)` holds tunables (`config.py:110-121`); `RuntimeConfig` is `frozen=True` (`config.py:133-136`). Matches the inherited-invariant table exactly.
- `Thresholds` (`config.py:68-74`) with `escalation_red_days: int = 3` — the "Thresholds pattern" AD-5 says `EscalationCfg` follows is real. Adding `EscalationCfg` to `AppConfig` and `OPENWA_URL` to `EnvSettings` is a clean fit.
- `OwnerCfg.manager: str | None` exists (`config.py:94`) — the Open Question "extend `OwnerCfg.manager` into an ordered `escalation_chain`" references a **real field**. Reality-checked.
- Note: `ChannelName = Literal["email", "teams", "whatsapp"]` (`config.py:19`). Adding an `openwa` channel means extending this Literal + `build_adapters` (`base.py:41-72`). Minor, unstated in spine, but implied by "channels/openwa.py NEW".

### `run.py` — _RUN_LOCK — CONFIRMED
- `_RUN_LOCK = threading.Lock()` module-level, non-blocking acquire, "busy" report on contention (`run.py:24`, `93-99`). AD-1's "never share `_RUN_LOCK`; use a dedicated `_ESCALATION_LOCK`" correctly reflects that the existing lock is a single global run lock and a second loop must not reuse it. Accurate.

### `scheduler.py` — APScheduler — CONFIRMED
- `BackgroundScheduler` (APScheduler) with `CronTrigger.from_crontab`, `coalesce/misfire_grace_time/max_instances=1` (`scheduler.py:7-34`). AD-1's "a new APScheduler job under `escalation_cron`" is a real, minimal extension of `build_scheduler`. Note: existing jobs are **cron** triggers; a ~1-min cadence is expressible as cron (`* * * * *`) — feasible, correctly marked `[ASSUMPTION]`.

### `web/app.py` — FastAPI + auth middleware for the webhook — CONFIRMED, with a caveat
- FastAPI app factory with an `@app.middleware("http")` **Basic-auth** middleware guarding everything except `AUTH_EXEMPT_PREFIXES = ("/healthz", "/static", "/public")` (`app.py:44-51`, `123-136`).
- The spine's convention "the OpenWA webhook is authenticated; `AUTH_EXEMPT` **not** applied" is **correct and important**: by default any new `/webhooks/openwa` route WOULD be caught by the Basic-auth middleware. **Caveat (F2):** the existing auth is HTTP **Basic** (username:password), designed for a human dashboard operator, not a machine webhook. OpenWA's `-w` webhook POSTs to a URL; making it send a Basic-auth header (or the spine's alternative "shared secret") is an *added* mechanism — the current middleware only knows Basic. The spine says "shared secret/`AUTH_EXEMPT` not applied" which acknowledges a *new* auth path is needed; this is directionally right but the reuse is less clean than "reuse the E3 FastAPI app" implies.

**No AD misdescribes the code.** All seam descriptions are faithful.

---

## 2. Tech currency

### OpenWA sidecar — CONFIRMED REAL & CURRENT (web-verified 2026-07-14)
- `openwa/wa-automate` is a real, published Docker image (Docker Hub `hub.docker.com/r/openwa/wa-automate`; repo `github.com/open-wa/wa-automate-docker`).
- Exposes an **HTTP API** (default internal port 8080) — matches AD-2's "exposes its HTTP API" and the `httpx → OPENWA_URL` client.
- The **`-w` flag sets a webhook** (`docker run ... openwa/wa-automate -w <url> --socket`) — matches AD-7's "OpenWA `-w` webhook delivers the inbound reply." Confirmed from the vendor docs/README, not training data.
- The research doc (`research/technical-whatsapp-...`) already primary-source-verified that OpenWA has **only `onIncomingCall` (no outbound call API)** — consistent with the spine correctly **deferring** the call rung.
- `[ASSUMPTION] pin a specific tag` is the right call — the image publishes a `latest` and the WA-Web-breakage risk is real (called out in research). Good.

### APScheduler / FastAPI / httpx already in the project — CONFIRMED
Verified in `pyproject.toml` dependencies:
- `fastapi>=0.111`, `apscheduler>=3.10,<4`, `httpx>=0.27` — all three are **genuinely already declared and imported** (`scheduler.py`, `web/app.py`, `glpi/client.py`). The Stack table's "existing (reused)" for each is accurate.
- SQLite WAL: `PRAGMA journal_mode=WAL` (`db.py:90`) — "existing store" accurate.
- **Stack table says Python 3.13; `pyproject.toml` says `requires-python = ">=3.11"` and mypy `python_version = "3.11"`.** Minor: the spine over-specifies the runtime as 3.13 (existing) when the project floor is 3.11. Non-blocking (3.13 is a valid runtime), but "3.13 (existing)" is not what the project pins. See F4.

---

## 3. Decisions that only work if a library behaves a certain way but weren't verified

- **AD-6 fresh single-fetch (`GlpiClient.get_ticket`)** — the *method* doesn't exist yet (correctly stated), but the deeper unverified assumption is that a per-rung fetch is cheap enough given the client's **one-session-per-context-manager, kill-on-exit** design (`client.py:59-77`). Re-authing GLPI on every rung of every P0 every minute is a behavior not exercised today. **Flagged as F3 (medium).** GLPI apirest.php supports a direct `GET /Ticket/{id}` (standard), so the API itself is fine — the risk is session-lifecycle churn, not API existence.
- **APScheduler 1-min cadence** — APScheduler `CronTrigger` supports `* * * * *`; with `max_instances=1` + `coalesce=True` a slow tick is skipped, not stacked. Behavior is standard and consistent with existing job config. No unverified dependency. OK.
- **FastAPI middleware ordering for the webhook** — the Basic-auth middleware wraps *all* routes; a webhook needing a different auth scheme must branch inside/around it. Behavior is understood (F2), not an unverified library assumption.
- No decision rests on an *unverified* library behavior that would silently break. The OpenWA HTTP-API + `-w` webhook shape — the one external dependency most likely to be asserted from memory — was independently web-confirmed.

---

## Findings (severity-ranked)

| # | Sev | Finding |
|---|-----|---------|
| F1 | LOW | **Mis-attributed inherited invariant.** The spine attributes the `ChannelAdapter` port to "E2-S5 (`channels/base.py`)". The channel-adapter pattern per the research doc is Teams=Epic 5, WhatsApp=Epic 6; `begin_run` (WhatsApp rate-cap reset) is an Epic-6 artifact. The `(E2-S5)` provenance tag looks asserted, not checked. Code content is right; the *source citation* is likely wrong. Fix the binding label. |
| F2 | LOW-MED | **Webhook auth reuse is less clean than stated.** Existing `web/app.py` auth is HTTP **Basic** for a human operator (`app.py:66-74`, `123-136`). The OpenWA `-w` webhook is a machine caller; authenticating it means adding a shared-secret/token path the current middleware doesn't have. The spine's "authenticated; `AUTH_EXEMPT` not applied" is directionally correct and the risk is acknowledged, but "reuse the E3 FastAPI app" understates that a *new* auth mechanism (not the existing Basic middleware) is required. Make the shared-secret path an explicit sub-decision in E7-S4. |
| F3 | MED | **AD-6 per-rung re-fetch vs. one-session-per-run client.** `GlpiClient` is "read-only, one session per nag run," opening+`killSession` per `with` block (`client.py:1-4`, `59-77`). AD-6 mandates a fresh `get_ticket` immediately before *every* rung dispatch on a ~1-min loop — a GLPI session-churn / re-auth pattern the codebase does not exercise today and did not reality-check for cost/latency. The `/Ticket/{id}` API exists; the concern is session lifecycle. Recommend E7-S2/S4 decide whether the escalation loop holds one session per tick (fetch all active P0s in the open `with`) rather than one `with` per rung. |
| F4 | LOW | **Stack over-specifies Python 3.13.** `pyproject.toml` pins `requires-python = ">=3.11"` and mypy targets 3.11; the spine's Stack table says "Python 3.13 (existing)". Harmless but not what the project actually declares — reads as asserted. Align to ">=3.11" or note 3.13 is the deploy target, not the floor. |
| F5 | INFO | **`ChannelName` Literal + `build_adapters` must extend for `openwa`.** `config.py:19` and `base.py:41-72` hardcode the three current channels; adding `openwa` requires touching both. Implied by the source tree but not called out. Non-blocking. |

---

## Bottom line

The spine was genuinely reality-checked, not hallucinated. The load-bearing "this does not exist today" claims (Ticket priority/urgency/impact, `GlpiClient.get_ticket`, a second scheduler lock) are all literally true against `src/nagbot/`. The one external tech most at risk of being asserted from memory — the `openwa/wa-automate` Docker image with HTTP API + `-w` webhook — is real and current per vendor docs. The remaining gaps are a citation error (F1), an under-stated auth-reuse nuance (F2), one genuine under-explored design tension around GLPI session churn (F3, the only medium), and a cosmetic Python-version overstatement (F4). None blocks proceeding to stories; F3 should be resolved inside E7-S2/S4.

**Sources (tech currency):**
- OpenWA Docker image: https://hub.docker.com/r/openwa/wa-automate
- OpenWA docker docs (`-w` webhook, port 8080): https://github.com/open-wa/wa-automate-docker
- OpenWA get-started (Docker): https://docs.openwa.dev/docs/get-started/docker
