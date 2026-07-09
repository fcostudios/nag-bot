# Epic 5 — Teams live (later cycle)

**Goal:** The TeamsAdapter goes from stub to live: POST the Adaptive Card in a Power
Automate Workflow envelope to `TEAMS_WEBHOOK_URL`, with @mentions and GLPI deep links.
Built on Workflows (not legacy O365 connectors, retired ~May 2026).

**Depends on:** E2-S5 (adapter protocol + card template), a Power Automate Workflow
created by the user ("Post to a channel when a webhook request is received").

| Story | Title | Size |
|---|---|---|
| E5-S1 | Adaptive Card POST via Power Automate Workflow | M |
| E5-S2 | Mentions + deep links | S |

**Done when:** the daily digest card lands in the support channel mentioning the owner;
failures are logged per-recipient and never block email.

## Retrospective

**Closed:** 2026-07-09 · 2/2 stories Done, all gates PASS · suite: 124 tests, ruff+mypy clean.

- **Changed vs. plan:** `send_rollup` went live alongside digests in S1 (transport was
  already there; a simple FactSet card). Mention entity implemented conditionally inside
  the template rather than in adapter code — no-teams_id owners degrade gracefully.
- **Deploy prerequisite (user-side):** create the Power Automate Workflow and set
  `TEAMS_WEBHOOK_URL` (steps + curl test in docs/teams-setup.md); add `teams` to
  `channels.enabled`; set each owner's `teams_id` (AAD UPN) for mentions.
- **Carry-overs:** none.
