---
baseline_commit: c095df484d25f70c0f5fa00991b4076e5c1ad293
---

# E7-S6: Transparency notice (compliance gate)

Status: done

<!-- bmad. Closes Module 1. Encodes the brief/UX consent decision: staff are notified ONCE that nagbot may WhatsApp/call them for P0 events (employment/legal basis, no P0 opt-out). Made an enforced gate, not just docs. -->

## Story

As **the operator enabling P0 escalation**,
I want **nagbot to refuse to page anyone until I've confirmed the staff transparency notice was given**,
so that **the LOPDP/consent requirement can't be skipped by accident — enabling escalation and having notified staff are two deliberate steps**.

## Context

- The brief + UX EXPERIENCE.md set the consent basis: employment/legal work coverage, **no per-event opt-in and no P0 opt-out**, paired with a **one-time transparency notice** that nagbot may message/call staff for certain events. This story makes that notice a **precondition in code**, plus ships the runbook.
- Cheap and low-risk — the escalation loop already gates on `enabled`; this adds a second required flag. But it turns a process promise into an enforced guardrail (consistent with "never cry wolf / compliance-by-construction").

## Acceptance Criteria

- **AC1:** `EscalationCfg` gains `transparency_notice_given: bool = False`. Escalation actually runs only when **`enabled` AND `transparency_notice_given`** are both true.
- **AC2:** In `execute_escalation_run`, if `enabled` but `transparency_notice_given` is false → **do not escalate** (return 0), and log a clear one-line warning naming the flag to set (so an operator who enabled it but forgot the notice sees why nothing fires). No alerts, no writes.
- **AC3:** With both flags true, escalation behaves exactly as E7-S3/S4/S5 (regression: the existing runner tests, updated to set the notice flag, still pass).
- **AC4:** Ships a **go-live runbook** `docs/e7-escalation-runbook.md` containing: the actual **transparency notice text** to give staff, and the operator go-live checklist (dedicated WhatsApp number + QR login, `OPENWA_IMAGE_TAG` pin, `OPENWA_WEBHOOK_SECRET`, the priority-5/6 P0 marking convention for triage, and the two flags to flip).
- **AC5:** no regressions; `ruff` + `mypy` + full suite green.

## Tasks

- [x] `src/nagbot/config.py` — add `transparency_notice_given: bool = False` to `EscalationCfg` (AC1).
- [x] `src/nagbot/run.py` — gate `execute_escalation_run` on the notice flag with a clear warning (AC2).
- [x] `docs/e7-escalation-runbook.md` — NEW runbook with the notice text + go-live checklist (AC4).
- [x] tests — enabled-but-no-notice → no escalation (0, warning); enabled+notice → escalates; update the existing runner-happy-path tests to set the flag (AC2, AC3).

## Dev Notes

- **Gate placement:** mirror the existing `if not cfg.app.escalation.enabled: return 0` early-return; add `if not cfg.app.escalation.transparency_notice_given` right after, with `logger.warning(...)`. Keep it before acquiring `_ESCALATION_LOCK`/fetching (a pure no-op).
- **Not opt-out:** this is an operator-side precondition, not a per-recipient opt-out (which the brief explicitly rules out for P0). Don't add per-owner opt-out.
- **Existing tests:** `_runtime(enabled=True)` in `test_escalation.py`/`test_ack.py` must now also set `transparency_notice_given=True` or the runner returns 0 — update the shared helper so all runner tests keep exercising the happy path.

### References

- [Source: product brief "Consent & Compliance"; UX EXPERIENCE.md §Foundation (informed PII decision, one-time transparency notice)]
- [Source: src/nagbot/run.py execute_escalation_run enabled-gate; config.py EscalationCfg]

## Testing

- `test_no_escalation_without_transparency_notice`: enabled=True, notice=False → `execute_escalation_run` returns 0, no active escalations, adapter not called.
- `test_escalates_when_notice_given`: enabled=True, notice=True → escalates (1 sent) — the existing happy path, via the updated helper.
- runbook: assert the file exists and contains the notice + go-live keywords (light doc test) — or verify manually.

Run `python -m pytest -q`; `ruff check`; `mypy src/nagbot`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (dev-story workflow)

### File List

- `src/nagbot/config.py` (transparency_notice_given flag)
- `src/nagbot/run.py` (compliance gate + once-per-process warn)
- `docs/e7-escalation-runbook.md` (new — notice text + go-live checklist)
- `tests/unit/test_escalation.py` (gate tests + shared `_runtime` helper)

## QA Results

**Verification:** adversarial reviewer. **Verdict: clean — ship it. No correctness/security/compliance defects.**

- **Gate completeness (verified):** the `transparency_notice_given` check is the sole chokepoint — placed before `_ESCALATION_LOCK` and any fetch/tick/ack-drain/dispatch/store write; `execute_escalation_run` is the *only* caller of the escalation internals (grep-confirmed), and the webhook only records acks (drained by the gated runner). No page is possible with the flag false, under any dry-run setting.
- **Default-safe:** `transparency_notice_given=False` by default; escalation requires `enabled AND transparency_notice_given` (AND, not OR).
- **Test integrity:** the shared `_runtime` helper defaults `notice=True` so existing runner tests still exercise the full path (not silently gated); the enabled-but-no-notice path is explicitly asserted (0 sent, nothing written).
- **Applied the one non-blocking nit:** the enabled-but-no-notice warning was logged every tick (60s) → throttled to **once per process**.

**Suite:** 221 passed, ruff + mypy clean.

**Gate:** ✅ PASS — approved for merge. Completes Epic 7 Module 1.
