# E2-S2: Ownership resolution + grouping

Status: Draft

## Story
As the nagbot, I want each ticket mapped to exactly one responsible owner with contact
details, so that digests reach the right person and unmapped tickets surface instead of
vanishing.

## Context
After E2-S1. Consumes `Ticket.tech_names/group_names` and YAML `owners`/`groups`/`fallback`.

## Acceptance Criteria
- AC1: `resolve_owner(ticket, cfg)`: first assigned tech with a YAML mapping wins; else first mapped group; else fallback owner (`kind="unassigned"`, email=`fallback.email`).
- AC2: A tech/group present on the ticket but missing from YAML produces a warning string (collected into the run report) while resolution continues down the chain.
- AC3: `group_by_owner(scored, cfg)` buckets ScoredTickets per Owner, tickets sorted worst-tier-first then oldest-first.
- AC4: Owner is hashable/frozen (dict key) with `key` like `tech:jdoe` / `group:Networking` / `unassigned`.

## Tasks
- [ ] engine/ownership.py: Owner, resolve_owner, group_by_owner — all ACs
- [ ] tests/unit/test_ownership.py — all ACs

## Dev Notes
Match tech by GLPI login (YAML key) — E1-S3 normalizes assignee cells to logins where the
API returns them; if the instance returns display names, `owners.<key>.aliases: []` (add
field to OwnerCfg) matches those. ScoredTicket dataclass lives here (ticket+metrics+tier)
to avoid a circular import with digest/.

## Testing
Chain permutations (tech mapped / tech unmapped+group mapped / neither), warning
collection, sort order inside buckets, aliases matching.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
