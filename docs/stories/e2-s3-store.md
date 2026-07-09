# E2-S3: SQLite store — migrations + Store

Status: Draft

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
- [ ] store/db.py: connect, MIGRATIONS, migrate — AC1
- [ ] store/repo.py: Store + row dataclasses — AC2..AC5
- [ ] fields.py: SqliteCache(CacheBackend) — AC2
- [ ] tests/unit/test_store.py — all ACs

## Dev Notes
Timestamps stored as UTC ISO-8601 strings. `ticket_ids` JSON via json.dumps. Two runs on
the same run_date must not double-bump a streak (dashboard run-now + cron) — guard with
`last_red_date`. Single connection per Store instance; `check_same_thread=False` +
a `threading.Lock` around writes (scheduler thread + web thread share it).

## Testing
tmp_path DB; migrate twice (idempotent); multi-day streak simulation incl. same-day
double run, reset, re-escalation after clear; snooze expiry with injected now.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
