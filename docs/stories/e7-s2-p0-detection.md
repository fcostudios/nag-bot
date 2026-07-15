---
baseline_commit: 90b70e4d009c469a56ced0b9dfa7e4326f08ac4a
---

# E7-S2: P0 detection + verification gate

Status: done

<!-- bmad create-story. Governing spec: architecture spine AD-5 (config-driven P0 rule) + AD-6 (re-validate). Epic: docs/epics/e7-urgent-p0-escalation.md. GLPI field IDs + default rule confirmed by the 2026-07 live probe. -->

## Story

As **nagbot's escalation engine (E7-S3, later)**,
I want **a configurable, multi-field rule that decides whether a GLPI ticket is a genuine P0**,
so that **escalation fires only on real, verified P0s — never crying wolf — and the definition of "P0" can change in config without a code change**.

## Context

- **Governing decisions (spine):** AD-5 — the P0 rule is a **configurable OR-of-AND expression** over GLPI ticket fields, evaluated by a tiny safe evaluator (no `eval`), extensible without code changes. AD-6 — the same predicate is the "verification gate": the engine (E7-S3/S4) re-checks it live before every dispatch.
- **Confirmed against the live GLPI (2026-07 probe):** field search-option IDs `priority=3`, `urgency=10`, `impact=11`, `category(itilcategories.completename)=7`, `status=12`, `type=14`. **Default rule = `priority >= 5`** (5/6 = Alta/Muy alta). Reality: severity is unused today (all open tickets = priority 3; only 11 ever hit P5/P6; type always Request), so detection depends on a **team marking convention** (triage sets priority 5/6 for a genuine P0). Ships safe — with today's data it escalates **nothing** until a P0 is deliberately marked.
- **Scope:** the detection predicate + the GLPI model/field plumbing it needs. NOT the escalation state machine/ladder (E7-S3), the ack/re-validate loop or single-ticket `get_ticket` refetch (E7-S4), or dispatch. This story is pure, testable logic + config + GLPI parsing.

## Acceptance Criteria

