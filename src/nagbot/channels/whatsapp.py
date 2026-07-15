"""WhatsApp adapter — Meta Cloud API utility-template sends.

Requires a Meta Business account, a registered number (WHATSAPP_PHONE_NUMBER_ID),
an access token, and a pre-approved utility template (WHATSAPP_TEMPLATE_NAME) whose
body takes 5 params: name, open count, overdue count, oldest id, oldest days.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from nagbot.channels.base import SendResult
from nagbot.digest.builder import Digest, Rollup
from nagbot.digest.renderer import Renderer

logger = logging.getLogger(__name__)

GRAPH_VERSION = "v20.0"
GRAPH_BASE = "https://graph.facebook.com"


class WhatsAppAdapter:
    name = "whatsapp"

    def __init__(
        self,
        renderer: Renderer,
        *,
        token: str = "",
        phone_number_id: str = "",
        template_name: str = "",
        max_per_run: int = 20,
        http: httpx.Client | None = None,
    ) -> None:
        self.renderer = renderer
        self.token = token
        self.phone_number_id = phone_number_id
        self.template_name = template_name
        self.max_per_run = max_per_run
        self._http = http or httpx.Client(timeout=30)
        self._attempts_this_run = 0

    @property
    def _configured(self) -> bool:
        return bool(self.token and self.phone_number_id and self.template_name)

    @property
    def _endpoint(self) -> str:
        return f"{GRAPH_BASE}/{GRAPH_VERSION}/{self.phone_number_id}/messages"

    def begin_run(self) -> None:
        """Called by the orchestrator at the start of each run (rate-cap window)."""
        self._attempts_this_run = 0

    def build_payload(self, digest: Digest, template_name: str = "") -> dict[str, Any]:
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
                "name": template_name or self.template_name or "<pending-approval>",
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
        if dry_run:
            logger.info(
                "whatsapp dry-run payload: %s", json.dumps(payload, ensure_ascii=False)[:400]
            )
            return SendResult(
                self.name, digest.owner.whatsapp, "dry_run", detail="payload rendered"
            )
        if not self._configured:
            return SendResult(
                self.name,
                digest.owner.whatsapp,
                "skipped",
                detail="WHATSAPP_TOKEN/PHONE_NUMBER_ID/TEMPLATE_NAME not configured",
            )
        if self._attempts_this_run >= self.max_per_run:
            return SendResult(
                self.name,
                digest.owner.whatsapp,
                "skipped",
                detail=f"rate cap ({self.max_per_run}/run) reached",
            )
        self._attempts_this_run += 1
        return self._post(payload, digest.owner.whatsapp)

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult:
        return SendResult(self.name, "-", "skipped", detail="no WhatsApp rollup planned")

    def _post(self, payload: dict[str, Any], recipient: str) -> SendResult:
        try:
            resp = self._http.post(
                self._endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
            )
        except httpx.TransportError as exc:
            logger.exception("whatsapp POST to %s failed", recipient)
            return SendResult(self.name, recipient, "failed", detail=f"transport error: {exc}")
        if resp.status_code < 300:
            try:
                message_id = resp.json()["messages"][0]["id"]
            except (KeyError, IndexError, ValueError):
                message_id = "?"
            return SendResult(self.name, recipient, "sent", detail=f"message id {message_id}")
        logger.error("whatsapp POST %d: %s", resp.status_code, resp.text[:300])
        return SendResult(
            self.name,
            recipient,
            "failed",
            detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
