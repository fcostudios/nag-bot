# Epic 4 — Escalation & manager rollup (later cycle)

**Goal:** Sustained-red tickets CC the manager automatically; Monday mornings managers
get a rollup: WIP per person, aging distribution, worst-offenders leaderboard.

**Depends on:** E2 (store escalation table, pipeline hooks already in place), E3 (ops
dashboard shows escalations).

| Story | Title | Size |
|---|---|---|
| E4-S1 | Red-streak escalation (manager CC) | M |
| E4-S2 | Monday manager rollup | M |

**Done when:** a ticket red for `escalation_red_days` consecutive run-days produces
exactly one escalation CC until it leaves red; the rollup renders and sends on the
Monday cron, respecting dry-run.

## Retrospective

**Closed:** 2026-07-09 · 2/2 stories Done, all gates PASS · suite: 114 tests, ruff+mypy clean.

- **Changed vs. plan:** the epic was smaller than sharded because E2 had already shipped
  the streak table, CC plumbing and rollup templates — exactly as the E2 retro predicted.
  S1 became proofs + UI (weekend-gap test, /ops streak table, WIP ⚠️ markers); S2 became
  the real `execute_rollup_run` + a dedicated `/rollup` page behind the /ops card.
- **Decisions recorded:** skipped rollups (no snapshots) write no run row; rollup send
  rows carry the leaderboard ticket ids; /rollup renders the identical HTML the email
  sends (single code path).
- **Carry-overs:** none. Next cycles: E5 (Teams live — needs the Power Automate Workflow
  URL from the user), E6 (WhatsApp — Meta template approval is the long pole, start it
  now if WhatsApp is wanted).
