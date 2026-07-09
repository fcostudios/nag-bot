# E2-S6: Orchestrator, scheduler, entrypoint & compose

Status: Done

## Story
As the operator, I want the full pipeline wired to a weekday cron inside a composable
container, so that the nagbot runs itself and I can trigger/dry-run it from the CLI.

## Context
Last E2 story; consumes S1–S5 + E1. After this the MVP is deployable.

## Acceptance Criteria
- AC1: `execute_nag_run(...)` runs: start_run → fetch (one GLPI session) → metrics/tiers → save_snapshots → drop active snoozes → group by owner → bump_red_streaks → build digests (escalated flagged) → adapters × digests → log_send each → finish_run with counts; returns RunReport (incl. ownership warnings).
- AC2: A failing adapter/digest logs `failed` and continues; an exception before dispatch marks the run `failed` with the error recorded.
- AC3: Overlap guard: concurrent invocation returns a "run already in progress" report without touching GLPI (lock + APScheduler max_instances=1).
- AC4: `build_scheduler(cfg, …)` registers digest cron (+ rollup cron placeholder calling execute_rollup_run stub that logs "E4 pending") from YAML crontabs in cfg.timezone, coalesce=True, misfire_grace_time=3600.
- AC5: CLI: `python -m nagbot run-once [--live]` (dry-run unless --live AND config allows), `serve` starts scheduler+web (web lands E3-S1; until then serve runs scheduler + healthz-less keepalive), `fetch --json` unchanged.
- AC6: docker-compose.yml runs the image with `./config:/config:ro`, named volume on `/data`, env from `.env`; `docker build` + compose config validate.

## Tasks
- [x] run.py: RunReport, execute_nag_run, execute_rollup_run stub, run lock — AC1..AC3
- [x] scheduler.py (+ tests/unit/test_scheduler.py) — AC4
- [x] main.py: run-once/serve/fetch + runtime.py wiring — AC5
- [x] docker-compose.yml (+ Dockerfile CMD `python -m nagbot serve`, interim scheduler-only serve in web/app.py) — AC6
- [x] tests/integration/test_dry_run.py — AC1..AC3, AC5

## Dev Notes
`glpi_factory: Callable[[], GlpiClient]` so tests inject respx-backed clients. Dry-run
resolution: `effective = not live_flag or cfg.dry_run` — CLI `--live` still can't override
config. RunReport: run_id, dry_run, tickets_seen, digests_built, sends, warnings, error.

## Testing
Integration: tmp store + mocked GLPI + fake-SMTP EmailAdapter; dry-run writes snapshots +
`dry_run` send rows, SMTP untouched; live writes `sent` + correct MIME; snoozed ticket
excluded from digest but snapshotted; lock test with threading.Barrier.

## Dev Agent Record
- Added `runtime.py` (Runtime dataclass + build_runtime) so CLI and the E3 web app share one wiring path — not in the original task list but prevents E3 from importing main.py circularly.
- `fetch_and_score` and `build_all_digests` split out of the pipeline for E3-S4's /preview to reuse (story dev note honored ahead of time).
- Escalation manager-CC plumbing (bump_red_streaks → escalated_ids → EmailAdapter CC + kind='escalation' rows) is fully wired and integration-tested here; E4-S1 remains for semantics hardening + UI surfacing.
- Snoozed tickets are excluded from red streaks (a deliberately parked ticket must not CC the manager) — decision recorded for E4-S1 review.
- web/app.py currently holds a scheduler-only keepalive `serve()` so this commit stays deployable; E3-S1 replaces it with FastAPI + uvicorn.
- CLI catches ConfigError → clean stderr message, exit 2.
- Test fix during QA: the escalation-streak test's ticket was only 🟠 on its first simulated day (stale 6.5bd < 7); switched to a mid-June ticket that is 🔴 on all three days.

## QA Results
- AC1 ✅ `test_dry_run_end_to_end` (3 tickets → 2 digests, snapshots for all incl. tiers, dry_run rows, warnings for unmapped 'ghost').
- AC2 ✅ `test_glpi_failure_marks_run_failed` (run row failed + error); `_safe_send` covered by unit `test_smtp_failure_returns_failed_not_raises`.
- AC3 ✅ `test_overlap_guard_returns_busy` (no run row written while lock held); scheduler max_instances=1 asserted.
- AC4 ✅ `test_scheduler_registers_both_crons` (both jobs, tz America/Guayaquil, mon-fri 8h / mon 8:30, coalesce+grace via max_instances/misfire asserts).
- AC5 ✅ run-once wired with `dry_run = not live or cfg.dry_run` (note printed when config overrides --live); `test_live_run_sends_email` proves the live path MIME; snooze exclusion via `test_snoozed_ticket_excluded_but_snapshotted`; escalation CC via `test_escalation_ccs_manager_after_streak` ([None, None, boss@x.com], exactly one kind='escalation' row).
- AC6 ✅ `docker compose config -q` valid (with .env from example); Dockerfile CMD serve unchanged; image build delegated to CI (E1-S1 note).
- Suite: ruff/mypy clean, 87 passed. **Gate: PASS**
