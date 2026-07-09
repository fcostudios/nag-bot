# E2-S3: SQLite store — migrations + Store

Status: Done

## Story
As the nagbot, I want one thin storage module owning all SQL, so that runs, snapshots,
send logs, snoozes and escalation streaks persist across restarts on the container volume.

## Context
After E1. Schema per architecture §3.5. Also swaps E1-S4's InMemoryCache for the SQLite
`field_cache` backend.

## Acceptance Criteria
- AC1: `connect(path)` enables WAL + foreign keys; `migrate()` applies numbered migrations idempotently, recording versions in `schema_migrations`.
- AC2: `Store` methods: start_run/finish_run, save_snapshots, log_send, snooze/unsnooze/active_snoozes(now), bump_red_streaks(red_ids, run_date) → newly-escalated ids, ticket_history, latest_snapshot, recent_runs, recent_sends, field_cache get/put.
- AC3: `bump_red_streaks`: increments streak once per distinct run_date, resets tickets absent from `red_ids`, returns ids whose streak crossed `escalation_red_days` today and are not yet `escalated_at`-stamped; leaving red clears `escalated_at`.
- AC4: `active_snoozes(now)` excludes expired snoozes; snoozing again replaces the row.
- AC5: All methods round-trip dataclasses (no raw dict leakage to callers).

## Tasks
- [x] store/db.py: connect, MIGRATIONS, migrate — AC1
- [x] store/repo.py: Store + row dataclasses — AC2..AC5
- [x] Store itself implements CacheBackend (get/put) — no separate SqliteCache class needed — AC2
- [x] tests/unit/test_store.py — all ACs

## Dev Notes
Timestamps stored as UTC ISO-8601 strings. `ticket_ids` JSON via json.dumps. Two runs on
the same run_date must not double-bump a streak (dashboard run-now + cron) — guard with
`last_red_date`. Single connection per Store instance; `check_same_thread=False` +
a `threading.Lock` around writes (scheduler thread + web thread share it).

## Testing
tmp_path DB; migrate twice (idempotent); multi-day streak simulation incl. same-day
double run, reset, re-escalation after clear; snooze expiry with injected now.

## Dev Agent Record
- `Store` implements the `CacheBackend` protocol directly (structural `get`/`put`) instead of a wrapper class — one object to pass around.
- Added `snoozed` flag to ticket_snapshots (E3-S2 needs the 💤 marker; cheaper now than a migration later) and `snooze_for`/`sends_for_ticket`/`last_run`/`escalations` accessors the web stories will need.
- "Leaving red" is implemented as row deletion (clears streak AND escalated_at in one statement); re-entering red starts a fresh streak — semantics matched to E4-S1 AC2.
- Snooze expiry compares `until >= today` — a snooze "until 2026-07-10" still covers the 10th (inclusive), documented in the /tickets form label (E3-S4).
- `latest_snapshot` skips runs with zero snapshots so a failed run doesn't blank the WIP dashboard.

## QA Results
- AC1 ✅ `test_migrate_is_idempotent` (double migrate, single version row); WAL+FK pragmas in connect().
- AC2 ✅ every listed method exists and is covered (`test_run_lifecycle`, `test_snapshots_and_latest`, `test_send_log_filters_and_ticket_lookup`, `test_field_cache_backend`).
- AC3 ✅ `test_red_streaks_escalate_once_and_reset`: same-day double run no-op, escalate exactly once on day 3, no repeat on day 4, clear on non-red, full re-escalation cycle.
- AC4 ✅ `test_snooze_roundtrip_and_expiry` (replace + expiry + unsnooze).
- AC5 ✅ all reads return dataclasses (RunRow/SnapshotRow/SendRow/SnoozeRow/EscalationRow).
- Suite: ruff/mypy clean, 67 passed. **Gate: PASS**
