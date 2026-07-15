---
baseline_commit: daedddf189f8133f3666fe7a09d97c3d8c1b9d4f
---

# E7-S5: Teams fallback

Status: done

<!-- bmad. Spine: AD-3 (composable send_alert fallback + alert_send_timeout), AD-7/AD-9 (Teams as the always-on fallback when OpenWA fails/session down). Builds on E7-S3 (dispatch fallback loop) + E7-S1 (send_alert capability). -->

## Story

As **the on-call team**,
I want **a P0 alert to fall through to Teams the moment the unofficial OpenWA channel fails or hangs**,
so that **a real P0 is never silenced by a banned number or a dead WhatsApp-Web session — delivery has two axes (roster climb + channel fallback)**.

## Context

- Closes the last E7-S3 documented deviation (`alert_send_timeout`) and realizes AD-3's multi-channel fallback + AD-9's "fall through on a defined health signal (send failure/timeout)".
- The **fallback loop already exists** (`_dispatch_one`, E7-S3): iterate `alert_channels`; `sent`/`dry_run` stops, `failed`/timeout/`skipped` falls through; fail-fast if none implement `send_alert`. E7-S5 makes **Teams a real alert channel** and makes OpenWA **fail fast** so the fallback actually fires.
- **Scope:** the failure-driven fallback. A *proactive* OpenWA session-health probe (AD-9) remains an ops follow-up.

## Acceptance Criteria

- **AC1:** `TeamsAdapter.send_alert(alert, *, dry_run) -> SendResult` posts an Adaptive Card (title "🔴 P0 escalation" + the alert text) to the Teams Workflow webhook, reusing the existing retry `_post`. `dry_run` → `dry_run` (no post); no webhook → `skipped`; non-2xx after retries → `failed`; 2xx → `sent`. No renderer needed (renderer is now optional on `TeamsAdapter`).
- **AC2:** `EscalationCfg.alert_channels` accepts `"teams"` (validator now allows `{openwa, teams}`); an unknown channel still fails loud at config load. Default remains `["openwa"]`; a user opts into fallback with `["openwa", "teams"]`.
- **AC3:** `build_alert_adapters(cfg, renderer)` wires `"teams"` → `TeamsAdapter(renderer, TEAMS_WEBHOOK_URL)` in the configured order; `make_jobs`' escalation job passes `rt.renderer`.
- **AC4 (fail-fast, `alert_send_timeout`):** new `EscalationCfg.alert_send_timeout` (default 15s); `OpenWaAdapter.from_config` uses it as the httpx timeout so a hung OpenWA raises → `failed` → the dispatch falls through to Teams (rather than blocking the tick).
- **AC5:** dispatch with `[openwa(failed), teams(sent)]` → the alert is sent once via Teams; both channels attempted in order. (`_dispatch_one` from E7-S3.)
- **AC6:** no regressions; `ruff` + `mypy` + full suite green.

## Tasks

- [x] `src/nagbot/channels/teams.py` — `send_alert` + `_alert_card`; renderer optional (assert on the digest paths).
- [x] `src/nagbot/channels/openwa.py` — `__init__` timeout; `from_config` uses `alert_send_timeout`.
- [x] `src/nagbot/config.py` — allow `"teams"`; add `alert_send_timeout`.
- [x] `src/nagbot/run.py` — `build_alert_adapters(cfg, renderer)` teams branch.
- [x] `src/nagbot/web/app.py` — escalation job passes `rt.renderer`.
- [x] tests — Teams `send_alert` (respx: sent/skipped/dry_run/failed), fallback openwa-failed→teams-sent, config accepts teams / rejects unknown, `build_alert_adapters` wires teams, from_config timeout.

## Dev Notes

- **Renderer optional:** `TeamsAdapter.send_alert` builds its own card and needs no renderer; `send_digest`/`send_rollup` keep an `assert self.renderer is not None` (only reached on the digest path, where it's always set via `build_adapters`).
- **Why timeout = fallback:** enforcing a wall-clock timeout around a sync `send_alert` needs a watchdog; instead the httpx client timeout makes a hung OpenWA raise `TimeoutException` → adapter returns `failed` → `_dispatch_one` moves to Teams. Simple and correct for the single-thread tick.
- **Deferred (documented):** a proactive OpenWA session-health probe + the `/healthz` escalation-liveness surface (AD-9) — the failure-driven fallback covers the P0-delivery guarantee; the probe is an ops nicety.

### References

- [Source: spine AD-3 (composable fallback + alert_send_timeout), AD-7/AD-9]
- [Source: src/nagbot/engine/escalation.py `_dispatch_one` (E7-S3 fallback loop); channels/teams.py `_post`; channels/openwa.py `from_config`]

## Testing

- Teams `send_alert`: respx 202 → sent (card carries the alert text + "P0 escalation"); dry_run → no post; no webhook → skipped; 400 → failed.
- Fallback: `[openwa(failed), teams(sent)]` → 1 sent, both called.
- Config: `["openwa","teams"]` accepted; `["sms"]` rejected at load.
- Wiring: `build_alert_adapters(cfg, None)` with `["openwa","teams"]` → `[OpenWaAdapter, TeamsAdapter]`; `OpenWaAdapter.from_config` honors `alert_send_timeout`.

Run `python -m pytest -q`; `ruff check`; `mypy src/nagbot`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (dev-story workflow)

### File List

- `src/nagbot/channels/teams.py` (send_alert + optional renderer)
- `src/nagbot/channels/openwa.py` (configurable timeout)
- `src/nagbot/config.py` (allow teams + alert_send_timeout)
- `src/nagbot/run.py` (build_alert_adapters teams branch)
- `src/nagbot/web/app.py` (escalation job passes renderer)
- `tests/unit/test_escalation.py`, `tests/unit/test_channels.py` (fallback + Teams alert tests)

## QA Results

**Verification:** adversarial reviewer (fallback correctness, the timeout→fail-fast crux, renderer-optional footgun, double-send, AC coverage). The reviewer stalled on a runtime watchdog (not a code issue) after finding **no bugs**; its probed paths were then verified directly + covered by new tests.

**Verified (no change needed):**
- **The crux (AC4):** httpx timeouts subclass `httpx.TransportError`, so a hung OpenWA is caught → `failed` → dispatch falls through to Teams (never blocks/crashes the tick). Confirmed empirically + `test_openwa_timeout_is_failed_not_raises`.
- **Fallback (AD-3):** `_dispatch_one` honors channel order; `sent`/`dry_run` stops at the first success (openwa not re-called), `failed`/`skipped`/timeout falls through, both-fail → no persist → retry next tick. New tests: `test_dispatch_stops_at_first_sent_channel`, `test_dispatch_both_channels_fail_no_persist`, `test_dispatch_falls_through_to_teams_when_openwa_fails`.
- **Renderer-optional:** only `send_alert` runs renderer-less; `build_adapters` (digest path) always constructs Teams with a renderer; the digest methods `assert` it.
- **Card payload:** `alert.text` is JSON-embedded via httpx `json=` (no injection); no secret in the card.

**Known/inherent (documented):** if OpenWA actually delivered but reported `failed`/timeout, the alert also sends on Teams (a rare double-page) — inherent to fail-open fallback; `send_log` is per-attempt so both are recorded. A *proactive* OpenWA session-health probe (AD-9) remains an ops follow-up.

**Suite:** 218 passed (was 215 at cycle start / 186 at S3 start), ruff + mypy clean.

**Gate:** ✅ PASS — approved for merge. Closes the S3 `alert_send_timeout` deviation.
