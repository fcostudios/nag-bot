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


@dataclass(frozen=True)
class EscalationAlert:
    """A single per-ticket urgent alert (E7). Minimal for E7-S1; enriched in E7-S3."""

    recipient: str  # E.164 WhatsApp number
    text: str


class ChannelAdapter(Protocol):
    name: str

    def send_digest(self, digest: Digest, *, dry_run: bool) -> SendResult: ...

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult: ...


def begin_run(adapters: list[ChannelAdapter]) -> None:
    """Reset any per-run adapter state (e.g. WhatsApp's rate-cap counter)."""
    for adapter in adapters:
        hook = getattr(adapter, "begin_run", None)
        if callable(hook):
            hook()


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
            webhook = (
                cfg.env.teams_webhook_url.get_secret_value() if cfg.env.teams_webhook_url else ""
            )
            adapters.append(TeamsAdapter(renderer, webhook))
        elif name == "whatsapp":
            adapters.append(
                WhatsAppAdapter(
                    renderer,
                    token=(
                        cfg.env.whatsapp_token.get_secret_value() if cfg.env.whatsapp_token else ""
                    ),
                    phone_number_id=cfg.env.whatsapp_phone_number_id or "",
                    template_name=cfg.env.whatsapp_template_name or "",
                    max_per_run=cfg.app.channels.whatsapp_max_per_run,
                )
            )
    return adapters
