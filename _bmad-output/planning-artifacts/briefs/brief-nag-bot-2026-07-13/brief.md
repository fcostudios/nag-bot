---
title: "Epic 7 — Urgent P0 Escalation"
status: draft
created: 2026-07-14
updated: 2026-07-14
inputs:
  - _bmad-output/brainstorming/brainstorm-urgent-escalation-model-2026-07-13/brainstorm-intent.md
  - _bmad-output/planning-artifacts/research/technical-whatsapp-openwa-urgent-channel-research-2026-07-13.md
---

# Product Brief: Epic 7 — Urgent P0 Escalation

## Executive Summary

When something business-critical breaks — payments stop, a core system is down — a P0 ticket is raised in GLPI. Today, someone has to *notice* and *phone the developer*. That human step is the weak link: it depends on a person remembering, being awake, and knowing who to call. Epic 7 makes nagbot do it automatically, off the ticket's P0 status: the instant a genuine P0 is confirmed, nagbot reaches the right people, climbs the roster if ignored, and won't stop until the ticket is actually being handled.

The hard part is not sending a message — nagbot already sends WhatsApp (Cloud API) and Teams. The hard part is **earning the right to interrupt someone at 3am**. So one principle governs this epic: **it is a trust instrument, and it must never cry wolf.** Every rule — verify before escalating, re-check reality at every step, stop the instant a ticket is resolved — protects the one moment that matters: when the *real* payments-down P0 lands, people still believe the alert.

Module 1 ships the messaging escalation over **self-hosted OpenWA**, with the reliability and compliance guardrails built in from day one. The phone-call rung — the "top-of-top" final nag — is a deliberate later module.

## The Problem

- **Escalation is person-dependent and fragile.** A P0 only gets urgent attention if a human remembers to chase it. Nights, weekends, and hand-offs are exactly when that fails.
- **Existing nags are not urgent-grade.** The digest/dashboard cadence is right for aging tickets, wrong for "the business is down right now."
- **The credibility trap.** People over-tag tickets as P0. Any system that escalates on the raw tag will fire false 3am alarms — and once burned, people mute the bot or refuse to own tickets. The cost of crying wolf is that the *real* P0 gets ignored. This is the central risk, not an edge case.

## The Solution

A P0-triggered escalation engine that behaves like a disciplined on-call human:

- **Trigger:** a GLPI P0 ticket — but nagbot **verifies** it's a genuine P0 (corroborating evidence + severity advice) before escalating. Verification makes an aggressive, no-quiet-hours trigger survivable.
- **Roster:** notify the assigned owner **and** their manager; unassigned P0s go to a default triage owner who routes them.
- **Timing:** immediate, 24/7 — P0 overrides do-not-disturb.
- **Climbing ladder:** message the current rung; if unacknowledged after the dwell (5 min for P0), climb to the next. Each back-off ping warns that escalation is coming.
- **Acknowledgement & truth:** an ack is a WhatsApp reply *or* a GLPI status change (an ack reply may auto-advance the ticket). A reply alone is not a permanent stop — nagbot keeps watching the live ticket and **re-validates at every rung**: if the ticket is resolved, reassigned, or downgraded, it stops instantly. The live ticket, never a stale reply, is the source of truth.
- **Resilience:** delivery is multi-channel — **Teams is the always-on fallback** when the unofficial OpenWA session is down or banned. Escalation is both vertical (up the roster) and horizontal (across channels).
- **Message content:** affected system, time reported, what's broken, and a ticket link — decision-ready in one glance.

## Design Principle (the north star)

> **A trust instrument — never cry wolf.** Reliability and credibility outrank loudness in every design decision. If a rule makes nagbot louder but less trustworthy, the rule loses. This is the acceptance lens for every story in the epic.

## Who This Serves

- **Ticket owner** — the assigned engineer; needs to know *what broke* and act with one thumb from bed.
- **Manager** — notified alongside the owner; needs the same picture without chasing.
- **Default triage owner** — catches unassigned P0s and routes them.
- All are **staff**; reachability for a P0 is part of the job (see Consent).

## Consent & Compliance

Legal basis is **employment / work coverage** — no per-event opt-in and no P0 opt-out — paired with a **one-time transparency notice** that nagbot may message or call staff for certain events. (LOPDP-aware, consistent with how the project has treated data decisions.)

## Transport Decisions (settled)

- **Messaging: self-hosted OpenWA** (Node sidecar + persisted WhatsApp-Web session) — decided. Unofficial → ban risk is managed with a dedicated number, paced sends (reuse Epic-6 rate-cap/opt-out), and Teams fallback.
- **Calls (later module):** neither OpenWA nor UltraMSG can place a call (verified). The call rung will use the **official WhatsApp Cloud API Calling** (already integrated; Ecuador supported; requires call-permission opt-in) or **Twilio Voice**.
- Fits the existing **channel-adapter** pattern (Teams, WhatsApp Cloud) and can reuse **Epic-4** red-streak escalation plumbing.

## Success Criteria

- **Reliability first (the metric that matters):** a genuine P0 reliably reaches a human and is acknowledged; **near-zero false escalations** — nobody woken for a resolved/misassigned/non-incident ticket. *[ASSUMPTION] target: 0 false 3am escalations; >95% of true P0s acknowledged within one ladder cycle — confirm targets.*
- **Time-to-acknowledge** for P0s drops materially vs. the manual "someone calls the dev" baseline. *[ASSUMPTION] measurable once stats module lands.*
- **Adoption/trust proxy:** no rise in opt-out/block or ticket-refusal after launch.
- **Resilience:** when OpenWA is down, P0s still land via Teams (verified in test).

## Scope

**Module 1 (in):** P0 detection · P0 verification gate · roster (owner + manager + default triage) · immediate/24-7 trigger · OpenWA WhatsApp alert (system/time/what-broke/link) · climbing ladder (5-min dwell) · ack handling (reply + keep polling) · auto-move GLPI status on ack · re-validate & stop · back-off cooldown (with warning) · Teams fallback · transparency notice.

**Deferred (later modules):** SLA/priority-configurable thresholds (MVP hardcodes P0 = 5 min) · the phone-**call** rung · stats/analytics (false-positive rate, ack times, who-blocks).

**Explicitly out:** using OpenWA/UltraMSG for calling (they can't); messaging non-consenting third parties/customers over the unofficial channel.

## Risks & Open Questions

- **P0 detection & verification (biggest unknown):** which GLPI signals define a *genuine* P0, and how nagbot advises on severity. Drives the whole credibility promise → resolve in architecture.
- **WhatsApp ban / session ops:** dedicated number, ban-avoidance pacing, and who watches/recovers the OpenWA session (QR re-auth, failover to Teams).
- **Roster & triage config:** how owner→manager mapping and the default triage owner are configured/maintained.
- **Verification vs. speed tension:** verification must not add latency that defeats "immediate" — how much evidence is "enough"?

## Vision

nagbot grows from a *nagging* bot into the team's **automated on-call reflex**: it notices the business is hurting before a human does, reaches exactly the right person on the channel they'll answer, escalates with judgment, and — when all else is ignored — makes the call. Trusted enough that when it rings, everyone knows it's real.
