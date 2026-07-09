"""Channel adapter contract shared by email, Teams and WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from nagbot.config import RuntimeConfig
    from nagbot.digest.builder import Digest, Rollup
    from nagbot.digest.renderer import Renderer

SendStatus = Literal["sent", "failed", "skipped", "dry_run"]


@dataclass(frozen=True)
class SendResult:
    channel: str
    recipient: str
    status: SendStatus
    detail: str = ""
    cc: str | None = None


class ChannelAdapter(Protocol):
    name: str

    def send_digest(self, digest: Digest, *, dry_run: bool) -> SendResult: ...

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult: ...


def build_adapters(cfg: RuntimeConfig, renderer: Renderer) -> list[ChannelAdapter]:
    """Instantiate adapters for every channel enabled in the YAML config."""
    from nagbot.channels.email import EmailAdapter
    from nagbot.channels.teams import TeamsAdapter
    from nagbot.channels.whatsapp import WhatsAppAdapter

    adapters: list[ChannelAdapter] = []
    for name in cfg.app.channels.enabled:
        if name == "email":
            adapters.append(EmailAdapter.from_config(cfg, renderer))
        elif name == "teams":
            adapters.append(TeamsAdapter(renderer))
        elif name == "whatsapp":
            adapters.append(WhatsAppAdapter(renderer))
    return adapters