- **AC1:** `glpi/fields.py` `_SIGNATURES` + `CANONICAL` gain `priority (glpi_tickets.priority, uid 3)`, `urgency (glpi_tickets.urgency, 10)`, `impact (glpi_tickets.impact, 11)`, `category (glpi_itilcategories.completename, 7)`. Field discovery resolves them from `listSearchOptions` (falling back to canonical uids), exactly like the existing fields.
- **AC2:** `glpi/models.py` `Ticket` gains `priority: int = 0`, `urgency: int = 0`, `impact: int = 0`, `category: str = ""` (safe defaults so existing construction/tests don't break).
- **AC3:** `FieldMap.to_ticket` parses the new cells into the `Ticket` (ints via `int(... or 0)`, category as str); `forcedisplay` includes the new field uids so a search returns them.
- **AC4:** New `config.py` `EscalationCfg` (added to `AppConfig` as `escalation`, default via `Field(default_factory=...)`): `enabled: bool = False`; `p0_rule: list[list[P0Condition]]` defaulting to a single group `[[priority >= 5]]`. `P0Condition = {field: str, op: Literal[">=",">","<=","<","==","!=","in"], value: int|str|list}`. Existing config load stays valid with no `escalation:` key present.
- **AC5:** New `engine/p0.py` — a **safe evaluator** (operator map, no `eval`): `is_p0(ticket, rule) -> bool` returns True iff **any** group matches and **all** conditions in that group match (OR-of-AND). `detect_p0s(tickets, rule) -> list[Ticket]` filters. Reads ticket attributes by `field` name.
- **AC6:** Correctness on real values: `priority >= 5` matches priority 5 and 6, and does NOT match 3 or 4. An `in` op works for `category in [...]`. An empty rule (`[]`) matches nothing. A group with multiple conditions is ANDed; multiple groups are ORed.
- **AC7:** **Safety/robustness:** an unknown `field` (not an attribute of `Ticket`) or a type-mismatched comparison (e.g. `>=` on a str) returns `False` for that condition — it never raises. (The evaluator is used in a hot loop; a bad rule must degrade, not crash.)
- **AC8:** No regressions — existing GLPI parsing, config load, and the full suite stay green; `ruff` + `mypy` clean.

## Tasks

- [x] `src/nagbot/glpi/fields.py` — add the 4 fields to `_SIGNATURES` + `CANONICAL`; ensure `to_ticket` reads them (AC1, AC3).
- [x] `src/nagbot/glpi/models.py` — add `priority`/`urgency`/`impact`/`category` to `Ticket` with safe defaults (AC2).
- [x] `src/nagbot/config.py` — add `P0Condition` + `EscalationCfg`; wire `escalation` into `AppConfig` (AC4).
- [x] `src/nagbot/engine/p0.py` — NEW safe evaluator `is_p0` / `detect_p0s` (AC5–AC7).
- [x] `tests/unit/test_p0.py` — evaluator + config-default tests; extend a GLPI parsing test to cover the new fields (AC6–AC8).

## Dev Notes

- **Reuse discovery, don't reinvent:** `_match_options` already maps `(table, field)` → uid and falls back to `CANONICAL`. `category` mirrors how `group` maps to a `*.completename` column — check the `_match_options` special-case (`name == "group" and field == "name"`) doesn't misfire; add category cleanly (its signature is `("glpi_itilcategories", "completename")`).
- **Evaluator shape:** `_OPS = {">=": operator.ge, ...}`; `in` handled separately (value is a list). `getattr(ticket, cond.field, _MISSING)`; missing or `TypeError` on compare → `False`. Keep it a pure function (no I/O), `now`-free — trivially unit-testable and reused verbatim by E7-S3/S4 as the AD-6 verification gate.
- **Config default is the whole safety story:** default `enabled=False` and `p0_rule=[[priority>=5]]`. With `enabled=False` nothing escalates; even enabled, today's data yields zero P0s until someone marks one. Do not hardcode `5` anywhere but the default factory.
- **Don't touch** `engine/escalation.py` (that file is E7-S3). Put detection in `engine/p0.py`.
- **Marking convention (ops, not code):** for this to ever fire, triage must set priority 5/6 on a genuine P0 — document in the epic/runbook; out of code scope.

### Project Structure Notes

- Ticket model gains 4 optional fields (backward-compatible). New `engine/p0.py`. No store/schema change. No change to the digest run or the escalation engine.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-e7-urgent-p0-escalation/ARCHITECTURE-SPINE.md#AD-5, #AD-6]
- [Source: src/nagbot/glpi/fields.py:25-46 (CANONICAL/_SIGNATURES), 84-160 (_match_options, discover, to_ticket)]
- [Source: src/nagbot/glpi/models.py:21-34 (Ticket)]
- [Source: src/nagbot/config.py:68-131 (Thresholds/AppConfig pattern)]
- [Source: scripts/probe_glpi_p0_fields*.py — the read-only probe that confirmed the field IDs + values]

## Testing

`pytest`. Pure-function tests for the evaluator (no I/O), plus a GLPI-parse test.

- **test_priority_rule_matches_5_and_6_not_3_4:** build `Ticket(priority=…)`; `is_p0` with default rule true for 5/6, false for 3/4.
- **test_and_within_group / test_or_across_groups:** a 2-condition group ANDs; two groups OR.
- **test_in_operator_on_category** and **test_empty_rule_matches_nothing**.
- **test_unknown_field_and_type_mismatch_return_false_not_raise** (AC7).
- **test_config_default_rule_is_priority_ge_5** and **test_config_loads_without_escalation_key** (AC4 backward-compat).
- **test_to_ticket_parses_priority_urgency_impact_category** (extend GLPI parse test; AC3).

Run `python -m pytest -q`; `ruff check`; `mypy src/nagbot`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (dev-story workflow)

### Debug Log References

- RED: test_p0 failed on missing `EscalationCfg`. GREEN after config/model/fields/evaluator.
- Fixed mypy (operator callables → `Callable[[Any,Any],bool]`) + ruff (Callable import, E501).
- 9 new tests; full suite 170 (was 161); ruff + mypy clean.

### Completion Notes List

- `engine/p0.py`: pure, safe OR-of-AND evaluator `is_p0`/`detect_p0s` — operator map (no `eval`), unknown field / type-mismatch → `False` (never raises). Reused verbatim by E7-S3/S4 as the AD-6 verification gate.
- `config.py`: `P0Condition` + `EscalationCfg` (`enabled=False`, default rule `[[priority>=5]]` via factory); wired `escalation` into `AppConfig`. Loads fine with no `escalation:` key.
- `glpi/fields.py`: `priority(3)/urgency(10)/impact(11)/category(7)` added to `_SIGNATURES` + `CANONICAL`; `to_ticket` parses them (safe int; forcedisplay includes them).
- `glpi/models.py`: `Ticket` gains `priority/urgency/impact/category` with safe defaults (backward-compatible).
- Field IDs + default rule confirmed against the live GLPI probe. Ships safe: `enabled=False`, and priority>=5 matches 0 current open tickets until a P0 is marked.
- Out of scope (later): escalation engine/ladder (E7-S3), `get_ticket` refetch + ack loop (E7-S4). `engine/escalation.py` untouched.

### File List

- `src/nagbot/engine/p0.py` (new — evaluator)
- `src/nagbot/config.py` (modified — `P0Condition`, `EscalationCfg`, `AppConfig.escalation`)
- `src/nagbot/glpi/fields.py` (modified — signatures/canonical + `to_ticket`)
- `src/nagbot/glpi/models.py` (modified — Ticket severity fields)
- `tests/unit/test_p0.py` (new — 9 tests)
- `_bmad-output/planning-artifacts/architecture/architecture-e7-urgent-p0-escalation/ARCHITECTURE-SPINE.md` (AD-5 default + open-question resolved)

## QA Results

**Review:** adversarial code review vs baseline `90b70e4` (evaluator safety / AC1–AC8 / config back-compat). **Verdict: clean, ship-ready.**

- **[LOW] fixed** — AC1's *discovery* of the 4 new fields was only exercised via the canonical fallback. Added `test_discovery_finds_p0_fields_from_options` (non-canonical uids) proving the real `listSearchOptions` resolve.
- **hardening applied** — `is_p0` now guards `isinstance(group, list)` so even in-code misuse (a non-list group) can't raise; the evaluator is now total.
- **Verified clean:** no `_match_options` category/group collision (different signature tables); AC7 never-raises across 11 hostile inputs (all rejected at pydantic load or degrade to `False`); `priority>=5` matches 5/6 not 3/4; `cell_int` handles None/""/non-numeric; `AppConfig` loads with no `escalation:` key; bad `op` rejected at load.
- Note (documented footgun, not a bug): a YAML-quoted numeric threshold (`value: "5"`) fails closed silently — numeric thresholds must be unquoted.

**Suite:** 172 passed (was 161 at cycle start), ruff + mypy clean.

**Gate:** ✅ PASS — approved for merge.
