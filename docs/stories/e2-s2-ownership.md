# E2-S2: Ownership resolution + grouping

Status: Done

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
- [x] engine/ownership.py: Owner, resolve_owner, group_by_owner — all ACs
- [x] tests/unit/test_ownership.py — all ACs

## Dev Notes
Match tech by GLPI login (YAML key) — E1-S3 normalizes assignee cells to logins where the
API returns them; if the instance returns display names, `owners.<key>.aliases: []` (add
field to OwnerCfg) matches those. ScoredTicket dataclass lives here (ticket+metrics+tier)
to avoid a circular import with digest/.

## Testing
Chain permutations (tech mapped / tech unmapped+group mapped / neither), warning
collection, sort order inside buckets, aliases matching.

## Dev Agent Record
- `resolve_owner` returns an `OwnershipResult` (owner + warnings) instead of a tuple — clearer at call sites.
- `group_by_owner` also returns the aggregated warnings list; run.py (E2-S6) stores them on the run row for the ops dashboard callout (E3-S3).
- `sort_scored` exported separately — the digest builder (E2-S4) reuses the same worst-first-then-oldest ordering.
- Alias matching (OwnerCfg.aliases, added in E1-S2) covers instances whose API returns display names instead of logins (risk R3).

## QA Results
- AC1 ✅ `test_mapped_tech_wins`, `test_nothing_mapped_falls_back` (fallback email + kind unassigned).
- AC2 ✅ `test_unmapped_tech_falls_to_group_with_warning`, double-warning case in fallback test.
- AC3 ✅ `test_group_by_owner_buckets_and_sorts` ([ON_FIRE oldest, ON_FIRE newer, FRESH]).
- AC4 ✅ `test_owner_is_hashable_dict_key`; alias path via `test_alias_matches_display_name`.
- Suite: ruff/mypy clean, 60 passed. **Gate: PASS**
