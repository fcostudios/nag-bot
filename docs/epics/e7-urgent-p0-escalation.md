# Epic 7 — Urgent P0 escalation

**Goal:** When a genuine **P0** ticket appears in GLPI (the business is broken — e.g. payments
down), nagbot escalates it automatically: verify it's real, reach the owner **and** manager
immediately (24/7), and **climb the roster** until someone acknowledges — without ever crying
wolf. Module 1 delivers the **messaging** escalation over a **self-hosted OpenWA** WhatsApp
channel, with reliability and compliance guardrails built in. The phone-**call** rung is a
deliberate later module.

**North-star (acceptance lens for every story):** *a trust instrument — never cry wolf.*
Reliability and credibility outrank loudness in every design decision.

**Depends on:** E2-S5 (channel-adapter protocol), E5 (Teams adapter — reused for fallback),
E4 (red-streak escalation plumbing — reused), E6 (rate-cap / opt-out — reused). Snapshot store
(E2-S3) and GLPI client (E1-S3) for ticket state.

**Inputs:** product brief `_bmad-output/planning-artifacts/briefs/brief-nag-bot-2026-07-13/brief.md`;
brainstorm intent + technical research it references.

**⚠️ Long pole / biggest open question (resolve in architecture before E7-S2):** how a *genuine*
P0 is **detected and verified** from GLPI signals (priority field alone vs. corroborating
evidence), and how nagbot "advises on severity." This underwrites the whole credibility promise.

**⚠️ Ops prerequisite (user-side):** a **dedicated, disposable WhatsApp number** for OpenWA
(never a person's primary — unofficial channel carries ban risk); one-time QR login; and a
one-time **transparency notice** to staff.

## Module 1 — messaging escalation (this cycle)

| Story | Title | Size |
|---|---|---|
| E7-S1 | OpenWA sidecar + WhatsApp-Web channel adapter (Node service, session/QR/reconnect, HTTP bridge, `openwa` adapter behind the E2-S5 protocol, send a message end-to-end) | L |
| E7-S2 | P0 detection + verification gate (identify P0 tickets from GLPI; verify genuineness & advise on severity before anything escalates) | M |
| E7-S3 | Escalation roster + climbing ladder (roster: owner + manager, default triage if unassigned; immediate/24-7 trigger; climb owner→manager→up at 5-min dwell; back-off with escalation warning; sends the decision-ready P0 message: system · time · what-broke · link) | L |
| E7-S4 | Acknowledgement + re-validate/stop (ack via WhatsApp reply OR GLPI status change; auto-move status on ack; keep polling live ticket; re-validate each rung; stop instantly if resolved/reassigned/downgraded) | M |
| E7-S5 | Teams fallback (multi-channel P0 delivery; when the OpenWA session is down/banned, deliver via the existing Teams channel — never sole-path WhatsApp) | S |
| E7-S6 | Transparency notice (one-time staff awareness that nagbot may message/call for P0 events; employment/legal basis, no P0 opt-out) | S |

**Done when:** a verified P0 triggers an immediate WhatsApp to the owner + manager; unacknowledged
P0s climb the roster on the 5-min cadence with back-off warnings; an ack (reply or GLPI status
change) or a resolved/reassigned/downgraded ticket **stops the climb instantly**; a P0 still lands
via **Teams** when the OpenWA session is unavailable; and no one is ever escalated for a
non-genuine, resolved, or misassigned ticket (zero false escalations in test).

## Deferred — later modules (NOT in Module 1)

| Story | Title | Size |
|---|---|---|
| E7-S7 | SLA/priority-configurable thresholds (per-tier dwell times in config; MVP hardcodes P0 = 5 min) | S |
| E7-S8 | Phone-**call** rung — the top-of-top final nag (official WhatsApp Cloud API Calling or Twilio Voice; needs call-permission opt-in; Ecuador supported). *Neither OpenWA nor UltraMSG can place calls.* | M |
| E7-S9 | Stats/analytics (false-positive rate, ack times, who-blocks) — tune severity rules on data | S |
