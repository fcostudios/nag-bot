# Rubric Review — Architecture Spine: Epic 7 (Urgent P0 Escalation)

**Spine:** `_bmad-output/planning-artifacts/architecture/architecture-e7-urgent-p0-escalation/ARCHITECTURE-SPINE.md`
**Reviewer stance:** good-spine rubric walk. Terse, judgment-first.
**Verdict:** **PASS with reservations.** A tight, well-fitted brownfield spine that ratifies the existing codebase and fixes the real story-level divergences. Downgraded from clean-pass by one whole silent dimension (the OPERATIONAL envelope) and one soft rule.

---

## 1. Does it fix the real divergence points for E7-S1..S6, and miss none?

**Verdict: YES — the six real forks are each pinned by an AD.**

The genuine places two stories could build incompatibly are all decided:

- **S1 (OpenWA)** — process boundary decided (AD-2: out-of-process sidecar, thin `httpx` client), so S1 can't embed Node and S3 can't assume in-process calls.
- **S2/S3 (dispatch shape)** — AD-3 forbids overloading `send_digest` with synthetic single-ticket digests; new optional `send_alert(EscalationAlert)` capability. This is *the* adapter-contract fork and it's closed.
- **S3/S4 (state ownership)** — AD-4 makes `p0_escalations` single-writer (`engine/escalation.py` only), which prevents the digest run and escalation loop diverging on state. The real lost-update race is named and prevented.
- **S2/S3 (severity/timing source)** — AD-5 forces all P0 semantics + cadence into `EscalationCfg`, so no two stories hardcode different literals.
- **S4 (ack + truth)** — AD-6/AD-7 pin re-validation-before-every-rung and the two ack sources. This is where "never cry wolf" would otherwise fragment across stories.
- **S1/S5 (delivery path)** — AD-7 makes Teams the always-on fallback, so S5 isn't left to invent its own trigger.

**Miss check:** The scheduler-cadence fork (fast loop vs. daily cron) is caught by AD-1. Lock-sharing (`_ESCALATION_LOCK` vs `_RUN_LOCK`) is caught. I found **no un-pinned cross-story divergence** at this altitude. S6 is correctly flagged as process/config only, no invariant.

**Minor:** The **E4-reuse contract** the epic asserts ("reuse red-streak escalation plumbing") is *not* honored literally — the existing `escalations`/`EscalationRow` table (consecutive_red_days) is E4's plumbing, and the spine adds a *separate* `p0_escalations` table rather than extending it. That is arguably the *correct* call (different concern), but the spine states it "mirrors" the pattern without explicitly resolving the epic's "reuse" language. Low severity: a naming/lineage note, not a divergence.

---

## 2. Is every AD's Rule enforceable, and does it prevent its stated divergence?

**Verdict: MOSTLY YES — six of seven are hard; AD-7's fallback trigger is soft.**

- AD-1: enforceable (distinct job + named lock + idempotency-from-state). ✅
- AD-2: enforceable (separate container, `OpenWaAdapter` = `httpx` to `OPENWA_URL`; "nagbot never drives a browser" is a checkable structural fact). ✅
- AD-3: enforceable (optional method on the port, mirrors the existing `begin_run` getattr pattern — verified present in `channels/base.py`). ✅
- AD-4: enforceable and *checkable in review* ("only `engine/escalation.py` writes it"). Strong. ✅
- AD-5: enforceable (config schema + "no severity/timing literal in code"). ✅ — though the P0 rule itself is `[ASSUMPTION]` (see Open Questions; correctly deferred).
- AD-6: enforceable and load-bearing (new `get_ticket(id)` single-fetch — verified the client is batch-only today, so this is a real, concrete addition, not a hand-wave). ✅ This is the strongest rule in the spine.
- **AD-7: SOFT.** "If an OpenWA `send_alert` fails **or the session is down**, dispatch via Teams." *Fail* is observable (a `failed` SendResult). *"Session is down"* is **not defined as a signal** — OpenWA can accept a send that never actually delivers (WA-Web silently logged out). Without a defined health/liveness probe or delivery-confirmation, the fallback rule can't fire reliably, which undercuts the one resilience guarantee the epic verifies in test ("P0 still lands via Teams when OpenWA unavailable"). **Med severity.** Tighten: define what "session down" *is* (health endpoint poll / send-then-confirm / heartbeat) and make that the fallback trigger.

