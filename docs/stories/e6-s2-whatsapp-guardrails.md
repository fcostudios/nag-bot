# E6-S2: WhatsApp rate cap + opt-out

Status: Draft

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
- [ ] config: whatsapp_max_per_run — AC1
- [ ] adapter cap logic (worst-first ordering already in Digest) — AC1, AC2
- [ ] tests — AC1..AC3

## Dev Notes
Priority = digest worst tier then count. Cap applies to attempts, not successes.

## Testing
25 owners, cap 20 → 20 attempts + 5 rate-cap skips, worst 20 chosen; opted-out inside
the top 20 consumes no slot.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
