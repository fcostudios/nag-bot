# Brainstorm Intent — Epic 7: Urgent P0 Escalation

Input for the `bmad-product-brief` skill (nagbot project). Distilled from the completed brainstorming session on the urgent escalation model. Companion technical research: `_bmad-output/planning-artifacts/research/technical-whatsapp-openwa-urgent-channel-research-2026-07-13.md`.

## Problem / Context

When something business-critical breaks (a P0 ticket — e.g. payments not processing), the current process depends on a human remembering to phone the developer. That is fragile and person-dependent. Epic 7 automates the notify/call flow off the ticket's P0 status in GLPI, so escalation happens because the ticket is P0, not because someone remembered to act.

## North-star principle

This is not a notification feature — it is a **trust instrument**. Every rule serves one metric: **never cry wolf**. The day nagbot escalates a non-incident is the day the real payments-down P0 gets ignored, people block the bot, and refuse tickets. Reliability and credibility outrank loudness in every design decision.

Consequences of this through-line:
- The verification gate is what makes an aggressive immediate/24-7/no-quiet-hours trigger survivable — aggressive trigger and verification are two halves of one idea.
- "Keep polling status" (after ack) and "re-validate at every rung" are the same reliability mechanic: live ticket state is the source of truth, never a stale reply.
- Ack-reply + auto-move-status is one gesture that both quiets nagbot and produces the evidence it needs.
- Climbing ladder (vertical, up the roster) + Teams fallback (horizontal, across channels) = reliability on two axes, not one louder channel.

## Target users

Staff (employees). Roles in the escalation:
- **Ticket owner** — the assigned person.
- **Manager** — the owner's manager (notified alongside the owner).
- **Default triage owner** — a designated person who receives unassigned P0s and owns routing them to the right person.

## The escalation model

- **Trigger** = a P0 ticket (something broken / business-impacting). P0 is the escalate-now signal.
- **Verify before escalating** — do not trust the P0 tag blindly. An operator triages/classifies at intake; nagbot also checks for corroborating evidence of a genuine P0 and advises on severity before escalating.
- **Roster / who** — notify BOTH the assigned owner AND their manager. If unassigned, route to the default triage owner.
- **Speed** — escalate immediately on P0 detection, no grace window.
- **Hours** — no quiet hours for P0. 24/7; P0 overrides do-not-disturb for messages and calls.
- **Climbing ladder** — message the current escalation level; if ignored, keep climbing up the roster to the next higher level until the top is reached. Dwell = 5 minutes per rung before climbing.
- **Message content** — affected system, time of report, brief description of what is broken now, and a link to the ticket.
- **Ack** — a reply to nagbot with first thoughts/acknowledgment ("we're on it") OR a GLPI ticket update with a status change. On an ack reply, nagbot may auto-move the GLPI ticket status.
- **Keep polling** — a reply alone is NOT a permanent stop. Nagbot keeps polling ticket status; if it does not progress, it re-notifies with a warning ("this will be escalated for help") before climbing again.
- **Re-validate every rung** — right before acting at each rung, confirm the ticket is still OPEN, still a genuine P0, and correctly assigned. Stop escalating instantly if it is resolved/closed, reassigned, or downgraded. Never call about a resolved or misassigned ticket.
- **Multiple simultaneous P0s** — the initial alert MAY batch several into one message; follow-ups/escalations are tracked and sent per-ticket, one by one.
- **Back-off** — for a single unresolved P0, cadence backs off over time (not every 5 min forever); each back-off ping warns that escalation may follow before climbing.
- **Teams fallback** — Teams (the existing Epic-5 channel; always-on, more stable) is the backup urgent rung when OpenWA WhatsApp fails (banned/session down). P0 delivery is multi-channel, never sole-path WhatsApp.
- **Call = top-of-top final rung** — the phone call is the ultimate escalation ("the real nag"), reached only after the message ladder (owner → manager → up) is exhausted/unanswered. No jump-straight-to-call.

## Consent basis

Employment/legal work coverage: P0 reachability is part of the job. No per-event opt-in and no P0 opt-out. Provide a one-time transparency notice that nagbot may message/call staff for certain events.

## Transport decisions

- **Messaging: self-hosted OpenWA** — decided.
- **Calls (later):** via the official WhatsApp Cloud API Calling feature or Twilio. Neither OpenWA nor UltraMSG can place phone calls, so the call rung requires a different transport.

## Module-1 MVP scope

**MUST (Module 1):**
1. P0 detection
2. P0 verification gate
3. Roster (owner + manager; default triage if unassigned)
4. Immediate + 24/7 trigger
5. OpenWA WhatsApp alert (system / time / what-broke / link)
6. Climbing ladder (5-min dwell)
7. Ack handling (reply + keep polling)
8. Auto-move GLPI status on ack
9. Re-validate & stop
11. Back-off cooldown (with escalation warning)
12. Teams fallback
13. Transparency notice

**DEFERRED (later modules):**
- 10. SLA/priority-configurable thresholds (MVP hardcodes P0 = 5 min)
- 14. Phone CALL rung
- 15. Stats/analytics (false-positive rate, ack times, who-blocks)

## Open questions for the brief / architecture

- **P0 detection/verification** — how to detect and verify a genuine P0 from GLPI signals (which corroborating signals define "real"; how nagbot advises on severity).
- **Roster & triage-owner config** — how the owner/manager roster and default triage owner are configured and maintained.
- **Ban-avoidance + dedicated number** — how to avoid WhatsApp bans and provision a dedicated number for the OpenWA channel.
- **OpenWA session ops** — running and monitoring the self-hosted OpenWA session (session-down detection, recovery, failover to Teams).
