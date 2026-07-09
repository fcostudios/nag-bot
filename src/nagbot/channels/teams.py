"""Teams adapter — posts Adaptive Cards through a Power Automate Workflow webhook.

Built on Workflows (not the legacy O365 connectors retired ~May 2026). The webhook
URL comes from TEAMS_WEBHOOK_URL; setup steps live in docs/teams-setup.md.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from nagbot.channels.base import SendResult
from nagbot.digest.builder import Digest, Rollup
from nagbot.digest.renderer import Renderer

logger = logging.getLogger(__name__)

RETRIABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


def _envelope(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }


class TeamsAdapter:
    name = "teams"

    def __init__(
        self,
        renderer: Renderer,
        webhook_url: str = "",
        *,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.renderer = renderer
        self.webhook_url = webhook_url
        self._http = http or httpx.Client(timeout=30)
        self._sleep = sleep

    # -- digest ------------------------------------------------------------------

    def send_digest(self, digest: Digest, *, dry_run: bool) -> SendResult:
        card = self.renderer.teams_card(digest)  # render first — errors surface even dry
        recipient = digest.owner.teams_id or digest.owner.key
        mention_note = "" if digest.owner.teams_id else " (no teams_id — card sent unmentioned)"
        if dry_run:
            return SendResult(
                self.name, recipient, "dry_run", detail=f"card rendered{mention_note}"
            )
        if not self.webhook_url:
            return SendResult(
                self.name, recipient, "skipped", detail="TEAMS_WEBHOOK_URL not configured"
            )
        return self._post(card, recipient, mention_note)

    # -- rollup ---------------------------------------------------------------------

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult:
        card = self._rollup_card(rollup)
        if dry_run:
            return SendResult(self.name, "channel", "dry_run", detail="rollup card rendered")
        if not self.webhook_url:
            return SendResult(
                self.name, "channel", "skipped", detail="TEAMS_WEBHOOK_URL not configured"
            )
        return self._post(card, "channel", "")

    def _rollup_card(self, rollup: Rollup) -> dict[str, Any]:
        facts = [
            {
                "title": p.owner_name,
                "value": f"{p.total} open — oldest {p.oldest_age_bd:.1f}d, "
                f"stalest {p.worst_stale_bd:.1f}d",
            }
            for p in rollup.per_person
        ]
        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "size": "Medium",
                    "weight": "Bolder",
                    "text": self.renderer.rollup_subject(rollup),
                },
                {"type": "FactSet", "facts": facts},
            ],
        }

    # -- transport --------------------------------------------------------------------

    def _post(self, card: dict[str, Any], recipient: str, note: str) -> SendResult:
        payload = _envelope(card)
        last_detail = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = self._http.post(self.webhook_url, json=payload)
            except httpx.TransportError as exc:
                last_detail = f"transport error: {exc}"
                logger.warning("teams POST transport error (attempt %d): %s", attempt, exc)
            else:
                if resp.status_code < 300:
                    return SendResult(
                        self.name, recipient, "sent", detail=f"HTTP {resp.status_code}{note}"
                    )
                last_detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code not in RETRIABLE_STATUS:
                    logger.error("teams POST failed permanently: %s", last_detail)
                    return SendResult(self.name, recipient, "failed", detail=last_detail)
                logger.warning("teams POST retriable (attempt %d): %s", attempt, last_detail)
            if attempt < MAX_ATTEMPTS:
                self._sleep(2 ** (attempt - 1))
        return SendResult(
            self.name, recipient, "failed",
            detail=f"gave up after {MAX_ATTEMPTS} attempts — {last_detail}",
        )