---

## 3. Could anything under Deferred let two units diverge?

**Verdict: NO.** All three deferrals are additive and seam-guarded:

- Per-tier SLA dwell — "config seam exists; values are the extension." A pure value-later; can't fork structure.
- Phone-**call** rung — explicitly a *future third capability* (`send_call`), parallel to `send_alert`; won't retro-break `send_alert`.
- Stats/analytics — read-only downstream.

None removes a decision two current stories both depend on. Clean.

---

## 4. Is named tech verified-current, and does the spine RATIFY the brownfield codebase?

**Verdict: STRONG YES on ratification; tech is current with one honestly-hedged item.**

Every "existing" claim was checked against the code and **all match**:
- `ChannelAdapter` port + frozen `SendResult(channel, recipient, status, detail, cc)` — exact. ✅
- `EnvSettings`/`AppConfig`/frozen `RuntimeConfig` split + **`OwnerCfg.manager` already present** — exact. ✅
- `escalations` table + frozen `*Row` one-table-per-concern — exact. ✅
- `_RUN_LOCK` (threading.Lock), APScheduler, **dry-run hard default** (`env or app`) — exact. ✅
- GLPI **batch-only** (`search_open_tickets`, no single fetch) + `FieldMap.discover()` + Ticket lacks priority/urgency/impact — exact. This makes AD-5/AD-6's "new work" claims accurate, not aspirational. ✅
- FastAPI app + `AUTH_EXEMPT_PREFIXES` (spine correctly says webhook is *not* exempt) — exact. ✅
- Teams + WhatsApp adapters exist; **`send_log.kind` already carries "escalation"** — exact. ✅

The spine **contradicts nothing** in the codebase and reuses real seams (`begin_run` optionality → `send_alert` optionality; `send_log.kind`; FastAPI host for the webhook). This is model brownfield discipline.

**Tech currency:** Python 3.13 / APScheduler / FastAPI / httpx / SQLite-WAL are all reused-existing (no new pins to verify). The one new dependency, the **`openwa/wa-automate` Docker image**, is correctly flagged `[ASSUMPTION] pin a specific tag at build` — the research doc confirms OpenWA is a self-hosted Node library requiring a sidecar+HTTP bridge, matching AD-2. Honest hedge, not a gap.

---

## 5. Does it cover the epic/brief's Module-1 capabilities?

**Verdict: YES — full six-capability coverage.** The Capability→Architecture Map traces each:

| Brief capability | Covered |
|---|---|
| Detection | S2 → AD-5 (`EscalationCfg.p0_rule` + GLPI field extension) ✅ |
| Verification gate | S2 → AD-6 (re-validate via `get_ticket`) ✅ |
| Roster + climbing ladder | S3 → AD-1/3/4/5 (state machine + chain config) ✅ |
| Ack + re-validate/stop | S4 → AD-4/6/7 (webhook + re-fetch + `stopped_reason`) ✅ |
| Teams fallback | S5 → AD-7 ✅ |
| Transparency notice | S6 → config/process ✅ |

Message content ("system · time · what-broke · link") is carried by `EscalationAlert` (S3 map). Auto-move-status-on-ack is present (AD-7 "MAY auto-move," target deferred to an Open Question). Back-off-with-warning appears in the state-machine diagram. **Nothing in Module-1 scope is unaddressed.**

---

## 6. Is every dimension the epic altitude owns decided/deferred/open — esp. the OPERATIONAL envelope?

**Verdict: NO — the OPERATIONAL dimension is largely SILENT. This is the spine's biggest gap.**

