# E5-S2: Teams mentions + deep links

Status: Draft

## Story
As a technician, I want the card to @mention me and link straight to each ticket, so that
the nag is personal and actionable in one tap.

## Context
After E5-S1.

## Acceptance Criteria
- AC1: Card includes `msteams.entities` mention for `owner.teams_id` (AAD UPN) and the `<at>name</at>` token in the card text.
- AC2: Every ticket row links to `{glpi_web}/front/ticket.form.php?id={id}`.
- AC3: Owner without teams_id → card sends without mention (no failure), noted in detail.

## Tasks
- [ ] teams_card.json.j2 mention entities — AC1, AC3
- [ ] golden update + tests — AC1..AC3

## Dev Notes
Mention entity: `{"type":"mention","text":"<at>{name}</at>","mentioned":{"id":upn,"name":name}}`
under `content.msteams.entities`. Links already in Ticket.url (E1-S3).

## Testing
Golden with mention; goldenless unit for no-teams_id fallback.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
