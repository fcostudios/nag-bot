---
baseline_commit: ab53ccb8ac4950cfec75cd11957cf20aecba4cca
---

# E7-S1: OpenWA sidecar + WhatsApp-Web channel adapter

Status: done

<!-- bmad create-story. Governing spec: _bmad-output/planning-artifacts/architecture/architecture-e7-urgent-p0-escalation/ARCHITECTURE-SPINE.md (AD-2, AD-3, AD-9). Epic: docs/epics/e7-urgent-p0-escalation.md. -->

## Story

As **nagbot**,
I want **a self-hosted OpenWA WhatsApp channel — a sidecar service plus a Python adapter that can send a WhatsApp text end-to-end**,
so that **later stories (E7-S3) can dispatch urgent P0 alerts over WhatsApp without me driving a browser or coupling to a session lifecycle**.

## Context

- **Foundation story of Epic 7.** Delivers only the transport: the Python `OpenWaAdapter` + its config + the `docker-compose` sidecar. It does **not** build the escalation engine, P0 detection, the ack webhook, or Teams fallback — those are E7-S3/S2/S4/S5.
- **Spine constraints (binding):**
  - **AD-2** — OpenWA runs as its **own container** (`openwa/wa-automate`) exposing an HTTP API; the adapter is a thin `httpx` client to `OPENWA_URL`; the WA-Web session/QR + volume live in the sidecar. Nagbot never drives a browser.
  - **AD-3** — OpenWA is an **alert** channel: it implements the new optional `send_alert(alert, *, dry_run) -> SendResult` capability (parallel to the existing optional `begin_run`), returning the standard `SendResult` statuses. It is **not** a digest channel (no `send_digest` behaviour required).
  - **AD-9** — the live WhatsApp-Web QR session is an **ops/runbook** concern (session recovery, QR re-auth). Out of scope to *run* here; the sidecar config + a note is the deliverable.
- **Pattern to mirror:** `src/nagbot/channels/whatsapp.py` (`WhatsAppAdapter`: `name`, `_configured`, dry-run handling, `httpx.Client`, `SendResult`) and the respx-mocked adapter tests in `tests/unit/test_channels.py`.

## Acceptance Criteria

- **AC1:** New `EscalationAlert` dataclass in `src/nagbot/channels/base.py` — minimal for now: `recipient` (E.164 WhatsApp number) + `text` (the message body). (E7-S3 will enrich content; keep it small.)
- **AC2:** New `src/nagbot/channels/openwa.py` with `OpenWaAdapter` (`name = "openwa"`), constructed with a base URL and an optional injected `httpx.Client`. It exposes `send_alert(alert: EscalationAlert, *, dry_run: bool) -> SendResult` that POSTs to the sidecar EASY API (`{OPENWA_URL}/sendText` with JSON `{"chatId": <normalized>, "message": alert.text}`) and maps the outcome to `SendResult(channel="openwa", recipient=alert.recipient, status=…)`.
- **AC3:** **dry_run** → returns `SendResult(status="dry_run")` and makes **no** HTTP call.
- **AC4:** **Not configured** (no `OPENWA_URL`) → returns `status="skipped"` with a clear detail; no HTTP call. Also skip (status `skipped`) when `alert.recipient` is empty.
- **AC5:** **HTTP/transport failure** (5xx, connect error, non-2xx, or an OpenWA error body) → returns `status="failed"` with a detail; the adapter **never raises** out of `send_alert` (a P0 dispatch must degrade, not crash — never-cry-wolf/reliability).
- **AC6:** **Success** (2xx + OpenWA success body) → `status="sent"`.
- **AC7:** Recipient number → **chatId normalization**: an E.164 like `+593999999999` becomes the WhatsApp chatId form `593999999999@c.us` (strip `+`, append `@c.us`). Unit-tested.
- **AC8:** Config: `OPENWA_URL` and `OPENWA_WEBHOOK_SECRET` added to `EnvSettings` (secrets/endpoints per the config split). `"openwa"` added to the `ChannelName` literal is **not** required (it is not a digest channel); instead provide an `OpenWaAdapter.from_config(cfg)` (or equivalent) construction seam the E7-S3 escalation builder will use. If you do surface it via config validation, gate it behind escalation being enabled — do not break existing channel validation.
- **AC9:** Deployment: `docker-compose.yml` gains an `openwa` service — `openwa/wa-automate` image **pinned to a specific tag**, an exposed HTTP port, a **named volume for the session**, and the `-w` webhook argument pointing at the nagbot `/webhooks/openwa` endpoint (the endpoint itself is E7-S4). Config only; not started in CI.
- **AC10:** No regressions — existing channels, config load, and the full suite stay green; `ruff` clean.

