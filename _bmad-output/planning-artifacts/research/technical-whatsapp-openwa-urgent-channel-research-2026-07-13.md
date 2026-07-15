---
stepsCompleted: [1, 2, 3]
inputDocuments: []
workflowType: 'research'
lastStep: 3
research_type: 'technical'
research_topic: 'WhatsApp urgent-notification + call-escalation channel (OpenWA / UltraMSG / official Cloud API / Twilio) for the Python nagbot'
research_goals: 'Decide the messaging transport (OpenWA required) and plan the calling transport for an Epic 7 urgent-escalation channel; verify UltraMSG calling claim; surface risks, integration, cost, compliance.'
user_name: 'NagBot Owner'
date: '2026-07-13'
web_research_enabled: true
source_verification: true
---

# Research Report: WhatsApp urgent-notification + call-escalation channel

**Date:** 2026-07-13
**Author:** NagBot Owner
**Research Type:** technical
**Status:** draft for review → feeds brainstorming + Epic 7 architecture

---

## Research Overview

**Question.** What transport(s) should power a new *urgent* WhatsApp notification channel for the Python `nagbot`, and how should we plan the "call the user when something is critical" capability? OpenWA for messaging is a firm product requirement; UltraMSG must be evaluated (its calling claim verified); calls are **not** mandatory for the first modules but must be designed for.

**Method.** Current web + primary-source verification (official API docs, vendor docs, GitHub). Each material claim is cited under Sources. Findings are set against the existing nagbot architecture: a Python app with a **channel-adapter pattern** (Epics 2/5/6), an existing **official WhatsApp Cloud API** channel with rate-cap + opt-out (Epic 6), and an existing **red-streak escalation** engine (Epic 4).

---

## Headline finding (the decision-changer)

**No unofficial WhatsApp gateway can place a live call.** Verified from primary docs:

- **OpenWA** exposes only `onIncomingCall` — it can *detect* an incoming call and auto-reply with text; there is **no outbound-call API**.
- **UltraMSG** — confirmed from its own API docs — has message types `audio` and `voice` that send **pre-recorded files**; there is **no call-initiation endpoint**. Its marketing "voice & video" wording refers to media messages, not ringing a phone.

Therefore the "very urgent → call the user" capability, when we build it, **cannot** come from OpenWA or UltraMSG. It has exactly two realistic sources:

1. **Official WhatsApp Cloud API Calling** (Meta) — business-initiated outbound voice calls. **Ecuador is supported** (blocked only in US/CA/EG/VN/NG). Requires the user to grant **call permission**, enforces rate limits (100/day; 2/week for new permissions; permission auto-revoked after 4 consecutive unanswered), and supports calling hours. We **already** integrate the Cloud API in Epic 6.
2. **A telephony provider (e.g. Twilio Voice)** — a real PSTN phone call, WhatsApp-independent. Most reliable for "critical," no WhatsApp opt-in dance, but a separate vendor + per-minute cost + a spoken/IVR message to author.

**Implication for scope:** this epic is really *"urgent escalation"*, not *"add OpenWA."* Messaging and calling are two different transports with different vendors and risk profiles. Treat them as separate stories/modules (which matches "calls aren't mandatory for the first modules").

---

## Messaging transport comparison

You require OpenWA-style unofficial messaging. There are three shapes of "unofficial WhatsApp Web" transport, plus the official one you already have. WAHA is included because it directly fits our Python + self-host constraints.

| Option | Shape | Python fit | You control the session? | Cost (approx) | Ban/ToS risk | Notes |
|---|---|---|---|---|---|---|
| **OpenWA** (`@open-wa/wa-automate`) | Node.js **library** you self-host (drives WhatsApp Web via headless browser) | Poor-direct — Node runtime; needs a **sidecar service** + HTTP/socket bridge from Python | **Yes** (self-hosted) | ~$5/mo–$50/yr license per number for advanced (e.g. messaging unknown numbers) | **High** — unofficial, ToS violation, "use at your own risk"; breaks on WA Web changes | The stated requirement. Most control, most ops (QR session, browser, reconnects). |
| **WAHA** (`waha.devlike.pro`) | Self-hosted **HTTP API** in Docker (wraps WhatsApp Web) | **Good** — plain HTTP from Python; Dockerized like our stack | **Yes** (self-hosted) | Freemium (core free; plus tier paid) | **High** — same unofficial-WA category | Middle ground: OpenWA's self-hosting + UltraMSG's HTTP simplicity. Worth a serious look. |
| **UltraMSG** | Hosted **SaaS** gateway (they run WA Web) | **Good** — simple HTTP API | **No** — your WA session lives on their servers | ~$39/mo per instance | **High** — unofficial; **on the WhatsApp blacklisted-providers list**; peer "Chat-API" got a C&D and shut down | Lowest ops, but you hand session + message content to a third party → **LOPDP data-processor** concern. No calling. |
| **Official Cloud API** (Meta) | Official REST API (already in Epic 6) | Already integrated | N/A (Meta-hosted, sanctioned) | Per-conversation pricing; free service/utility windows vary | **None** (sanctioned) | Constraints: template pre-approval, 24-hour session window, opt-in. **Can also place calls.** |

**Why unofficial at all?** The *only* thing OpenWA/WAHA/UltraMSG buy over the official channel is messaging **without** template approval / outside the 24-hour window / without formal opt-in. That capability is precisely what triggers (a) WhatsApp's spam-detection **ban** of the sending number and (b) an **LOPDP consent** question (messaging people who haven't opted in). This is the same compliance theme as the public-dashboard PII decision.

---

## Calling transport comparison (plan now, build later)

