"""WhatsApp adapter — stub until Epic 6.

Builds the Meta Cloud API template payload (name, counts, oldest ticket) and logs
it; E6-S1 posts it to graph.facebook.com with the approved utility template.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from nagbot.channels.base import SendResult
from nagbot.digest.builder import Digest, Rollup
from nagbot.digest.renderer import Renderer

logger = logging.getLogger(__name__)


class WhatsAppAdapter:
    name = "whatsapp"

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def build_payload(
        self, digest: Digest, template_name: str = "<pending-approval>"
    ) -> dict[str, Any]:
        oldest = digest.oldest
        params = [
            digest.owner.display_name,
            str(len(digest.tickets)),
            str(digest.breached_count),
            f"#{oldest.ticket.id}" if oldest else "-",
            f"{oldest.metrics.age_bd:.0f}" if oldest else "0",
        ]
        return {
            "messaging_product": "whatsapp",
            "to": digest.owner.whatsapp,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "es"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in params],
                    }
                ],
            },
        }

    def send_digest(self, digest: Digest, *, dry_run: bool) -> SendResult:
        if not digest.owner.whatsapp:
            return SendResult(
                self.name, digest.owner.key, "skipped", detail="owner opted out (no number)"
            )
        payload = self.build_payload(digest)
        logger.info("whatsapp stub payload: %s", json.dumps(payload, ensure_ascii=False)[:400])
        if dry_run:
            return SendResult(
                self.name, digest.owner.whatsapp, "dry_run", detail="payload rendered"
            )
        return SendResult(
            self.name, digest.owner.whatsapp, "skipped", detail="not implemented until E6"
        )

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult:
        return SendResult(self.name, "-", "skipped", detail="no WhatsApp rollup planned")
