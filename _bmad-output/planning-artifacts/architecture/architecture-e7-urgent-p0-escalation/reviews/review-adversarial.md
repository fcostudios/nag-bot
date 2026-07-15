---
name: 'Adversarial Architecture Review — Epic 7 Spine'
type: architecture-review
mode: adversarial
target: ARCHITECTURE-SPINE.md (Epic 7 — Urgent P0 Escalation)
reviewer: adversarial-architecture-reviewer
created: 2026-07-14
verdict: CONDITIONAL — the paradigm is sound, but the spine leaves ~7 two-story compatibility holes where both stories obey every AD to the letter yet build incompatibly. Close them before E7-S3/S4 start.
---

# Adversarial Architecture Review — Epic 7 Spine

**Verdict:** CONDITIONAL. The ports-and-adapters + polled-state-machine paradigm is coherent, but the spine's ADs under-specify the *seams between stories*. Multiple story pairs can each be individually AD-compliant and still not compose: `send_log(kind="escalation")` already has a **second, pre-existing writer**; AD-4's "single writer" is contradicted by the dependency diagram's `web --> store` edge; AD-6's failure mode is undefined and can silently stop a live P0; and the dwell/rung math has no defined epoch, so two ticks can double-notify or skip a rung. Each hole below is a concrete pair of Module-1 units that both honor every current AD yet clash.

Grounding facts I verified against `src/nagbot/` (they change the analysis):
- **The store is a single shared `sqlite3.Connection` guarded by one process-level `threading.Lock` (`self._lock`) on writes; reads run unlocked** (`store/repo.py:94-95`). So "single writer" is enforceable *in-process by the lock*, not by table ownership — and the webhook, run loop, and escalation loop all share this one connection object.
- **The digest run ALREADY writes `send_log` with `kind="escalation"`** for manager-CC lines (`run.py:181-192`). This is a live naming collision with AD-7 / the Consistency-Conventions row `kind="escalation"`.
- **Each `with glpi_factory() as client:` opens and kills its own GLPI session** (`glpi/client.py:59-75`). The digest and escalation loops do not share a session token, but a ~1-min escalation loop that calls `get_ticket` per rung will churn GLPI sessions.
- **The FastAPI app runs sync routes in a threadpool** (`web/app.py`); a webhook handler is a *different thread* from the scheduler's escalation-loop thread, both touching the one shared connection.

---

## Hole 1 — AD-4 "single writer" is directly contradicted by the dependency diagram (`web --> store`)

**The two units:** E7-S4 (ack ingestion webhook, `web/app.py`) vs E7-S3 (escalation engine, `engine/escalation.py`).

**The incompatibility.** AD-4's rule: *"Only `engine/escalation.py` writes [`p0_escalations`]."* But the spine's own dependency diagram draws a **solid** edge `web[web: /webhooks/openwa] --> store[(store: p0_escalations)]` and only a **dashed** `web -.ack.-> esc`. Read to the letter, the diagram sanctions the webhook writing `acknowledged_at`/`acknowledged_by` **directly** into `p0_escalations`. That is a flat AD-4 violation, and it is a real lost-update race: the webhook thread can `UPDATE ... SET acknowledged_at=?` at the same wall-clock moment the escalation-loop thread is mid-tick deciding to climb a rung and writing `current_rung`/`last_notified_at`. The process lock serializes the two *statements*, but not the *read-modify-write*: the engine can read "not acked", then the webhook writes "acked", then the engine writes rung N+1 and sends an alert for an already-acked ticket. Cry-wolf.