## Tasks

- [x] `src/nagbot/channels/base.py` — add `EscalationAlert` dataclass (recipient, text). Keep `ChannelAdapter`/`SendResult`/`begin_run` untouched (AC1).
- [x] `src/nagbot/channels/openwa.py` — NEW `OpenWaAdapter`: `name`, `_configured`, injectable `httpx.Client`, `send_alert(...)`, chatId normalization, robust error handling → `SendResult` (AC2–AC7). Mirror `whatsapp.py`.
- [x] `src/nagbot/config.py` — add `OPENWA_URL` + `OPENWA_WEBHOOK_SECRET` to `EnvSettings`; add the `OpenWaAdapter` construction seam; keep existing channel validation intact (AC8).
- [x] `docker-compose.yml` — add the pinned `openwa` sidecar service (image, port, session volume, `-w` webhook) (AC9).
- [x] `tests/unit/test_channels.py` (or a new `tests/unit/test_openwa.py`) — respx-mocked tests for AC3–AC7 (AC10).

## Dev Notes

- **Alert vs digest:** do NOT add `send_digest`/`send_rollup` behaviour to `OpenWaAdapter` or wire it into `build_adapters` (that iterates digest channels in `channels/base.py:41`). OpenWA is dispatched by the escalation engine (E7-S3) via `send_alert`. Keeping it out of `build_adapters` avoids sending unofficial-WhatsApp *digests* (the official Cloud API channel E6 owns digests).
- **`send_alert` as an optional capability:** follow the `begin_run` precedent (`channels/base.py:33-38`) — it's discovered via `getattr`, not part of the `ChannelAdapter` Protocol. Define `EscalationAlert` in `base.py` so both `openwa` and (later) `teams` can import it.
- **HTTP client:** mirror `WhatsAppAdapter.__init__` (`self._http = http or httpx.Client(timeout=30)`) so tests inject/respx-mock it. The EASY API send endpoint is `POST /sendText`; treat a non-2xx or a JSON body without a success indicator as `failed`.
- **chatId:** OpenWA addresses individuals as `<digits>@c.us`. Normalize from the stored E.164 (`owner.whatsapp`, already E.164-validated at config load, `config.py:97`).
- **Reliability (AD-6/AD-3 spirit):** `send_alert` must catch transport exceptions and return `failed`, never propagate — a later rung/fallback depends on a status, not an exception.
- **Sidecar (AD-2/AD-9):** the container holds the browser + session; document that first-run requires scanning a QR (ops runbook, E7-S1 note). Pin the image tag — do not use `:latest`.

### Project Structure Notes

- New adapter joins `src/nagbot/channels/`. No store/schema change. No change to the digest run.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-e7-urgent-p0-escalation/ARCHITECTURE-SPINE.md#AD-2, #AD-3, #AD-9]
- [Source: docs/epics/e7-urgent-p0-escalation.md] — E7-S1 row.
- [Source: src/nagbot/channels/whatsapp.py] — adapter pattern (httpx, `_configured`, dry-run, SendResult).
- [Source: src/nagbot/channels/base.py:16-38] — `SendResult`, `ChannelAdapter`, `begin_run` optional-capability precedent.
- [Source: src/nagbot/config.py:19,26,42-46,77-80] — `ChannelName`, `EnvSettings`, `ChannelsCfg`.
- [Source: tests/unit/test_channels.py:169-206] — respx-mocked adapter test style.

