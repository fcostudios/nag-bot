# E6-S2: WhatsApp rate cap + opt-out

Status: Done

## Story
As the operator, I want WhatsApp volume capped and opt-out respected, so that costs stay
at fractions of a cent and nobody gets spammed into blocking the number.

## Context
After E6-S1.

## Acceptance Criteria
- AC1: `channels.whatsapp_max_per_run` (YAML, default 20) caps sends per run; overflow → `skipped` with "rate cap" detail, worst owners prioritized first.
- AC2: `whatsapp: null` / absent in owner config = opted out → `skipped`, never an error.
- AC3: Cap and skips visible in /ops send log.

## Tasks
- [x] config: whatsapp_max_per_run — AC1 (shipped E1-S2)
- [x] adapter cap logic (worst-first ordering already in Digest) — AC1, AC2
- [x] tests — AC1..AC3

## Dev Notes
Priority = digest worst tier then count. Cap applies to attempts, not successes.

## Testing
25 owners, cap 20 → 20 attempts + 5 rate-cap skips, worst 20 chosen; opted-out inside
the top 20 consumes no slot.

## Dev Agent Record
- Cap = a per-run attempt counter inside the adapter, reset via the new `begin_run()` hook the orchestrator calls once per run (`channels/base.py::begin_run` duck-types so other adapters need no changes).
- Worst-first priority needs no adapter logic: `build_digests` already sorts owners worst-first and run.py dispatches in that order, so the first `max_per_run` attempts ARE the worst owners.
- Opt-out and dry-run checks run before the cap check, so neither consumes a slot.
- Cap counts *attempts* (sent or failed), not successes — a burst of API failures can't burn unlimited money-messages.

## QA Results
- AC1 ✅ `test_whatsapp_rate_cap_worst_first` (25 owners, cap 20 → 20 sent + 5 "rate cap" skips in dispatch order); `test_begin_run_resets_cap_between_runs`.
- AC2 ✅ `test_whatsapp_optout_consumes_no_slot` (opted-out mid-sequence skips without burning a slot).
- AC3 ✅ skips carry "rate cap"/"opted out" details into send_log (visible on /ops via existing rendering); cross-channel `test_all_channels_dry_run_end_to_end` shows whatsapp dry_run + skipped rows side by side.
- Suite: ruff/mypy clean, 134 passed. **Gate: PASS**