Both units can be individually AD-compliant: S4 "obeys AD-7" (ingest the reply) by writing the ack where the diagram points; S3 "obeys AD-4" (it's the writer of rung state). They still clash.

**AD fix (tighten AD-4 + correct the diagram).** Make the webhook a *producer of intent, never a writer of `p0_escalations`*. Add to AD-4: *"The webhook records the raw inbound reply into an append-only `p0_ack_inbox` table (its own concern) and does nothing else; `engine/escalation.py` is the sole writer of `p0_escalations` and drains the inbox on its next tick, applying the ack as part of the same locked read-modify-write that advances rung state."* Redraw the diagram edge `web --> p0_ack_inbox` (solid) and delete `web --> p0_escalations`. This makes ack application single-threaded and idempotent-by-construction, and it removes the read-modify-write race entirely.

---

## Hole 2 — `send_log(kind="escalation")` already has a writer; two owners of one log semantic

**The two units:** the **existing** digest run (`run.py:181-192`, manager-CC escalation lines) vs E7-S3/S5 escalation dispatch (Consistency-Conventions row: *"every dispatch logged to `send_log` (`kind="escalation"`)"*).

**The incompatibility.** `send_log` rows are keyed on `run_id` (FK to `runs`) and carry `kind`. The digest run writes `kind="escalation"` rows *inside a `runs` row it created*. The P0 escalation loop has **no `run_id`** — it's a per-tick state-machine advance, not a `runs` row. So the escalation loop either (a) invents a fake `runs` row per tick (pollutes the ops "runs" list, breaks `last_run`/rollup which read "latest run"), or (b) writes `send_log` with `run_id=NULL` — but then the ops dashboard's `recent_sends`/`sends_for_ticket` queries and any `JOIN runs` mix two totally different "escalation" concepts (aging-streak manager CC vs urgent-P0 rung) under one `kind`, and `/tickets/{id}` history conflates them. Both are "correct" per their AD, and the reader can no longer tell a P0-rung alert from a red-streak CC.

**AD fix (new AD or tighten Consistency-Conventions).** Reserve a distinct `kind` and define the `run_id` contract: *"P0 escalation dispatches log with `kind="p0_alert"` (NOT `"escalation"`, which is owned by the digest red-streak CC), `run_id=NULL`, and MUST carry `ticket_id` + `current_rung` + `channel` in structured columns. `send_log.run_id` is nullable for engine-originated rows; all readers (ops, ticket history) MUST branch on `kind` and never assume a `runs` row exists."* Add a nullable `escalation_ticket_id`/`rung` column pair, or a dedicated `p0_send_log`, so the two escalation semantics never share a filter.

---

## Hole 3 — AD-6 has no defined behavior when `get_ticket` fails; a real P0 can be silently starved or the engine can spin

**The two units:** E7-S2 (`GlpiClient.get_ticket` + P0 verify) vs E7-S3/S4 (the tick loop that calls re-validate before *every* rung).

**The incompatibility.** AD-6: *"immediately before every rung dispatch the engine re-fetches the ticket via `get_ticket(id)` and re-verifies... Any of resolved/closed/reassigned/downgraded → stop instantly."* AD-1: *"each tick is idempotent... derives all actions from durable state + live GLPI."* Neither AD says what happens when `get_ticket` **raises** (GLPI down, 500, timeout, session expired). Three readings are all "AD-compliant":
- **Treat fetch-failure as a stop condition** → a GLPI blip permanently kills a genuine P0 climb (violates north-star: silently stops a real fire). S3 could reasonably implement this because "can't verify P0 → don't cry wolf."
- **Treat fetch-failure as skip-this-tick** → correct, but undefined how many consecutive skips before the dwell clock is considered "paused" vs "elapsed"; a 20-minute GLPI outage means the P0 sits un-escalated with no visibility.
- **Retry inside the tick** → risks the ~1-min tick overrunning into the next tick (APScheduler `max_instances=1` on the digest job coalesces, but the spine hasn't stated the escalation job's `max_instances`/`coalesce`/`misfire_grace_time`).

Because the behavior is undefined, S2 and S3 can be built against *different* readings and disagree at runtime. That is the hole.

**AD fix (tighten AD-6, add a transient-error clause).** *"`get_ticket` failure is NEVER a stop reason. On fetch error the engine leaves state unchanged, does not advance the rung, does not send, records `last_validation_error`/`last_validation_at`, and re-tries on the next tick. A stop is set ONLY on a *successful* fetch that shows resolved/closed/reassigned/downgraded. If validation has failed continuously for `validation_grace` (config, default e.g. 15 min), raise an ops alert ('P0 escalation blind: GLPI unreachable') rather than silently stopping."* Also pin the escalation job's scheduler policy in AD-1: `max_instances=1, coalesce=True, misfire_grace_time=<one dwell>`.

---

## Hole 4 — AD-3 optional `send_alert` + AD-7 Teams fallback: "OpenWA failed" is undefined, so dispatch order and fallback are non-composable

**The two units:** E7-S1 (`OpenWaAdapter.send_alert`) + E7-S5 (`TeamsAdapter.send_alert`) vs E7-S3 (engine dispatch, which "dispatches only via `send_alert`").

**The incompatibility.** AD-3: adapters *MAY* implement `send_alert`; *"email/whatsapp-cloud may no-op."* AD-7: *"If an OpenWA `send_alert` fails or the session is down, the engine dispatches the same alert via Teams."* Three unresolved seams:
1. **What is "failed"?** The existing contract returns `SendResult(status ∈ sent/failed/skipped/dry_run)` — it does not raise. A no-op adapter returns `skipped`. So does the engine fall back to Teams on `failed` only, or also on `skipped`? If OpenWA is *configured but the WA-Web session is down*, does the adapter return `failed` (fall back — good) or does it hang? AD-7 says "or the session is down" but nothing defines a **send timeout**: a *slow* OpenWA send (session reconnecting) blocks the tick with no deadline, so "OpenWA send failed → fall back to Teams" never triggers and the tick overruns. Slow ≠ failed is undefined.
2. **Dispatch order / dedupe.** If OpenWA returns `sent` but the message silently never arrives, no fallback. If OpenWA returns `failed` *after* partially sending, Teams double-notifies. The engine has no idempotency key tying "this rung's alert" across the two channels, so a retry-after-ambiguous-failure can double-fire across channels.
3. **Capability discovery.** AD-3 says the engine "dispatches only via `send_alert`," but `send_alert` is optional (`getattr`, like `begin_run`). If the configured escalation channel's adapter lacks `send_alert`, the engine has *no* dispatch path and the rung silently no-ops — a P0 with zero alerts, fully AD-compliant.

**AD fix (tighten AD-3 + AD-7).** Define the fallback contract precisely: *"`send_alert` MUST return within `alert_send_timeout` (config, default e.g. 10s); exceeding it is treated as `failed`. The engine falls back to Teams on `failed` OR timeout, NEVER on `skipped` (a `skipped`/no-op adapter means 'not my channel' and is transparent). Each rung dispatch carries an `alert_key = (ticket_id, rung)`; adapters and `send_log` dedupe on it so a fallback after ambiguous failure cannot double-notify. At engine construction the escalation chain MUST resolve to at least one adapter that implements `send_alert`, else fail fast at startup — a rung with no dispatch path is a config error, not a silent no-op."*

---

## Hole 5 — Dwell/rung math has no defined epoch or elapsed-basis; two ticks can double-notify or skip a rung despite `last_notified_at`

**The two units:** E7-S3 (rung-advance logic: dwell + back-off curve) vs E7-S3/S4 (the idempotent tick guarded by `last_notified_at`).

**The incompatibility.** AD-1 claims `last_notified_at` + dwell make double-notify impossible. But the spine never states *the elapsed-time basis*:
- **Basis = `now - last_notified_at`** vs **basis = `now - p0_detected_at` mapped onto a cumulative rung schedule.** These diverge. If a tick is *missed* (GLPI outage, coalesce), the `now - last_notified_at` basis will, on the next tick, see "dwell hugely exceeded" and climb exactly **one** rung — but two full dwell periods have elapsed, so the ticket is now a rung *behind* where the schedule says it should be (a real P0 escalates too slowly). Conversely if the loop runs slightly fast / clock skews backward (NTP step, container clock), `now - last_notified_at` can read as elapsed on the *same* logical dwell twice → **double-climb / double-notify**, defeating the very guard AD-1 relies on.
- **The guard is `last_notified_at`, but the write of `last_notified_at` and the send are not atomic w.r.t. crash.** If the process dies after `send_alert` returns `sent` but before the `UPDATE last_notified_at` commits, the next tick re-sends the same rung. If it writes `last_notified_at` first and the send fails, it skips a rung. AD-1 says "idempotent" but the ordering that makes it so is unspecified.
- **`current_rung` can skip.** With a back-off curve, if two dwell windows pass in one tick gap, does the engine emit rung N+1 *and* N+2, or jump to N+2 silently? Both are AD-compliant; they produce different alert histories and different "did the manager get paged" outcomes.

**AD fix (new AD-8, "escalation clock").** *"Rung timing is computed from a single monotonic-per-ticket epoch: the target rung for `now` is the highest rung whose cumulative dwell-from-`p0_detected_at` has elapsed, using UTC-aware `now` injected into the pure engine (never wall-clock read twice per tick). A tick advances AT MOST one rung per tick even if multiple dwells elapsed (never batch-fire), and re-computes the target each tick so a slow schedule self-heals without skipping. The send→state-write ordering is: (1) compute intent, (2) `send_alert`, (3) on `sent`/`failed` write `last_notified_at=now` + `current_rung` in the SAME locked transaction; a crash between (2) and (3) is reconciled on next tick by comparing `send_log` (alert_key) to `p0_escalations` — send_log is the source of truth for 'was this rung dispatched.' Clock must be monotonic-guarded: if injected `now < last_notified_at`, treat dwell as not-yet-elapsed."*

---

## Hole 6 — AD-1 escalation loop vs the digest `_RUN_LOCK` run: concurrent unlocked reads + FieldMap cache write race

**The two units:** the existing digest run (`_RUN_LOCK`, `fetch_and_score` → `FieldMap.discover(..., cache=store)`) vs E7-S2/S3 escalation loop (`_ESCALATION_LOCK`, also needs field discovery for priority/urgency/impact).

**The incompatibility.** AD-1 correctly separates the two *locks* so they don't deadlock. But they are **not** isolated in the store:
- **`send_log` concurrent writes are safe** (verified: single connection + `self._lock` serializes writes; WAL handles durability) — so that specific worry from the brief is *closed by the existing design*. State this explicitly so nobody "fixes" it into a second connection and reintroduces the race.
- **`field_cache` IS a shared-write hazard.** Both loops call `FieldMap.discover(..., cache=store)`. E7-S5/AD-5 requires *extending* discovery to fetch `priority`/`urgency`/`impact`. If the escalation loop discovers-and-caches a FieldMap that includes the new fields, and the digest run (older code path, or a stale cache read) reads/overwrites `field_cache` for the same `itemtype="Ticket"` with a *different-shaped* payload, the two loops fight over one cache row — a **clashing shared-data shape** on `field_cache.payload`. One loop's write can strip fields the other needs. Both obey their ADs; the cache row has two owners with two schemas.
- **Reads run unlocked** (`store/repo.py`: `escalations()`, `latest_snapshot()`, etc. have no `self._lock`). A webhook or dashboard read of `p0_escalations` mid-write sees WAL-consistent rows (fine), but any *multi-statement* read the engine does (e.g. read inbox + read escalation row) is not a snapshot — interleaves with the other loop's writes.

**AD fix (tighten AD-4/AD-5 + Consistency-Conventions).** *"`field_cache` payload is versioned and additive: the escalation and digest paths MUST share one FieldMap schema that is a superset (priority/urgency/impact added, never a divergent shape); the cache key includes a schema version so a mixed-version deployment can't overwrite a richer payload with a poorer one. `send_log` durability under two loops is guaranteed by the single-connection + process-write-lock store; adapters and engine MUST NOT open a second SQLite connection. Any engine read that spans multiple statements (inbox drain + rung read) MUST occur inside one locked transaction so it is a consistent snapshot."*

---

## Secondary hole — Webhook auth + ack authenticity (AD-7)

**The two units:** E7-S4 webhook (`/webhooks/openwa`) vs E7-S3 engine (which trusts the ack to halt a climb).

The Consistency-Conventions row requires the webhook be authenticated (shared secret, not `AUTH_EXEMPT`). Good — but AD-7 lets an ack reply *auto-move GLPI status* and *halt escalation*. Two undefined seams: (1) **which inbound number/sender is authoritative** — any WhatsApp reply to the sidecar hits the webhook; the engine must verify the reply came from the *rostered recipient of that ticket's current rung*, not any number, or a wrong-number "ok" silences a real P0; (2) the webhook is `is_auth_exempt`-excluded, but the current middleware only does *Basic auth against the dashboard password* — the spine must specify a **separate** shared-secret path for the webhook, since the OpenWA sidecar can't send Basic dashboard creds.

**AD fix.** Add to AD-7: *"An inbound ack is honored only if the sender maps to the ticket's rostered on-call at the acked rung (or higher); unmatched replies are logged and ignored, never halt. The webhook authenticates via a dedicated `OPENWA_WEBHOOK_SECRET` (constant-time compare), independent of `DASHBOARD_PASSWORD`."*

---

## Summary table

| # | Two units that clash | AD each obeys | Fix |
|---|---|---|---|
| 1 | webhook (S4) vs engine (S3) | AD-7 / AD-4 | Webhook writes `p0_ack_inbox` only; engine drains it. Delete `web-->p0_escalations` diagram edge. |
| 2 | existing digest CC (run.py) vs P0 dispatch (S3/S5) | Conventions `kind="escalation"` on both | Reserve `kind="p0_alert"`, define nullable `run_id`, structured `ticket_id`/`rung`. |
| 3 | `get_ticket` (S2) vs tick loop (S3/S4) | AD-6 / AD-1 | Fetch-failure = never a stop; skip-tick + `validation_grace` ops alert; pin scheduler policy. |
| 4 | OpenWA/Teams `send_alert` (S1/S5) vs engine (S3) | AD-3 / AD-7 | Define timeout=failed, fall back on failed/timeout not skipped, `alert_key` dedupe, fail-fast if no `send_alert` in chain. |
| 5 | rung math (S3) vs `last_notified_at` guard (S3/S4) | AD-1 | New AD-8 escalation clock: cumulative-dwell-from-epoch, ≤1 rung/tick, send-then-write ordering, monotonic guard. |
| 6 | digest run vs escalation loop | AD-1 lock split / AD-5 discovery | Versioned additive `field_cache` schema; forbid 2nd SQLite connection; multi-statement reads in one locked txn. |
| 7 (sec.) | webhook (S4) vs engine trust (S3) | AD-7 / Conventions auth | Sender-must-match-roster; dedicated `OPENWA_WEBHOOK_SECRET`. |
