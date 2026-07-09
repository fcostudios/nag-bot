# E5-S1: Adaptive Card POST via Power Automate Workflow

Status: Draft

## Story
As a technician, I want my digest as an Adaptive Card in the support channel, so that my
stale pile is visible where the team already lives (peer pressure included).

## Context
Later cycle. Card template + stub adapter shipped in E2. User must create the Power
Automate Workflow ("Post to a channel when a webhook request is received") and set
`TEAMS_WEBHOOK_URL`.

## Acceptance Criteria
- AC1: TeamsAdapter.send_digest POSTs `{"type":"message","attachments":[{"contentType":"application/vnd.microsoft.card.adaptive","content":<card>}]}` to the webhook; 2xx → `sent`.
- AC2: 429/5xx retried (3 attempts, backoff); terminal failure → `failed` with body snippet in detail; never blocks other adapters.
- AC3: Dry-run renders the card and returns `dry_run` without network.
- AC4: docs/teams-setup.md documents creating the Workflow and testing it with curl.

## Tasks
- [ ] channels/teams.py live implementation (httpx, injectable client) — AC1..AC3
- [ ] respx tests — AC1..AC3
- [ ] docs/teams-setup.md — AC4

## Dev Notes
Workflows accept the message envelope shape above. Rate limits are per-flow — keep the
per-run POST count = number of owners (one card each), sequential.

## Testing
respx: 202 accepted; 429→retry→202; 400 → failed with detail; dry-run no route hit.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
