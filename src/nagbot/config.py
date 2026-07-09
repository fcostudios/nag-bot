"""Configuration: secrets/endpoints from env vars, tuning from a mounted YAML file.

Dry-run is the hard default: the effective flag is ``env OR yaml`` — either source
can force it on, and only both agreeing (false) allows live sends.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ChannelName = Literal["email", "teams", "whatsapp"]


class ConfigError(Exception):
    """Raised on invalid or inconsistent configuration; message is operator-readable."""


class EnvSettings(BaseSettings):
    """Secrets and endpoints — environment variables only."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    glpi_base_url: str = ""
    glpi_app_token: SecretStr = SecretStr("")
    glpi_user_token: SecretStr = SecretStr("")

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    smtp_from: str | None = None

    teams_webhook_url: SecretStr | None = None

    whatsapp_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_template_name: str | None = None

    dashboard_password: SecretStr | None = None

    nagbot_config_path: Path = Path("/config/nagbot.yaml")
    nagbot_db_path: Path = Path("/data/nagbot.db")
    nagbot_dry_run: bool = True  # HARD DEFAULT: must be explicitly false to go live
    nagbot_log_level: str = "INFO"


class ScheduleCfg(BaseModel):
    digest_cron: str = "0 8 * * mon-fri"
    rollup_cron: str = "30 8 * * mon"

    @field_validator("digest_cron", "rollup_cron")
    @classmethod
    def _five_fields(cls, v: str) -> str:
        if len(v.split()) != 5:
            raise ValueError(f"cron expression must have 5 fields, got {v!r}")
        return v


class Thresholds(BaseModel):
    fresh_max_age_bd: float = 2.0
    aging_stale_bd: float = 2.0
    hot_stale_bd: float = 5.0
    on_fire_stale_bd: float = 7.0
    sla_due_soon_hours: float = 24.0
    escalation_red_days: int = 3


class ChannelsCfg(BaseModel):
    dry_run: bool = True
    enabled: list[ChannelName] = Field(default_factory=lambda: list[ChannelName](["email"]))
    whatsapp_max_per_run: int = 20


class GlpiTuning(BaseModel):
    server_timezone: str | None = None  # defaults to app timezone
    page_size: int = 100
    field_ids: dict[str, int] = Field(default_factory=dict)


class OwnerCfg(BaseModel):
    name: str
    email: str | None = None
    teams_id: str | None = None
    whatsapp: str | None = None
    manager: str | None = None
    aliases: list[str] = Field(default_factory=list)

    @field_validator("whatsapp")
    @classmethod
    def _e164(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\+[1-9]\d{6,14}", v):
            raise ValueError(f"whatsapp number {v!r} must be E.164 (+593999999999)")
        return v


class FallbackCfg(BaseModel):
    email: str | None = None
    rollup_recipients: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Tuning — YAML file only."""

    timezone: str = "America/Guayaquil"
    schedule: ScheduleCfg = Field(default_factory=ScheduleCfg)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    holidays: list[date] = Field(default_factory=list)
    channels: ChannelsCfg = Field(default_factory=ChannelsCfg)
    glpi: GlpiTuning = Field(default_factory=GlpiTuning)
    owners: dict[str, OwnerCfg] = Field(default_factory=dict)
    groups: dict[str, OwnerCfg] = Field(default_factory=dict)
    fallback: FallbackCfg = Field(default_factory=FallbackCfg)

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone {v!r}") from exc
        return v


class RuntimeConfig(BaseModel):
    """Merged, validated configuration handed to the rest of the app."""

    model_config = {"frozen": True}

    env: EnvSettings
    app: AppConfig
    dry_run: bool

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app.timezone)

    @property
    def glpi_server_tz(self) -> ZoneInfo:
        return ZoneInfo(self.app.glpi.server_timezone or self.app.timezone)

    @property
    def glpi_web_base(self) -> str:
        return self.env.glpi_base_url.removesuffix("/").removesuffix("/apirest.php")


def _load_yaml(path: Path) -> AppConfig:
    if not path.exists():
        raise ConfigError(f"config file not found: {path} (set NAGBOT_CONFIG_PATH)")
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    try:
        return AppConfig.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid config in {path}: {exc}") from exc


def _validate(env: EnvSettings, app: AppConfig) -> None:
    missing: list[str] = []
    if not env.glpi_base_url:
        missing.append("GLPI_BASE_URL")
    if not env.glpi_app_token.get_secret_value():
        missing.append("GLPI_APP_TOKEN")
    if not env.glpi_user_token.get_secret_value():
        missing.append("GLPI_USER_TOKEN")
    if "email" in app.channels.enabled:
        if not env.smtp_host:
            missing.append("SMTP_HOST (email channel is enabled)")
        if not env.smtp_from:
            missing.append("SMTP_FROM (email channel is enabled)")
    if "teams" in app.channels.enabled and not env.teams_webhook_url:
        missing.append("TEAMS_WEBHOOK_URL (teams channel is enabled)")
    if "whatsapp" in app.channels.enabled:
        for var, val in (
            ("WHATSAPP_TOKEN", env.whatsapp_token),
            ("WHATSAPP_PHONE_NUMBER_ID", env.whatsapp_phone_number_id),
            ("WHATSAPP_TEMPLATE_NAME", env.whatsapp_template_name),
        ):
            if not val:
                missing.append(f"{var} (whatsapp channel is enabled)")
    if missing:
        raise ConfigError(
            "missing required environment variables:\n  - " + "\n  - ".join(missing)
        )


def load_config(env: EnvSettings | None = None) -> RuntimeConfig:
    env = env or EnvSettings()
    app = _load_yaml(env.nagbot_config_path)
    _validate(env, app)
    return RuntimeConfig(env=env, app=app, dry_run=env.nagbot_dry_run or app.channels.dry_run)
