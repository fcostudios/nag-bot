"""Process-wide wiring shared by the CLI and the web app."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from nagbot.channels.base import ChannelAdapter, build_adapters
from nagbot.config import RuntimeConfig, load_config
from nagbot.digest.renderer import Renderer
from nagbot.glpi.client import GlpiClient
from nagbot.run import GlpiFactory
from nagbot.store.repo import Store


@dataclass
class Runtime:
    cfg: RuntimeConfig
    store: Store
    renderer: Renderer
    adapters: list[ChannelAdapter]
    glpi_factory: GlpiFactory


def _make_client(cfg: RuntimeConfig) -> GlpiClient:
    return GlpiClient(
        cfg.env.glpi_base_url,
        cfg.env.glpi_app_token.get_secret_value(),
        cfg.env.glpi_user_token.get_secret_value(),
        page_size=cfg.app.glpi.page_size,
        server_timezone=cfg.glpi_server_tz,
        web_base=cfg.glpi_web_base,
    )


def build_runtime(cfg: RuntimeConfig | None = None) -> Runtime:
    cfg = cfg or load_config()
    cfg.env.nagbot_db_path.parent.mkdir(parents=True, exist_ok=True)
    store = Store(cfg.env.nagbot_db_path)
    renderer = Renderer(cfg.tz, glpi_web_base=cfg.glpi_web_base)
    return Runtime(
        cfg=cfg,
        store=store,
        renderer=renderer,
        adapters=build_adapters(cfg, renderer),
        glpi_factory=partial(_make_client, cfg),
    )
