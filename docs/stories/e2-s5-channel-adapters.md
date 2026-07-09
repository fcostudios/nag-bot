# E2-S5: ChannelAdapter protocol + Email live + stubs

Status: Draft

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
- [ ] channels/base.py — AC1
- [ ] channels/email.py — AC2..AC4
- [ ] channels/teams.py, channels/whatsapp.py — AC5
- [ ] tests/unit/test_channels.py with recording fake SMTP — AC2..AC5

## Dev Notes
smtp_factory default: `lambda: smtplib.SMTP(host, port, timeout=30)`; STARTTLS when
cfg.smtp_starttls; login when username set. Fake SMTP records `starttls/login/send_message/
quit` calls. SendResult.detail for email: `"to=… cc=… subject=…"` (feeds ops dashboard).

## Testing
Live-path MIME assertions (To/Cc/subject/both parts), dry-run never-connects, skipped on
missing email, failed SMTP → `failed` result (exception captured, not raised).

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
