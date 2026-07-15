---
baseline_commit: feff866daeea65b9d66c30c4f20f1dbe46fb29ab
---

# E7-S3: Escalation roster + climbing ladder

Status: done

<!-- bmad create-story. Spine: AD-1 (loop+lock), AD-3 (send_alert dispatch), AD-4 (single-writer p0_escalations), AD-5 (is_p0 gate), AD-8 (cumulative/monotonic/send-before-write clock). Epic: docs/epics/e7-urgent-p0-escalation.md. Builds on E7-S1 (OpenWaAdapter.send_alert + EscalationAlert) and E7-S2 (is_p0/detect_p0s + EscalationCfg). -->

## Story

As **the on-call team**,
I want **nagbot to open an escalation for each genuine P0 and climb the roster (owner → manager → default triage) on a timed cadence until the top rung**,
so that **a real P0 keeps getting louder until a human is reached — without ever escalating a ticket that is no longer a P0**.

## Context

- **Heart of Epic 7.** Turns the E7-S2 P0 predicate + the E7-S1 transport into a running, stateful, climbing escalation. It is deliberately **scoped**: it does NOT do inbound ack ingestion (webhook) or the single-ticket `get_ticket` refetch (E7-S4), nor Teams fallback (E7-S5). Re-validation in S3 uses the **current fetch** (a ticket that is no longer in the P0 set this tick is stopped).
- **Spine (binding):** AD-1 (own APScheduler job + `_ESCALATION_LOCK`, idempotent tick); AD-3 (dispatch via `send_alert` down `alert_channels`); AD-4 (only the engine writes `p0_escalations`); AD-5 (`is_p0` is the gate); AD-8 (target rung = cumulative `now − p0_detected_at` / dwell; **≤1 dispatch per tick**; **send-then-persist**; monotonic).
- **Reuse:** `engine/p0.is_p0/detect_p0s`, `EscalationCfg`, `channels.EscalationAlert` + `OpenWaAdapter.send_alert`, `run.fetch_and_score`, `ownership.resolve_owner`/`Owner`, the `escalations`/`EscalationRow` store pattern, `scheduler.build_scheduler` (`coalesce/misfire_grace_time/max_instances=1` already used).

## Acceptance Criteria

- **AC1 (store, AD-4):** migration 003 creates `p0_escalations(ticket_id PK, p0_detected_at, current_rung, last_notified_at, acknowledged_at, acknowledged_by, stopped_reason, stopped_at)`; `P0EscalationRow` dataclass + accessors `active_p0_escalations()` (stopped_at IS NULL), `upsert_p0_escalation(row)`, `stop_p0_escalation(ticket_id, reason, now)`. Follows the existing `escalations` pattern (lock + `_conn`).
- **AC2 (roster):** a pure `escalation_chain(ticket, cfg) -> list[Recipient]` where `Recipient(name, whatsapp)`: rung 0 = the ticket **owner**; rung 1 = the owner's **manager** (resolved by matching `owner.manager_email` to a configured owner, to get their whatsapp); rung 2 = **default triage** (`EscalationCfg.default_triage`, an owner key or E.164). Rungs that resolve to no whatsapp are still present (recorded) but yield no dispatch. Empty/duplicate rungs collapse sensibly.
- **AC3 (engine, AD-5/AD-8):** a pure `escalation_tick(*, p0_tickets, active, cfg, now) -> TickResult` (no I/O, `now` injected):
  - **Open:** a P0 ticket with no active escalation → new `P0EscalationRow(p0_detected_at=now, current_rung=0)` and an alert for rung 0.
  - **Climb:** target rung = `min(floor((now − p0_detected_at)/dwell), len(chain)−1)`; if target > current_rung, climb by **exactly one** rung this tick and emit its alert (cumulative catch-up but ≤1 dispatch/tick).
  - **Hold:** at the top rung, no further climb.
  - **Stop (AD-5 gate):** an active escalation whose ticket is **not** in this tick's P0 set → stop with `reason="resolved_or_downgraded"`, no alert.
- **AC4 (dispatch order, AD-8):** the runner **sends first, then persists** — an alert that fails to send does not advance `current_rung`/`last_notified_at` (so it retries next tick); `send_log` (kind `p0_alert`) records each attempt. The engine returns intended actions; the runner performs send→persist.
- **AC5 (alert content):** the alert text carries **system/category, time reported, what's broken (title), and the ticket link** (mirrors the E7-S2 brief content), plus a rung/"escalating" marker so a climb reads as escalating.
- **AC6 (loop, AD-1):** a new `execute_escalation_run(...)` runner under a module-level `_ESCALATION_LOCK` (separate from `_RUN_LOCK`): `fetch_and_score → detect_p0s(is_p0) → load active → escalation_tick → send via alert adapters → persist`. A new scheduler job (`escalation`, short interval from `EscalationCfg`, `max_instances=1, coalesce`) is added **only when `cfg.escalation.enabled`**. Dry-run aware.
- **AC7 (safe + configurable):** with `escalation.enabled=False` (default) no job is scheduled and nothing escalates. `dwell_minutes` and `default_triage` and `alert_channels` are config, not hardcoded. Nothing here writes to the digest tables or calls the digest run.
- **AC8:** no regressions; `ruff` + `mypy` + full suite green.

