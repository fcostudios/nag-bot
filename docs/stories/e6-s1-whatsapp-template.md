# E6-S1: WhatsApp Cloud API template send

Status: Done

## Story
As a technician who ignores email, I want the bluntest channel — a WhatsApp utility
message with my numbers — so that the nag is truly unavoidable.

## Context
Later cycle. Prereqs (user-side): Meta Business account, registered number,
**approved utility template** (draft in epic e6 header — submit early), env vars
WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_TEMPLATE_NAME.

## Acceptance Criteria
- AC1: WhatsAppAdapter.send_digest POSTs `https://graph.facebook.com/v20.0/{phone_number_id}/messages` with `type:"template"`, template name from env, params: name, open count, overdue count, oldest id, oldest days, dashboard/GLPI URL.
- AC2: 2xx → `sent` (message id in detail); 4xx/5xx → `failed` with error body snippet; per-recipient — one failure never aborts the loop.
- AC3: Dry-run logs the exact payload, no network.
- AC4: Owner without `whatsapp` → `skipped`.

## Tasks
- [x] channels/whatsapp.py live implementation (httpx, injectable) — AC1..AC4
- [x] respx tests — AC1..AC4

## Dev Notes
Graph API version pinned in one constant. Numbers must be E.164 (validate in config
load — add to OwnerCfg validator). Utility templates are cheap but *metered*: see E6-S2.

## Testing
respx: success, 400 invalid-param, 401 bad token; dry-run payload snapshot; E.164
validation unit test.

## Dev Agent Record
- Graph version pinned (`GRAPH_VERSION = "v20.0"`); Bearer auth; success extracts the `wamid` into SendResult detail for the ops log.
- Single-attempt sends (no retry): WhatsApp is per-recipient isolated by `_safe_send`, and duplicate utility messages on retry are worse than a missed nag (next morning re-nags anyway). Deviation from GLPI's retry pattern — deliberate, recorded here.
- Missing creds at send time → `skipped` with a naming detail (config validation already blocks enabling the channel without them; this covers dry-run-first setups).
- E.164 validator on `OwnerCfg.whatsapp` (`+[1-9]\d{6,14}`) fails config load, not send time.
- Rate-cap counter + `begin_run()` hook shipped here structurally (E6-S2 tests its semantics).

## QA Results
- AC1 ✅ `test_whatsapp_live_send_success` (endpoint URL, Bearer header, to=E.164, template name from config, param payload via existing build_payload test).
- AC2 ✅ `test_whatsapp_400_fails_with_detail`, `test_whatsapp_401_fails`; per-recipient isolation via `_safe_send` (E2-S6).
- AC3 ✅ `test_whatsapp_dry_run_no_network`.
- AC4 ✅ opt-out skip covered by `test_whatsapp_stub_payload_and_optout` (still green against the live adapter); `test_whatsapp_unconfigured_skips_live`; `test_e164_validation`.
- Suite: ruff/mypy clean, 130 passed. **Gate: PASS**
