# E5-S2: Teams mentions + deep links

Status: Done

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
- [x] teams_card.json.j2 mention entities — AC1, AC3
- [x] golden update + tests — AC1..AC3

## Dev Notes
Mention entity: `{"type":"mention","text":"<at>{name}</at>","mentioned":{"id":upn,"name":name}}`
under `content.msteams.entities`. Links already in Ticket.url (E1-S3).

## Testing
Golden with mention; goldenless unit for no-teams_id fallback.

## Dev Agent Record
- Mention is conditional in the template itself: with `teams_id` the intro TextBlock uses `<at>Name</at>` and the card gains `msteams.entities`; without it the card renders the plain name and omits the block entirely (E5-S1's SendResult detail already notes unmentioned sends).
- Golden diff was one line (fixture owner has no teams_id → wording only); mention path covered by direct unit tests instead of a second golden.
- Deep links were already in the FactSet rows via `Ticket.url` (E1-S3) — added an explicit assertion.

## QA Results
- AC1 ✅ `test_card_mentions_owner_with_teams_id` (`<at>` token + mention entity with id/name).
- AC2 ✅ `test_card_rows_deep_link_to_glpi`.
- AC3 ✅ `test_card_without_teams_id_has_no_mention` (no msteams block, no failure).
- Suite: ruff/mypy clean, 124 passed; teams_card golden regenerated. **Gate: PASS**