## Tasks

- [x] `src/nagbot/store/db.py` + `repo.py` — migration 003 + `P0EscalationRow` + 3 accessors (AC1).
- [x] `src/nagbot/config.py` — `EscalationCfg` gains `dwell_minutes: float = 5.0`, `default_triage: str | None = None`, `alert_channels: list[str] = ["openwa"]`, `cadence_seconds: int = 60` (AC2, AC6, AC7).
- [x] `src/nagbot/engine/escalation.py` — NEW `Recipient`, `escalation_chain`, `EscalationAction`/`TickResult`, `escalation_tick`, `build_alert_text` (AC2, AC3, AC5). Pure, `now`-injected.
- [x] `src/nagbot/run.py` + `scheduler.py` — `execute_escalation_run` + `_ESCALATION_LOCK` + the conditional `escalation` job (AC4, AC6, AC7).
- [x] `tests/unit/test_escalation.py` + `tests/unit/test_p0_store.py` — engine tick scenarios (open/climb/hold/stop, ≤1/tick, cumulative catch-up), roster resolution, alert text, store round-trip; a runner test with a fake store + fake alert adapter for send-then-persist + dry-run (AC1–AC7).

## Dev Notes

- **AD-8 clock:** target rung is a function of `now − p0_detected_at` (cumulative — a missed tick catches up), but climb **at most one rung per tick**; compute elapsed with a monotonic-safe comparison (all times UTC-aware; `now` injected). `last_notified_at` guards re-sending the same rung within a tick.
- **Send-then-persist (AD-4/AD-8):** engine is pure and returns `(alerts, upserts, stops)`; the runner sends each alert, and only on a non-failed `SendResult` persists the matching `upsert`/rung bump. This makes a crash-between-send-and-write re-send at worst once, and a send failure simply retries next tick.
- **Dispatch (AD-3):** iterate `cfg.escalation.alert_channels` (default `["openwa"]`); the adapter must implement `send_alert` (getattr, like `begin_run`); a `sent`/`dry_run` stops, `failed`/timeout/`skipped` falls through; if none implement it → config error (fail fast). Teams is added to the chain in E7-S5.
- **Roster manager lookup:** `Owner.manager_email` is an email; to WhatsApp the manager, find a `cfg.owners` entry whose `email == manager_email` and use its `whatsapp`. If absent, rung 1 has no whatsapp (recorded, skipped). Keep `escalation_chain` pure and unit-tested.
- **Re-validation scope:** S3 stops on "no longer in the P0 set this fetch". The AD-6 single-ticket `get_ticket` refetch + ack sources are E7-S4 — do not build them here. Leave `acknowledged_at`/`acknowledged_by` columns present but unset.
- **Do NOT** touch the digest run / `_RUN_LOCK`. Use a distinct `_ESCALATION_LOCK`.

### Project Structure Notes

- New `engine/escalation.py` (finally created — reserved since S1). New store table + rows. Config additions. Scheduler gains one conditional job. No change to digest behavior.

### References

- [Source: architecture spine AD-1/AD-3/AD-4/AD-5/AD-8]
- [Source: src/nagbot/store/db.py:66-72 (escalations table pattern), repo.py:84-90 (EscalationRow), 93-99 (Store init/lock)]
- [Source: src/nagbot/engine/p0.py (is_p0/detect_p0s), engine/ownership.py:22-53,76 (Owner/resolve_owner/manager)]
- [Source: src/nagbot/channels/openwa.py + base.py EscalationAlert (E7-S1); run.py fetch_and_score; scheduler.py build_scheduler]

## Testing

`pytest`. Engine tests are pure (inject `now`, build `Ticket`s + `P0EscalationRow`s); store test uses a tmp SQLite; runner test uses fakes.

