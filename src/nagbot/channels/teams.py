"""Teams adapter — stub until Epic 5.

Renders the Adaptive Card (so template errors surface in every run) and logs it;
E5-S1 replaces the log with a POST of the Power Automate Workflow envelope to
TEAMS_WEBHOOK_URL.
"""

from __future__ import annotations

import json
import logging

from nagbot.channels.base import SendResult
from nagbot.digest.builder import Digest, Rollup
from nagbot.digest.renderer import Renderer

logger = logging.getLogger(__name__)


class TeamsAdapter:
    name = "teams"

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def send_digest(self, digest: Digest, *, dry_run: bool) -> SendResult:
        card = self.renderer.teams_card(digest)  # render even in stub mode
        logger.info(
            "teams stub: card for %s (%d tickets): %s",
            digest.owner.display_name,
            len(digest.tickets),
            json.dumps(card)[:400],
        )
        if dry_run:
            return SendResult(self.name, digest.owner.key, "dry_run", detail="card rendered")
        return SendResult(
            self.name, digest.owner.key, "skipped", detail="not implemented until E5"
        )

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult:
        if dry_run:
            return SendResult(self.name, "-", "dry_run", detail="rollup via Teams lands in E5")
        return SendResult(self.name, "-", "skipped", detail="rollup via Teams lands in E5")
