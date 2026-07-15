# Epic 7 — Urgent P0 escalation: go-live runbook

Nagbot can page a person about a P0 ticket over WhatsApp (and, later, call them). Because
that reaches staff on their personal phones, two things must happen before it is turned on:
a one-time **transparency notice** to the team, and a short operator checklist.

## 1. Transparency notice (give this to staff once, on the record)

> **Heads-up: automated P0 alerts.** For tickets marked **P0** (a critical incident — a core
> system down, payments failing, etc.), our ticket assistant "nagbot" may **message you on
> WhatsApp** — and, in a later phase, **call you** — to make sure the incident is seen and
> handled quickly. It escalates to your manager and then to on-call/triage if there's no
> response. This applies only to genuine P0 incidents and is part of our IT incident-response
> process. Reply to the WhatsApp to acknowledge ("on it") and it stops escalating.

Record who was notified and when (email/announcement is fine). This is the LOPDP/consent basis
(employment/work coverage; there is **no P0 opt-out** — P0 reachability is part of the role).

Once done, set `escalation.transparency_notice_given: true` in the YAML config. **Escalation
will not page anyone until this flag is set** (nagbot logs a warning and stays silent).

## 2. Operator go-live checklist

1. **Dedicated WhatsApp number** — provision a throwaway number for OpenWA (never a person's
   primary; the unofficial channel carries a ban risk). Scan the QR once to log the sidecar in.
2. **Pin the OpenWA image** — set `OPENWA_IMAGE_TAG` to a specific tag/digest (never `latest`).
3. **Webhook secret** — set `OPENWA_WEBHOOK_SECRET` (used to authenticate inbound-ack replies
   at `POST /webhooks/openwa`).
4. **P0 marking convention** — brief triage/operators: a genuine P0 must be set to **priority
   5 or 6 (Alta / Muy alta)** in GLPI. Nagbot escalates on the configured rule (default
   `priority >= 5`); it escalates **nothing** until a real P0 is marked that way.
5. **Optional fallback** — set `escalation.alert_channels: [openwa, teams]` so a P0 falls
   through to Teams if the OpenWA session is down/banned.
6. **Flip the two flags** — `escalation.enabled: true` **and**
   `escalation.transparency_notice_given: true`. Keep `NAGBOT_DRY_RUN` / `channels.dry_run` as
   your safety net until you've watched a real P0 flow end to end.

## 3. What nagbot does once live

Detect a verified P0 → message the owner (and manager) → climb owner → manager → default
triage on the dwell cadence (default 5 min/rung) → re-validate the live ticket before every
page (stops instantly if resolved/reassigned/downgraded) → stop the moment someone replies
"on it" or the ticket moves → fall over to Teams if WhatsApp is unavailable.

Deferred (not yet live): the phone-**call** rung (E7-S8), per-tier SLA thresholds (E7-S7),
stats (E7-S9), and a proactive OpenWA session-health probe.
