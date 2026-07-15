"""OpenWA adapter — sends a WhatsApp text via a self-hosted OpenWA sidecar.

Spine AD-2: OpenWA runs as its own container exposing an HTTP API; this adapter is
a thin `httpx` client to `OPENWA_URL` and never drives a browser. AD-3: OpenWA is an
*alert* channel — it implements `send_alert`, not the digest protocol. The live
WhatsApp-Web QR session lives in the sidecar (AD-9, ops runbook).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from nagbot.channels.base import EscalationAlert, SendResult

if TYPE_CHECKING:
    from nagbot.config import RuntimeConfig

logger = logging.getLogger(__name__)


def to_chat_id(number: str) -> str:
    """E.164 (``+593999999999``) → OpenWA individual chatId (``593999999999@c.us``)."""
    return f"{number.strip().lstrip('+')}@c.us"


class OpenWaAdapter:
    name = "openwa"

    def __init__(self, base_url: str = "", *, http: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30)

    @classmethod
    def from_config(cls, cfg: RuntimeConfig) -> OpenWaAdapter:
        return cls(cfg.env.openwa_url or "")

    @property
    def _configured(self) -> bool:
        return bool(self.base_url)

    def send_alert(self, alert: EscalationAlert, *, dry_run: bool) -> SendResult:
        """Send one urgent alert. Never raises — a P0 dispatch must degrade to a
        status (so a later rung/fallback can act), not crash."""
        recipient = alert.recipient
        if not recipient:
            return SendResult(self.name, "-", "skipped", detail="no recipient number")
        if dry_run:
            logger.info("openwa dry-run to %s: %s", recipient, alert.text[:200])
            return SendResult(self.name, recipient, "dry_run", detail="message rendered")
        if not self._configured:
            return SendResult(self.name, recipient, "skipped", detail="OPENWA_URL not configured")

        chat_id = to_chat_id(recipient)
        try:
            resp = self._http.post(
                f"{self.base_url}/sendText",
                json={"chatId": chat_id, "message": alert.text},
            )
        except httpx.TransportError as exc:
            logger.exception("openwa POST to %s failed", recipient)
            return SendResult(self.name, recipient, "failed", detail=f"transport error: {exc}")

        if resp.status_code < 300:
            try:
                body = resp.json()
                # OpenWA EASY API returns {"success": bool}; a non-object 2xx body
                # (or non-JSON) is treated as delivered — never let parsing raise.
                ok = bool(body.get("success", True)) if isinstance(body, dict) else True
            except ValueError:
                ok = True
            if ok:
                return SendResult(self.name, recipient, "sent", detail=f"chatId {chat_id}")
            return SendResult(
                self.name, recipient, "failed", detail=f"openwa error: {resp.text[:200]}"
            )
        logger.error("openwa POST %d: %s", resp.status_code, resp.text[:300])
        return SendResult(
            self.name, recipient, "failed", detail=f"HTTP {resp.status_code}: {resp.text[:200]}"
        )
