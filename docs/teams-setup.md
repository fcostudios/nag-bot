# Teams channel setup (Power Automate Workflow)

The nagbot posts Adaptive Cards to a Teams channel through a **Power Automate Workflow**
webhook. Legacy Office 365 connector webhooks are retired (~May 2026) — don't use them.

## 1. Create the Workflow

1. In Teams, open the target (public) channel → **⋯ → Workflows**, or go to
   [make.powerautomate.com](https://make.powerautomate.com).
2. Pick the template **"Post to a channel when a webhook request is received"**.
3. Select the Team and Channel, create the flow.
4. Copy the generated **HTTP POST URL** — this is your `TEAMS_WEBHOOK_URL`.

> The flow's trigger accepts any request by default; anyone with the URL can post to the
> channel. Treat it as a secret.

## 2. Test it with curl

```bash
curl -sS -X POST "$TEAMS_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message",
    "attachments": [{
      "contentType": "application/vnd.microsoft.card.adaptive",
      "content": {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [{"type": "TextBlock", "text": "nagbot webhook test 👋"}]
      }
    }]
  }'
```

A card should appear in the channel within seconds (the endpoint usually answers `202`).

## 3. Wire it into the nagbot

```bash
# .env
TEAMS_WEBHOOK_URL=https://prod-XX.westus.logic.azure.com/workflows/....
```

```yaml
# config/nagbot.yaml
channels:
  enabled: [email, teams]
```

Restart the container. Dry-run mode applies to Teams exactly like email — cards are
rendered and logged but not posted until dry-run is disabled in **both** env and YAML.

## Mentions

If `owners.<login>.teams_id` is set to the person's Microsoft 365 UPN (usually their
work email), the card @mentions them. Without it the card still posts, just unmentioned
(the send log notes it).

## Troubleshooting

- **HTTP 400 from the webhook** — the flow's trigger schema may reject the payload;
  recreate the flow from the exact template above.
- **Card posts but mention doesn't highlight** — the `teams_id` must be the AAD UPN of a
  member of that team.
- **429s** — Workflows are rate-limited per flow; the nagbot retries with backoff, and
  posts one card per owner per day, which is far below the limits.