| Option | Places a real call? | Ecuador | Preconditions | Cost | Fit |
|---|---|---|---|---|---|
| **WhatsApp Cloud API Calling** | Yes (WhatsApp voice) | ✅ supported | User **call-permission opt-in**; rate limits 100/day, 2/week new, revoke after 4 unanswered; calling hours | Meta call pricing | Reuses the Epic-6 Cloud API integration; stays in one app the user already has |
| **Twilio Voice (or PBX/SIP)** | Yes (PSTN phone call) | ✅ (global) | Phone number on file; author a spoken/TwiML/IVR message | Per-minute + number rental | Most reliable for "critical"; independent of WhatsApp bans; extra vendor |
| OpenWA / UltraMSG | ❌ **No** | — | — | — | Not an option for calling |

---

## Integration & architecture implications

- **Python ↔ Node reality.** OpenWA is Node.js. Even the "python" OpenWA package still drives a Node/browser process. So OpenWA = a **new sidecar container** (`docker-compose` service) exposing an HTTP endpoint the Python nagbot calls, plus **persistent session state** (QR login once, storage volume, auto-reconnect when WA Web logs it out). WAHA is the same self-host model but ships *as* an HTTP server, removing the bridge-authoring work.
- **Channel-adapter fit.** nagbot already has a channel-adapter pattern (Teams in Epic 5, WhatsApp Cloud in Epic 6). A new `openwa`/`waha` adapter slots in cleanly behind the same interface — the transport choice is mostly hidden from the orchestrator.
- **Reuse Epic 6 guardrails.** Epic 6 already built a **rate cap + opt-out** for WhatsApp. An unofficial channel needs those *more*, not less (ban avoidance = low, paced send rates; UltraMSG itself advises 6–12 msgs/min initially). Reuse, don't reinvent.
- **Escalation hook.** Epic 4's red-streak escalation is the natural trigger for "urgent." The escalation ladder (nudge → WhatsApp → call) is a **policy** to design in brainstorming, not a transport question.

---

## Risk & compliance summary

- **Account ban (High).** Any unofficial transport can get the sending WhatsApp number permanently banned by WhatsApp's anti-automation. Mitigations: a **dedicated, disposable number** (never a person's primary), conservative send pacing, opt-in-only recipients, and keeping the **official Cloud API as the fallback**.
- **ToS violation.** OpenWA/WAHA/UltraMSG all violate WhatsApp ToS. This is a business-risk acceptance decision (like the PII call), to be recorded explicitly.
- **LOPDP / data protection.** UltraMSG (SaaS) becomes a **third-party processor** of message content + your WA session → strongest data-protection exposure. Self-hosted (OpenWA/WAHA) keeps data in-house. Messaging non-opted-in users is a consent question regardless of transport.
- **Vendor continuity.** UltraMSG-class providers have historically received cease-and-desists; SaaS continuity is a real risk. Self-hosting insulates against vendor shutdown but not against WA Web breakage.

---

## Recommendation

1. **Messaging (first module, required): self-host, and prefer WAHA over the OpenWA library — but honor the OpenWA requirement if firm.** Both are the same unofficial-WA risk class; WAHA gives us an HTTP API (clean Python integration, Docker-native to our stack) without hand-building a Node bridge and session babysitter. If OpenWA specifically is mandated, wrap it as a sidecar exposing HTTP and keep the adapter identical so we can swap later. **Use a dedicated throwaway number, opt-in only, reuse Epic-6 rate-cap/opt-out, and keep the official Cloud API channel as automatic fallback.**
2. **Calling (later module, not mandatory now): design the escalation ladder now, build on the official Cloud API Calling first** (Ecuador-supported, reuses Epic-6 integration, no new vendor), with **Twilio Voice** as the fallback/alternative for true "critical" reliability. **Neither OpenWA nor UltraMSG participates in calling.**
3. **Do not adopt UltraMSG** unless zero-ops SaaS outweighs handing session + PII to a blacklisted third party — it also adds nothing on calling.

---

## Open questions to carry into brainstorming + Epic 7 architecture

1. **Escalation ladder policy:** what severity triggers WhatsApp vs a call? Who is contacted — the ticket owner, the on-call, or the manager? Quiet hours? Fallback when unanswered?
2. **Which number(s)** send the unofficial messages, and are we OK risking a ban on them? Is a dedicated line acquirable?
3. **OpenWA vs WAHA:** is the "OpenWA" requirement about the *library specifically*, or about *self-hosted unofficial WhatsApp messaging* (which WAHA also satisfies more cleanly)?
4. **Consent/opt-in model** for unofficial messages and for call-permission (LOPDP): reuse Epic-6 opt-out, or build explicit opt-in?
5. **Calling transport** when we get there: WhatsApp Cloud API Calling vs Twilio — decided by reliability needs and cost.
6. **Ops ownership:** who watches the WA-Web session health / re-scans QR when it drops?

---

## Sources

- OpenWA — GitHub: https://github.com/open-wa/wa-automate-nodejs
- OpenWA — docs (incoming-call handling; no outbound call API): https://docs.openwa.dev/
- OpenWA — npm (license/paid features): https://www.npmjs.com/package/@open-wa/wa-automate
- UltraMSG — API docs (message types; **no call endpoint**): https://docs.ultramsg.com/
- UltraMSG — ban-avoidance guidance / pacing: https://blog.ultramsg.com/avoid-banned-whatsapp-number/
- WAHA — self-hosted WhatsApp HTTP API: https://waha.devlike.pro/
- WhatsApp Cloud API — Calling (business-initiated calls, limits, geography): https://developers.facebook.com/docs/whatsapp/cloud-api/calling/
- Twilio Voice (calling transport alternative): https://www.twilio.com/docs/voice