## Testing

`pytest` + `respx` (as in `tests/unit/test_channels.py` Teams tests). Mock `POST {OPENWA_URL}/sendText`.

- **test_openwa_send_alert_success:** 2xx + success body → `SendResult(status="sent")`; assert the request chatId = `593999999999@c.us` and message body.
- **test_openwa_dry_run_no_network:** `dry_run=True` → `status="dry_run"`, respx route **not** called.
- **test_openwa_not_configured_skipped:** empty `OPENWA_URL` → `status="skipped"`, no HTTP.
- **test_openwa_empty_recipient_skipped:** blank recipient → `skipped`.
- **test_openwa_http_5xx_failed:** `respx` returns 503 → `status="failed"`, does not raise.
- **test_openwa_transport_error_failed:** respx `side_effect=httpx.ConnectError` → `failed`, does not raise.
- **test_openwa_chatid_normalization:** `+593999999999` → `593999999999@c.us`.

Run `python -m pytest tests/unit/test_channels.py -q` then the full suite; `ruff check`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (bmad-dev-story)

### Debug Log References

- RED: `test_openwa.py` failed on missing `EscalationAlert` import. GREEN after base/openwa/config.
- 8 E7-S1 tests pass; full suite 158 (was 150); ruff + mypy clean.

### Completion Notes List

- `EscalationAlert` (recipient, text) added to `channels/base.py` (untouched `ChannelAdapter`/`SendResult`/`begin_run`).
- `channels/openwa.py`: `OpenWaAdapter` (alert channel, AD-3) — `send_alert` posts `{chatId, message}` to `{OPENWA_URL}/sendText`; `to_chat_id` normalizes E.164 → `<digits>@c.us`; dry_run/skipped(no url or no recipient)/failed(HTTP/transport/openwa-error-body)/sent; **never raises**. `from_config` seam for the E7-S3 escalation builder (deliberately NOT wired into `build_adapters` — OpenWA is not a digest channel).
- `config.py`: `OPENWA_URL` + `OPENWA_WEBHOOK_SECRET` in `EnvSettings`; existing channel validation untouched.
- `docker-compose.yml`: pinned `openwa` sidecar (`OPENWA_IMAGE_TAG` required — fails fast, never `:latest`), session volume, `-w` webhook → `/webhooks/openwa` (endpoint is E7-S4).
- Out of scope (later): escalation engine (E7-S3), P0 detect (E7-S2), webhook endpoint (E7-S4), Teams fallback (E7-S5). Live QR session is ops (AD-9).

### File List

- `src/nagbot/channels/base.py` (modified — `EscalationAlert`)
- `src/nagbot/channels/openwa.py` (new — `OpenWaAdapter`, `to_chat_id`)
- `src/nagbot/config.py` (modified — `OPENWA_URL`, `OPENWA_WEBHOOK_SECRET`)
- `docker-compose.yml` (modified — `openwa` sidecar service + volume)
- `tests/unit/test_openwa.py` (new — 8 respx-mocked tests)

## QA Results

**Review:** adversarial code review vs baseline `ab53ccb` (correctness / AC1–AC10 / security).

- **[MED] fixed** — AC5 "never raises" was violable: a 2xx with a non-object JSON body (`[]`/`true`/`null`) made `.get()` raise `AttributeError` out of `send_alert`. Fixed with an `isinstance(body, dict)` guard; added `test_non_object_json_2xx_never_raises_sent` + non-JSON-2xx + success-key-absent tests.
- **Clean:** `to_chat_id` edge cases (AC7); status precedence recipient→dry_run→configured→post (AC3/AC4); `{"success": false}`→failed; AC8 config seam (no `build_adapters` wiring, existing channel validation intact); AC9 compose pins `OPENWA_IMAGE_TAG` (never `:latest`); security — `httpx json=` safe, no secrets logged, `OPENWA_WEBHOOK_SECRET` correctly unused until E7-S4.

**Suite:** 161 passed (was 150 at epic start of this cycle / baseline), ruff + mypy clean.

**Gate:** ✅ PASS — approved for merge.
