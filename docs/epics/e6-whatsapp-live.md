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

_(appended when the epic closes)_
