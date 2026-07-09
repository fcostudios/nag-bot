# E2-S6: Orchestrator, scheduler, entrypoint & compose

Status: Draft

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
- [ ] run.py: RunReport, execute_nag_run, execute_rollup_run stub, run lock — AC1..AC3
- [ ] scheduler.py — AC4
- [ ] main.py: run-once/serve/fetch — AC5
- [ ] docker-compose.yml (+ Dockerfile CMD `python -m nagbot serve`) — AC6
- [ ] tests/integration/test_dry_run.py — AC1..AC3, AC5

## Dev Notes
`glpi_factory: Callable[[], GlpiClient]` so tests inject respx-backed clients. Dry-run
resolution: `effective = not live_flag or cfg.dry_run` — CLI `--live` still can't override
config. RunReport: run_id, dry_run, tickets_seen, digests_built, sends, warnings, error.

## Testing
Integration: tmp store + mocked GLPI + fake-SMTP EmailAdapter; dry-run writes snapshots +
`dry_run` send rows, SMTP untouched; live writes `sent` + correct MIME; snoozed ticket
excluded from digest but snapshotted; lock test with threading.Barrier.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
