# GLPI Nagbot — Strategy & Implementation Plan

**Goal:** Make dev-support ticket WIP and aging *visible and unavoidable*. Every day, push each responsible person a short, pointed message (Email → Teams → WhatsApp) listing their open and aging tickets, so nothing sits and rots. Quick to stand up, and deliberately naggy.

**Prepared for:** Francisco · **Date:** 2026-07-08 · **Platform:** GLPI (help desk) · **Channels:** Teams, WhatsApp, Email

---

## 1. The short version (TL;DR)

GLPI can *nag* on its own a little, but not the way you want. Its notifications are **event-based** (ticket created, updated, SLA level reached) — there is no built-in "every morning, send each tech a digest of their aging tickets." So the winning strategy is a **small scheduled "nagbot" service** that:

1. Wakes up on a schedule (e.g. every weekday at 08:00 America/Guayaquil).
2. Pulls open tickets from GLPI's **REST API**.
3. Computes **aging** (age, time since last update, SLA due/overdue) and sorts tickets into severity tiers.
4. Groups tickets **by responsible person** (assigned technician / group).
5. Sends each person a compact digest, escalating tone and audience the longer a ticket stalls.

The fastest, most reliable channel to build first is **Email**, then **Teams** (via a Power Automate "Workflow" webhook — the old Teams webhooks are being switched off), then **WhatsApp** (most setup overhead: Meta Business account + approved template).

**Recommended fastest path:** turn on native GLPI escalation emails **today** (zero code) for baseline nagging, and in parallel build the custom email nagbot this week. Add Teams next week, WhatsApp after that.

---

## 2. What GLPI gives us (and what it doesn't)

