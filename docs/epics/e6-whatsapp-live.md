# Epic 6 — WhatsApp live (later cycle)

**Goal:** The WhatsAppAdapter goes live against the Meta Cloud API using a pre-approved
utility template. Rate-capped and opt-out aware.

**Depends on:** E2-S5 (adapter protocol). **Long pole:** Meta Business account, registered
number, and template approval — start the approval process well before development.

Template draft (submit to Meta early):
> "Hi {{1}}, ticket reminder: you have {{2}} open, {{3}} overdue. Oldest #{{4}} ({{5}}d). Open GLPI to update: {{6}}"

| Story | Title | Size |
|---|---|---|
| E6-S1 | Cloud API template send | M |
| E6-S2 | Rate cap + opt-out | S |

**Done when:** owners with a `whatsapp` number receive the template message; owners
without one are skipped with `status='skipped'`; a per-run cap bounds message volume.

## Retrospective

**Closed:** 2026-07-09 · 2/2 stories Done, all gates PASS · suite: 134 tests, ruff+mypy clean.

- **Changed vs. plan:** no retry on WhatsApp sends (deliberate — duplicate paid utility
  messages are worse than waiting for tomorrow's digest; deviation recorded in S1).
  Rate-cap plumbing landed in S1, semantics proven in S2. Worst-first cap priority came
  free from `build_digests` ordering — zero adapter logic.
- **Deploy prerequisites (user-side, the long pole):** Meta Business account, registered
  number → `WHATSAPP_PHONE_NUMBER_ID`, access token, and an **approved utility template**
  (draft in this epic's header) → `WHATSAPP_TEMPLATE_NAME`. Owners need E.164 `whatsapp:`
  numbers (validated at config load). Enable with `channels.enabled: [email, teams, whatsapp]`.
- **Carry-overs:** none — all six epics of the original strategy are now implemented.
