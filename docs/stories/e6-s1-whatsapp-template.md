# E6-S1: WhatsApp Cloud API template send

Status: Draft

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
- [ ] channels/whatsapp.py live implementation (httpx, injectable) — AC1..AC4
- [ ] respx tests — AC1..AC4

## Dev Notes
Graph API version pinned in one constant. Numbers must be E.164 (validate in config
load — add to OwnerCfg validator). Utility templates are cheap but *metered*: see E6-S2.

## Testing
respx: success, 400 invalid-param, 401 bad token; dry-run payload snapshot; E.164
validation unit test.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
