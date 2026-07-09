# E2-S5: ChannelAdapter protocol + Email live + stubs

Status: Done

## Story
As the nagbot, I want all channels behind one protocol with Email fully live, so that
digests actually reach inboxes now and Teams/WhatsApp can go live later without touching
the pipeline.

## Context
After E2-S4. Dry-run safety (FR13) is enforced *here*: adapters receive `dry_run` and
must not touch the network when it's true.

## Acceptance Criteria
- AC1: `ChannelAdapter` Protocol (`name`, `send_digest`, `send_rollup`) + `SendResult(channel, recipient, status: sent|failed|skipped|dry_run, detail)`; `build_adapters(cfg)` returns instances for `channels.enabled`.
- AC2: EmailAdapter live path: multipart/alternative (text+html), `To` owner email, `Cc` manager when `digest.escalated` non-empty, subject from Renderer, sent via injectable `smtp_factory` with STARTTLS + optional auth.
- AC3: EmailAdapter dry-run: renders subject+bodies fully (render errors surface), returns `dry_run` with recipients in detail, and the smtp_factory is **never invoked** (asserted).
- AC4: Owner without email → `skipped`, never an exception.
- AC5: Teams/WhatsApp stubs satisfy the protocol: render their payload (card JSON / template params), log it, return `dry_run` when dry_run else `skipped` with "not implemented until E5/E6".

## Tasks
- [x] channels/base.py — AC1
- [x] channels/email.py — AC2..AC4
- [x] channels/teams.py, channels/whatsapp.py — AC5
- [x] tests/unit/test_channels.py with recording fake SMTP — AC2..AC5

## Dev Notes
smtp_factory default: `lambda: smtplib.SMTP(host, port, timeout=30)`; STARTTLS when
cfg.smtp_starttls; login when username set. Fake SMTP records `starttls/login/send_message/
quit` calls. SendResult.detail for email: `"to=… cc=… subject=…"` (feeds ops dashboard).

## Testing
Live-path MIME assertions (To/Cc/subject/both parts), dry-run never-connects, skipped on
missing email, failed SMTP → `failed` result (exception captured, not raised).

## Dev Agent Record
- `build_adapters` takes the shared Renderer (constructed once per process) — adapters render, they don't own template state.
- EmailAdapter also implements `send_rollup` now (recipients from `fallback.rollup_recipients`) so E4-S2 only has to call it.
- WhatsApp stub exposes `build_payload()` publicly — E6-S1 reuses it verbatim and its param mapping is already unit-tested ([name, open, overdue, #oldest, days]).
- Teams stub renders the card on every call (stub or not) so template regressions surface in daily dry-runs, not in E5.
- SendResult carries `cc` so the send log records who was manager-CC'd.

## QA Results
- AC1 ✅ protocol + SendResult in base.py; `build_adapters` maps channels.enabled (email→live, teams/whatsapp→stubs).
- AC2 ✅ `test_live_send_builds_correct_mime` (starttls→login→send_message order, To/Cc/From/Subject, text+html parts); `test_no_escalation_means_no_cc`.
- AC3 ✅ `test_dry_run_never_touches_smtp` (factory never invoked; detail carries to=/cc=).
- AC4 ✅ `test_owner_without_email_is_skipped`.
- AC5 ✅ `test_teams_stub_renders_card`, `test_whatsapp_stub_payload_and_optout` (param mapping + opt-out skip); `test_smtp_failure_returns_failed_not_raises` covers NFR5.
- Suite: ruff/mypy clean, 80 passed. **Gate: PASS**
