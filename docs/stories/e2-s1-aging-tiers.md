# E2-S1: Business-day aging + tier engine

Status: Done

## Story
As the nagbot, I want pure functions that turn a ticket's dates into business-day age,
staleness, SLA status and a severity tier, so that nag pressure is fair (weekends and
holidays don't count) and fully testable.

## Context
After E1. Consumes `Ticket` (E1-S3) and `Thresholds` (E1-S2). No I/O; `now` injected.

## Acceptance Criteria
- AC1: `business_days_between(start, end, tz, holidays)` returns fractional business days; weekends and listed holidays contribute 0; computed in the configured tz.
- AC2: `compute_metrics(ticket, now, thresholds, tz, holidays)` → `TicketMetrics(age_bd, stale_bd, sla_status, sla_due)`; `time_to_resolve` None ⇒ `NO_SLA`; due within `sla_due_soon_hours` ⇒ `DUE_SOON`; past ⇒ `BREACHED`.
- AC3: `classify(metrics, thresholds)` implements ON_FIRE (BREACHED or stale≥7bd) > HOT (DUE_SOON or stale≥5bd) > AGING (stale≥2bd) > FRESH, with thresholds from config, not constants.
- AC4: Exact-boundary values classify into the *higher* tier (stale_bd == aging_stale_bd ⇒ AGING, etc.).
- AC5: Breach precedence: a breached ticket updated 5 minutes ago is still ON_FIRE.

## Tasks
- [x] engine/aging.py: SlaStatus, TicketMetrics, business_days_between, compute_metrics — AC1, AC2
- [x] engine/tiers.py: Tier (with worst-first sort order), classify — AC3..AC5
- [x] tests/unit/test_aging.py, test_tiers.py — all ACs

## Dev Notes
Fractional bd: iterate calendar days in tz between the two aware datetimes; full business
day = 1.0; partial first/last day = fraction of that day's elapsed time; skip Sat/Sun +
holidays. Guayaquil has no DST but keep the math tz-generic. `TIER_ORDER = {ON_FIRE:0,
HOT:1, AGING:2, FRESH:3}` exported for sorting.

## Testing
Parametrized tables: Fri 17:00 → Mon 09:00 spans, holiday spans, exact thresholds,
NO_SLA, breach precedence, age vs stale divergence, one non-UTC-offset sanity case.

## Dev Agent Record
- Split `compute_sla_status` out as its own pure function (easier to table-test than through compute_metrics).
- Exported `TIER_EMOJI`/`TIER_LABEL` alongside `TIER_ORDER` — renderer (E2-S4) and web (E3) share them, keeping badge semantics in one place.
- "Exactly 24h away" counts as DUE_SOON (<= comparison) and "exactly now" as BREACHED (>=) — boundary-inclusive toward urgency, consistent with AC4's tier boundaries.

## QA Results
- AC1 ✅ parametrized table: half-day, full day, Fri 17:00→Mon 09:00 weekend span, full week=5.0, inside-weekend=0, end<start=0, holiday zeroing, UTC-vs-local weekend boundary case.
- AC2 ✅ SLA table incl. None→NO_SLA, 24h boundary→DUE_SOON, now→BREACHED.
- AC3 ✅ classify table over all four tiers; `test_thresholds_come_from_config` proves no hardcoding.
- AC4 ✅ boundary rows 2.0/5.0/7.0 land in the higher tier.
- AC5 ✅ breached + stale 0.003bd → ON_FIRE.
- Suite: ruff/mypy clean, 54 passed. **Gate: PASS**
