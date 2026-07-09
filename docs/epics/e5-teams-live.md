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

_(appended when the epic closes)_
