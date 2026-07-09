# E5-S1: Adaptive Card POST via Power Automate Workflow

Status: Done

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
- [x] channels/teams.py live implementation (httpx, injectable client) — AC1..AC3
- [x] respx tests — AC1..AC3
- [x] docs/teams-setup.md — AC4

## Dev Notes
Workflows accept the message envelope shape above. Rate limits are per-flow — keep the
per-run POST count = number of owners (one card each), sequential.

## Testing
respx: 202 accepted; 429→retry→202; 400 → failed with detail; dry-run no route hit.

## Dev Agent Record
- Retry loop mirrors GlpiClient's pattern (3 attempts, 1s/2s backoff, injectable sleep); retriable = 429/5xx/transport, anything else fails immediately with a body snippet.
- `send_rollup` also went live (simple FactSet card built in-code — per-person WIP lines) since the envelope/transport was already there; not in the original ACs, recorded as scope-adjacent.
- Missing `TEAMS_WEBHOOK_URL` at send time → `skipped` (belt-and-suspenders; config validation already blocks enabling teams without it).
- Card renders before the dry-run check so template errors surface in daily dry-runs (kept from stub behavior).

## QA Results
- AC1 ✅ `test_teams_live_posts_envelope` (message + adaptive attachment shape, 202→sent).
- AC2 ✅ `test_teams_retries_on_429_then_succeeds`, `test_teams_gives_up_after_retries` (503×3 → failed with attempts note), `test_teams_permanent_400_fails_with_detail`; pipeline isolation via existing `_safe_send`.
- AC3 ✅ `test_teams_dry_run_no_network` (route never called).
- AC4 ✅ docs/teams-setup.md (Workflow template steps, curl test, mention prerequisites, troubleshooting).
- Extra: `test_teams_without_webhook_skips`, `test_teams_rollup_card_posts`.
- Suite: ruff/mypy clean, 121 passed. **Gate: PASS**