The brief and epic both name ops as a first-class risk, twice and explicitly:
- Epic: *"who watches/recovers the OpenWA session (QR re-auth, failover to Teams)"* — an **ops prerequisite**.
- Brief risks: *"WhatsApp ban / session ops: dedicated number, ban-avoidance pacing, and who watches/recovers the OpenWA session (QR re-auth)."*

The spine covers **deployment/topology** well (docker-compose diagram, session volume in the sidecar, container boundaries) — that sub-dimension is decided. But the rest of the operational envelope is not decided, deferred, *or* listed as an open question:

- **OpenWA session recovery / reconnect** — the sidecar owns the session volume, but *nothing* states the recovery behavior, who restarts it, or how nagbot detects a dead session. (Ties directly to AD-7's soft trigger, finding #2.)
- **QR re-auth** — named as a user-side prerequisite in the epic but **absent from the spine** — no mention of where the QR is surfaced, who scans, or how a re-auth-needed state is signaled. A whole named prerequisite is dropped.
- **Monitoring / alerting on the escalation loop itself** — there is no "who watches the watcher." If the `escalation_cron` job dies or the sidecar is unreachable, a genuine 3am P0 is silently missed — the exact failure the epic exists to prevent. No health-surface for the escalation path is specified.
- **Ban-avoidance pacing on the escalation channel** — the brief mandates reusing Epic-6 rate-cap; the spine's Consistency table logs to `send_log` but **does not bind the escalation dispatch to the E6 rate-cap/opt-out plumbing** the epic's dependencies require. (P0 has "no opt-out" per S6, but pacing/ban-avoidance still applies.) Not mentioned.
- **Environments** (staging vs prod for an unofficial WA number you can get banned) — silent. Reasonable to defer, but it should say so.

**Severity: MED-HIGH (whole dimension partially silent).** These aren't nitpicks — session-recovery, QR re-auth, and escalation-loop monitoring are the operational failure modes that directly defeat "never cry wolf" / "reliably reaches a human." The spine should add at least one **AD-8 (Operational: session liveness + recovery + escalation-loop health)** or, at minimum, promote QR re-auth, session-recovery ownership, escalation-loop monitoring, and E6-pacing-reuse to explicit **Open Questions** so they aren't silently dropped between architecture and stories.

Other epic-owned dimensions are handled: data/state (AD-4), integration boundaries (AD-2/6/7), config (AD-5), concurrency/locking (AD-1), security (webhook auth in Consistency table — good catch that it's *not* AUTH_EXEMPT).

---

## Summary of Findings

| # | Severity | Finding |
|---|---|---|
| 1 | **MED-HIGH** | OPERATIONAL envelope partially silent: OpenWA session recovery, QR re-auth, and escalation-loop self-monitoring are named epic/brief risks but neither decided, deferred, nor listed as open. Add AD-8 (operational) or promote to Open Questions. |
| 2 | **MED** | AD-7 fallback trigger is soft: "session is down" is undefined as a signal. OpenWA can silently drop delivery; without a health/confirmation probe the Teams fallback (the epic's verified resilience guarantee) can't reliably fire. Define the liveness signal. |
| 3 | **LOW** | E6 rate-cap/ban-avoidance reuse (epic dependency) is not bound to escalation dispatch in the spine. |
| 4 | **LOW** | E4-reuse lineage: epic says "reuse red-streak escalation plumbing," but spine adds a *separate* `p0_escalations` table (likely correct) without explicitly resolving the "reuse" language. |
| 5 | **INFO** | Strong positives: exact brownfield ratification (all 8 code claims verified), all six story forks pinned, AD-4/AD-6 are model enforceable rules, Deferred is clean. |

**Bottom line:** Structurally excellent and faithful to the codebase; the divergence-fixing core is solid. Ship it once the OPERATIONAL dimension (finding #1) and the AD-7 liveness definition (finding #2) are addressed — both feed directly into the reliability promise that is this epic's entire reason to exist.