### Works out of the box
- **REST API** (`apirest.php`) with a powerful `/search/Ticket` endpoint — we can query open tickets and filter by status, assignee, group, and dates. This is how the nagbot reads WIP and aging. ([API docs](https://help.glpi-project.org/documentation/modules/configuration/general/api/api))
- **Automatic Actions (cron)** — GLPI's internal scheduler already runs jobs on intervals; we can either piggyback on the same server crontab or run our own. ([Automatic actions](https://help.glpi-project.org/documentation/modules/configuration/crontasks))
- **SLA / SLT with escalation levels** — you can define "when X% of resolution time elapsed → run action / send notification." This is native, event-driven nagging with **zero code**, but it's tied to SLA definitions and is famously fiddly to get right. ([Service levels](https://help.glpi-project.org/tutorials/helpdesk/service_levels))
- **Notification templates + SMTP** — GLPI already sends email; we can reuse its templating and mail config.

### The gaps we have to fill
- **No native "daily per-owner digest of aging tickets."** Native notifications fire on *events*, not on a "here's your stale pile every morning" cadence.
- **No native Teams/WhatsApp push.** Teams is possible via the community **Collaborative Tools / Webhook plugin**, but it's **event-based only** (fires on ticket events, not scheduled digests) and needs a *public* channel. WhatsApp has no native path at all.
- **Aging tiers and "naggy" escalation logic** (tone changes, manager CC on repeat offenders, leaderboards) are our own business rules.

**Conclusion:** native features are a good *baseline* (Phase 0), but the naggy daily digest is a custom scheduled service. That service is small and quick to write.

---

## 3. Recommended architecture — "the Nagbot"

A single small service (a Python script is ideal; runs on the GLPI server, a small VM, or a container) on a schedule:

```
                 ┌────────────────────────────────────────────┐
   cron / timer  │                 NAGBOT                      │
  (weekday 08:00)│                                             │
        ─────────▶  1. Auth to GLPI REST API                   │
                 │  2. GET /search/Ticket  (open + aging)      │
                 │  3. Enrich: assignee, group, SLA due dates  │
   GLPI  ◀───────┤  4. Compute age / stale-days / tier         │
  REST API       │  5. Group by responsible person             │
                 │  6. Render per-owner digest                 │
                 │  7. Dispatch via channel adapters ──────────┼──▶ Email (SMTP)
                 │  8. Log what was sent (dedupe / snooze)      ┼──▶ Teams (Workflow webhook)
                 └──────────────────────────────────────────────┼──▶ WhatsApp (Cloud API)
                                                                 └──▶ (Manager escalations)
```

**Why a standalone script rather than a GLPI plugin:** far faster to build, easy to change the nagging rules, and it can hit all three channels. A plugin would be locked to GLPI's event model and PHP. The API approach is also the least risky to your production GLPI (read-only calls).

### Channel adapters (pluggable, build in this order)
| Channel | Mechanism | Setup effort | Notes |
|---|---|---|---|
| **Email** | SMTP (reuse GLPI's mail server) | **Lowest** | Build first. Rich HTML digest, deep links back to each ticket. |
| **Microsoft Teams** | **Power Automate "Workflow"** incoming webhook (HTTP POST → Adaptive Card) | Medium | The old Office 365 connector webhooks are **being retired (rollout ~May 2026)** — use Workflows, not legacy connectors. Post to a support channel with @mentions; true 1:1 DMs need Graph API. |
| **WhatsApp** | **Meta WhatsApp Cloud API** (or Twilio/360dialog BSP) | **Highest** | Needs a Meta Business account, a registered number, and a **pre-approved "utility" message template**. Message-based pricing (utility messages are cheap, fractions of a cent). Build last. |

---

## 4. Aging & "naggy" logic

### Pull the WIP
Query GLPI for tickets that are **not closed/solved** — statuses New (1), Processing/Assigned (2), Processing/Planned (3), Pending (4). Example REST call (status = New):

```
GET /apirest.php/search/Ticket/
    ?criteria[0][field]=12&criteria[0][searchtype]=equals&criteria[0][value]=notold
    &forcedisplay[0]=2   # id
    &forcedisplay[1]=1   # title
    &forcedisplay[2]=12  # status
    &forcedisplay[3]=15  # date opened
    &forcedisplay[4]=19  # last update
    &forcedisplay[5]=5   # assigned technician
    &forcedisplay[6]=8   # assigned group
    &range=0-999
Session-Token: <token>
App-Token: <app-token>
```
*(Exact field IDs vary per instance — discover them once with `GET /listSearchOptions/Ticket`.)*

### For each ticket, compute
- **Age** = now − date opened.
- **Stale days** = now − last update (the real "nobody's touching this" signal).
- **SLA status** = time-to-resolve due date: OK / due soon / **breached**.

### Severity tiers (tune the thresholds to your team)
| Tier | Rule (example) | Nag behavior |
|---|---|---|
| 🟢 Fresh | opened < 2 business days, recently updated | Listed, no pressure |
| 🟡 Aging | no update in 2–4 days | "Please update" |
| 🟠 Hot | no update in 5+ days **or** SLA due within 24h | Bold, top of digest, daily |
| 🔴 On fire | SLA **breached** or no update in 7+ days | Top of digest **+ manager CC** + optional real-time ping |

### The nagging cadence (this is where "naggy" lives)
- **Daily 08:00 digest** to each responsible person: *"You have 6 open tickets. 🔴 2 are overdue, 🟠 1 hasn't moved in 5 days. Oldest: #4821, 12 days."* with direct links.
- **Escalation:** a ticket in 🔴 for N consecutive days automatically **CCs the manager / team lead** and appears on a weekly **"oldest tickets" leaderboard**.
- **Real-time pokes (optional):** the moment a ticket breaches SLA, fire a single Teams/WhatsApp ping — not just the morning batch.
- **Snooze/dedupe:** log what was sent so you don't double-nag, and allow a "snoozed until" so legitimately-blocked tickets go quiet for a day or two (prevents nag-fatigue, which is what kills these systems).
- **Weekly manager rollup:** every Monday, a summary to leads — WIP per person, aging distribution, worst offenders.

---

## 5. Message design (keep it short, pointed, scannable)

**Email (daily, per tech) — subject line does the nagging:**
> **Subject:** ⏰ 6 open tickets — 2 OVERDUE, oldest is 12 days (please act)

Body: a tight table, 🔴 first, each row linking straight to the ticket in GLPI. One line of "why this matters" at top, no fluff.

**Teams (Adaptive Card):** same content, but a card in the support channel that @mentions the person. Great for peer visibility — nobody likes their stale pile shown to the team.

**WhatsApp (utility template):** the bluntest, most unavoidable channel. Keep it tiny:
> *"Hi {name}, ticket reminder: you have {n} open, {overdue} overdue. Oldest #{id} ({days}d). Open GLPI to update. 🔗"*

*(Template text must be pre-approved by Meta before you can send.)*

Tone principle: **facts + a number + a link**. Naggy comes from *frequency and visibility*, not from harsh wording.

---

## 6. Phased rollout (fastest to value)

### Phase 0 — Today, zero code (baseline nag)
Turn on GLPI's native **SLA escalation notifications** and **"ticket not solved" reminders** by email. Confirm the "Automatic Actions" cron is running and SMTP works. This gives you *some* automated pressure within hours while we build the real thing. ([Setup notifications](https://help.glpi-project.org/tutorials/notifications/setup_notifications))

### Phase 1 — This week: Email nagbot (the core)
Build the script: GLPI auth → pull open tickets → aging + tiers → group by owner → **daily HTML email digest** → send log. This alone delivers ~80% of the value.

### Phase 2 — Next week: Teams
Create a Power Automate **Workflow** ("Post to a channel when a webhook request is received"), add a Teams adapter to the nagbot posting Adaptive Cards to the dev-support channel with @mentions.

### Phase 3 — Following week(s): WhatsApp
Set up Meta Business account + number + get a **utility template approved** (this approval is the long pole — start it early). Add the WhatsApp adapter (Cloud API or Twilio).

### Phase 4 — Polish
Manager weekly rollup, leaderboard, snooze rules, and optionally a **live WIP dashboard** (an HTML page the team can leave open) so aging is visible all day, not just at 08:00.

---

## 7. What I need from you to start building

1. **GLPI access:** base URL, and an **App-Token** + a service-account **user token** (Setup → General → API). Read-only is enough for the nagbot.
2. **Where it runs:** can I run a small scheduled script on the GLPI server / a VM / a container? (Any is fine.)
3. **Owner mapping:** how "responsible" is set — GLPI *assigned technician*, *assigned group*, or both? And each person's email / Teams / WhatsApp number.
4. **Thresholds:** your definition of "aging" and "overdue" (I'll start with the Section 4 defaults and we tune).
5. **Teams channel** name (public) and permission to create a Power Automate Workflow.

---

## 8. Risks & how we avoid them
- **Nag fatigue → people mute it.** Mitigate with snooze, tiering (don't nag on fresh tickets), and one digest not twenty pings.
- **Teams legacy webhooks retiring (~May 2026).** We build on Power Automate Workflows from day one, so nothing breaks.
- **WhatsApp template approval delay.** Start the Meta approval early (Phase 0), so it's ready by Phase 3.
- **Load on production GLPI.** Nagbot is read-only and runs a handful of paginated queries once a day — negligible.
- **Wrong owner gets nagged.** First run in "dry-run" mode (log only, no send) and eyeball the output before going live.

---

### Sources
- [GLPI REST API — Help Center](https://help.glpi-project.org/documentation/modules/configuration/general/api/api)
- [GLPI Search Engine (dev docs)](https://glpi-developer-documentation.readthedocs.io/en/master/devapi/search.html)
- [GLPI Automatic Actions (cron)](https://help.glpi-project.org/documentation/modules/configuration/crontasks)
- [GLPI Service Levels / SLA escalation](https://help.glpi-project.org/tutorials/helpdesk/service_levels)
- [GLPI Setup Notifications tutorial](https://help.glpi-project.org/tutorials/notifications/setup_notifications)
- [GLPI Collaborative Tools — Teams webhook plugin](https://glpi-plugins.readthedocs.io/en/latest/webhook/teams.html)
- [Microsoft: Retirement of Office 365 connectors in Teams](https://devblogs.microsoft.com/microsoft365dev/retirement-of-office-365-connectors-within-microsoft-teams/)
- [WhatsApp Business API pricing 2026 (respond.io)](https://respond.io/blog/whatsapp-business-api-pricing)