- **open/climb/hold/stop:** new P0 → rung-0 alert + row; after `dwell` → climb to rung 1 (exactly one); after `2·dwell` with a missed tick → still climbs only one rung/tick; at top rung → hold; ticket absent from P0 set → stop, no alert.
- **roster:** owner/manager/triage resolution incl. missing manager whatsapp and default_triage as key vs E.164.
- **alert text:** contains system, time, title, link, and an escalating marker.
- **send-then-persist:** a failed `send_alert` → no rung bump (retry next tick); dry-run → `dry_run`, no persist of a real send but state may advance per policy (assert chosen behavior).
- **store round-trip:** upsert → active list → stop; migration applies.
- **safety:** `enabled=False` → `build_scheduler` adds no escalation job.

Run `python -m pytest -q`; `ruff check`; `mypy src/nagbot`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (dev-story workflow)

### Completion Notes List

- `engine/escalation.py`: pure `escalation_chain` (owner→manager→triage, dedup, unreachable rungs recorded) + `escalation_tick` (open/climb-one-per-tick/hold/stop, AD-8 cumulative catch-up, AD-5 stop-when-not-P0) + `build_alert_text` + `dispatch_alerts` (AD-3 channel fallback, AD-4/AD-8 send-then-persist; failed → no rung bump).
- store: migration 003 `p0_escalations` + `P0EscalationRow` + `active_p0_escalations`/`upsert_p0_escalation`/`stop_p0_escalation` (single-writer).
- config: `EscalationCfg` gains `dwell_minutes`/`cadence_seconds`/`default_triage`/`alert_channels`.
- run/scheduler: `execute_escalation_run` under a distinct `_ESCALATION_LOCK`; `build_scheduler` adds the `escalation` interval job ONLY when `enabled` (max_instances=1, coalesce); `make_jobs` returns it.
- Scope kept: no ack ingestion / `get_ticket` refetch (E7-S4), no Teams alert channel (E7-S5). `acknowledged_*` columns present but unset.
- 14 tests (roster, tick open/climb/hold/stop/≤1-per-tick, alert text, store round-trip, send-then-persist incl. failed/dry-run/fail-fast). Suite 186; ruff + mypy clean.

### File List

- `src/nagbot/engine/escalation.py` (new)
- `src/nagbot/store/db.py`, `store/repo.py` (migration 003 + P0EscalationRow + accessors)
- `src/nagbot/config.py` (EscalationCfg ladder fields)
- `src/nagbot/run.py` (`_ESCALATION_LOCK`, `build_alert_adapters`, `execute_escalation_run`)
- `src/nagbot/scheduler.py`, `web/app.py` (conditional escalation job wiring)
- `tests/unit/test_escalation.py` (new — 14 tests)

## QA Results

**Verification:** 3 adversarial reviewers (concurrency/correctness, spine-AD/AC audit) after implementation, as requested. Fixes applied and re-tested.

**Fixed:**
- **[HIGH] Failed rung-0 send reset the dwell clock** — the OPEN row was only persisted on send success, so an unreachable/failing owner (the exact case escalation exists for) re-opened every tick with a fresh `p0_detected_at` and **never climbed**. Fixed: the detection anchor is now persisted unconditionally on open (independent of send); rung-0 notification stays send-gated. Regression: `test_open_anchors_clock_even_on_failed_send`.
- **[MED] Unlocked hot read** — `active_p0_escalations()` (escalation thread) shared the SQLite connection with the digest writer. Now takes `self._lock`.
- **[MED] Untested runner + enabled-gate** — added `execute_escalation_run` end-to-end tests (disabled no-op + happy path with fakes) and `build_scheduler` gating tests (job present iff enabled, IntervalTrigger, max_instances=1).
- **[LOW] Bad `alert_channels` config** → per-tick error-storm; now rejected at config load (fail loud). Test added.
- **[LOW] `INSERT OR REPLACE` climb could clobber future ack columns** — climbs now use a targeted `advance_p0_rung` UPDATE.

**Verified correct (no change):** AD-4 single-writer; AD-5 stop-when-not-P0; AD-8 cumulative catch-up ≤1 rung/tick (never stuck, never skips); dwell=0 / exactly-dwell / negative-elapsed / empty-chain edge cases; AD-3 fallback + fail-fast; lock release on all paths.

**Documented deviations (acceptable S3 scope):**
- AD-8 "send + log + persist in one transaction / `send_log` as dedup source" is **not** atomic — a sub-ms crash between `log_send` and the rung persist can double-send **once**. Bounded and rare; full atomicity / send_log-dedup is a follow-up.
- No monotonic clock (AD-8): skew-induced double-notify is instead prevented structurally (`current_rung` only ever increments).
- No `alert_send_timeout` (AD-3): only meaningful once E7-S5 adds the Teams alert channel (single channel today).

**Suite:** 192 passed (was 172 at cycle start), ruff + mypy clean.

**Gate:** ✅ PASS — approved for merge; the three deviations are logged as S4/S5 follow-ups.
