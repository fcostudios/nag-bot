---
baseline_commit: e0f5c7f35be3f22e4aff99f862f51f3bfa9a1bbe
---

# E7-S4: Acknowledgement + live re-validation

Status: done

<!-- bmad create-story. Spine: AD-6 (re-validate via get_ticket before dispatch; fetch-failure never stops), AD-7 (two ack sources; webhook secret; sender-must-match-roster; writes p0_ack_inbox), AD-4 (single-writer p0_escalations; webhook writes the ack inbox, engine drains it). Builds on E7-S3. -->

## Story

As **the on-call team**,
I want **nagbot to stop escalating the instant a P0 is handled — a WhatsApp reply OR the ticket actually moving — and to double-check the live ticket right before it pages anyone**,
so that **nobody is ever paged about a ticket that is already resolved, reassigned, or acknowledged (never cry wolf)**.

## Context

- Closes two of the three E7-S3 documented deviations: adds the AD-6 per-dispatch `get_ticket` re-validation and the AD-7 ack path. (The send/log/persist atomicity item remains a separate follow-up.)
- **Spine (binding):** AD-6 — re-fetch the ticket immediately before each rung dispatch; if resolved/closed/reassigned/downgraded (no longer `is_p0`) → stop instantly; a **fetch failure is never a stop** (don't dispatch, retry next tick). AD-7 — an ack is (1) an inbound WhatsApp reply via `POST /webhooks/openwa` (authed by `OPENWA_WEBHOOK_SECRET`, **sender must match roster**), or (2) a GLPI status change seen on the re-fetch; either **halts the climb**. AD-4 — the webhook writes only the **append-only `p0_ack_inbox`**; the escalation engine/runner drains it (single writer of `p0_escalations` preserved).
- **Reuse:** `is_p0` (E7-S2), `escalation_chain`/`escalation_tick` (E7-S3), `GlpiClient` + `FieldMap.to_ticket` (search-by-id), the app auth middleware + `OPENWA_WEBHOOK_SECRET` (E7-S1), the store `_row_to_*` pattern.

## Acceptance Criteria

- **AC1 (get_ticket):** `GlpiClient.get_ticket(ticket_id, field_map) -> Ticket | None` — a single-ticket fetch via `/search/Ticket` with an id-equals criterion + `forcedisplay`; returns the parsed `Ticket` or `None` if not found / not open (no `notold` filter needed — the caller re-checks `is_p0`/status).
- **AC2 (re-validate before dispatch, AD-6):** in `execute_escalation_run`, before dispatching a tick's alert, re-fetch that ticket via `get_ticket`; if it's `None` or **not `is_p0`** → drop the alert and `stop_p0_escalation(reason="revalidated_not_p0")`. A `get_ticket` **exception** → drop the alert for this tick (do **not** stop, do not advance) — retry next tick.
- **AC3 (ack store, AD-4/AD-7):** migration 004 `p0_ack_inbox(id PK, sender, text, received_at, processed_at)` + `AckRow` + accessors `append_ack(sender, text, now)`, `unprocessed_acks()`, `mark_acks_processed(ids, now)`, and `set_p0_acknowledged(ticket_id, by, now)` (targeted UPDATE of `acknowledged_at/by`, never `INSERT OR REPLACE`).
- **AC4 (drain + halt, AD-7):** at the start of `execute_escalation_run`, drain `unprocessed_acks`: for each active, not-yet-acked escalation whose ticket's `escalation_chain` includes an ack sender's number → `set_p0_acknowledged`; then `mark_acks_processed`. `escalation_tick` **must not climb** an escalation with `acknowledged_at` set (hold), but AD-6/stop still applies (a resolved ack'd ticket stops).
- **AC5 (webhook, AD-7):** `POST /webhooks/openwa` — authed by `OPENWA_WEBHOOK_SECRET` (checked in the middleware for that path; **not** Basic, **not** in `AUTH_EXEMPT_PREFIXES`). Parses the OpenWA message payload (`from` chatId + `body`), normalizes `from` (`<digits>@c.us` → `+<digits>`), and **only if the sender matches a roster `whatsapp`** appends to `p0_ack_inbox`; a non-roster sender is accepted (200) but ignored. Missing/invalid secret → 401. Read-only re: `p0_escalations` (writes only the inbox).
- **AC6 (safety):** `enabled=False` → the escalation loop is a no-op (unchanged). No secret configured → the webhook path 401s (never open). No writes to digest tables.
- **AC7:** no regressions; `ruff` + `mypy` + full suite green.

## Tasks

- [x] `src/nagbot/glpi/client.py` — `get_ticket` single-fetch (AC1).
- [x] `src/nagbot/store/db.py` + `repo.py` — migration 004 + `AckRow` + inbox accessors + `set_p0_acknowledged` (AC3).
- [x] `src/nagbot/engine/escalation.py` — `escalation_tick` holds (no climb) when `existing.acknowledged_at` is set (AC4).
- [x] `src/nagbot/run.py` — ack drain + AD-6 re-validation in `execute_escalation_run` (AC2, AC4).
- [x] `src/nagbot/web/app.py` — middleware webhook-secret auth + `POST /webhooks/openwa` route (AC5).
- [x] tests — `get_ticket` (respx), inbox store round-trip, tick-holds-on-ack, re-validate drops+stops non-P0 / keeps on fetch-error, webhook auth + roster-match + inbox write.

## Dev Notes

- **get_ticket shape:** reuse the search path (criteria field 2 = id, `searchtype=equals`, `range=0-0`, `forcedisplay`) so `to_ticket` parses the same row shape as `search_open_tickets`; empty `data` → `None`.
- **Re-validation placement:** keep `escalation_tick` pure; do the `get_ticket` I/O in `execute_escalation_run` between `tick` and `dispatch_alerts`. One extra client session for the (few) alert tickets is fine. On any exception opening the client or fetching → treat as "blind": drop the alert(s), don't stop.
- **Ack→ticket association:** an inbound reply carries the sender, not a ticket id. Resolve by: an ack from sender S acks every active, un-acked escalation whose current `escalation_chain` (built from the fetched ticket) contains S's number. Deterministic; safe (only people in the chain can ack). The "re-notify if no progress after ack" refinement is **deferred** (documented) — S4 just halts the climb on ack.
- **Webhook auth in middleware (AD-7):** handle the `/webhooks/openwa` path in `basic_auth` before the Basic check — require `X-Webhook-Secret == OPENWA_WEBHOOK_SECRET` (`secrets.compare_digest`); don't add the path to `AUTH_EXEMPT_PREFIXES`.
- **AD-4 preserved:** the webhook writes only `p0_ack_inbox`; `set_p0_acknowledged` runs inside the runner (the single writer), never from the web thread.
- **Do NOT** build Teams fallback (E7-S5) or the re-notify-after-ack cadence here.
- **AD-7 ack source #2 — partial (documented):** a GLPI status change that takes the ticket *out* of P0 (solved/closed/downgraded) **stops** the escalation (via `get_ticket` re-validate → `None`/not-P0, and the AD-5 batch gate). The *keep-open* status-change ack (e.g. status → "Processing" while still priority ≥5) is **not** treated as an ack-hold in S4 — it keeps climbing until a reply arrives or it leaves the P0 set. Deferred (needs a status→ack mapping); never-cry-wolf is preserved either way.

### References

- [Source: architecture spine AD-4/AD-6/AD-7]
- [Source: src/nagbot/glpi/client.py search_open_tickets; fields.py to_ticket/forcedisplay]
- [Source: src/nagbot/engine/escalation.py escalation_tick; run.py execute_escalation_run (E7-S3)]
- [Source: src/nagbot/web/app.py basic_auth middleware + is_auth_exempt; config OPENWA_WEBHOOK_SECRET (E7-S1)]
- [Source: src/nagbot/store/repo.py p0_escalations pattern]

## Testing

- **get_ticket:** respx a `/search/Ticket` id query → one row → Ticket; empty data → None.
- **inbox store:** append → unprocessed → mark processed → empty; `set_p0_acknowledged` sets ack columns only.
- **tick holds on ack:** an active escalation with `acknowledged_at` set + dwell elapsed → no climb; a resolved ack'd ticket (not in P0 set) → still stops.
- **re-validate:** runner with a fake glpi where the alert ticket comes back not-P0 → alert dropped + escalation stopped; get_ticket raises → alert dropped, escalation NOT stopped.
- **webhook:** no/invalid secret → 401; valid secret + roster sender → 200 + inbox row; non-roster sender → 200 + no inbox row.

Run `python -m pytest -q`; `ruff check`; `mypy src/nagbot`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (dev-story workflow)

### Completion Notes List

- `GlpiClient.get_ticket(id, field_map)` single-fetch (search-by-id, same row shape as batch).
- store: migration 004 `p0_ack_inbox` + `AckRow` + `append_ack`/`unprocessed_acks`/`mark_acks_processed`; `set_p0_acknowledged` (targeted UPDATE, guarded `acknowledged_at IS NULL`).
- `escalation_tick`: holds (no climb) when `acknowledged_at` set; AD-5 stop still applies.
- `run.py`: `_drain_acks` (roster-sender → ack every active un-acked escalation whose chain includes the sender) + `_revalidate_alerts` (AD-6: get_ticket before dispatch; not-P0 → stop; fetch-error → drop this tick, never stop). Refactored persistence: `persist_tick_state` (anchors/stops) runs BEFORE re-validation so an AD-6 stop lands on a persisted row; `dispatch_alerts` now handles only alerts.
- `web/app.py`: middleware authenticates `POST /webhooks/openwa` via `OPENWA_WEBHOOK_SECRET` (not Basic, not AUTH_EXEMPT); route writes ONLY the ack inbox, and only when the (normalized) sender matches a roster whatsapp.
- Deferred (documented): re-notify-after-ack cadence; Teams fallback (E7-S5).

### File List

- `src/nagbot/glpi/client.py` (get_ticket)
- `src/nagbot/store/db.py`, `store/repo.py` (migration 004 + AckRow + accessors + set_p0_acknowledged)
- `src/nagbot/engine/escalation.py` (tick holds on ack; persist_tick_state split)
- `src/nagbot/run.py` (_drain_acks, _revalidate_alerts, runner reorder)
- `src/nagbot/web/app.py` (webhook auth + route + _normalize_chatid)
- `tests/unit/test_ack.py` (new), `tests/glpi/test_client.py`, `tests/integration/test_web.py`, `tests/unit/test_escalation.py`

## QA Results

**Verification:** 2 adversarial reviewers (webhook/ack security + AD-4/6/7 & AC audit). Fixes applied + re-tested.

**Fixed:**
- **[HIGH] Valid acks silently dropped** — `_drain_acks` marked *every* ack processed even when no active escalation matched, so a reply arriving before its escalation was anchored was consumed and lost (the escalation kept climbing despite a genuine "on it"). Fixed: only **applied** acks are consumed; unmatched acks are **retained** for a later tick, with an `ack_ttl_minutes` (default 120) sweep to bound the inbox. Tests: `test_ack_retained_until_escalation_exists`.
- **[MED] `get_ticket` treated solved tickets as still-P0** — no open-status filter, and the default rule has no status condition, so a ticket *solved* between fetch and re-validate would keep escalating. Fixed: `get_ticket` now filters `notold` → a solved ticket returns `None` → re-validate stops it (this also realizes AD-7's GLPI-status-change→stop path). Test: `test_revalidate_stops_when_ticket_solved`.
- **[coverage] unconfigured-secret → 401** — added `test_webhook_401_when_secret_unconfigured`.
- **[docs] AD-7 ack source #2** — the *keep-open* status-change ack-hold is explicitly deferred in Dev Notes (out-of-P0 changes already stop; never-cry-wolf preserved).

**Verified sound (no change):** webhook auth (`secrets.compare_digest`; 401 on unset/missing/wrong/empty; fails closed on trailing slash; secret never logged); AD-4 single-writer (webhook writes only the ack inbox; all `p0_escalations` writes are targeted UPDATEs under `_ESCALATION_LOCK`); persist→revalidate→dispatch ordering (AD-6 stop lands on a persisted row); both open + climb alerts re-validated; fetch-failure-never-stops; no SQL injection. **Audit verdict: no real bugs.**

**Accepted by design (documented):** a single `default_triage` number can ack every active P0 at once (triage "I've got the board") — noted as an operational consideration.

**Suite:** 207 passed (was 186 at cycle start), ruff + mypy clean.

**Gate:** ✅ PASS — approved for merge.
