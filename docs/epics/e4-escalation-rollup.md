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

_(appended when the epic closes)_
