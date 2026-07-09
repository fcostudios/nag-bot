# E1-S2: Config loading (env + YAML)

Status: Draft

## Story
As the operator, I want secrets from env vars and tuning from a YAML file merged into one
validated config, so that the container deploys with no secrets on disk and misconfig
fails fast instead of misbehaving at 08:00.

## Context
After E1-S1 scaffold. Everything downstream (client, engine, adapters, web) reads
`RuntimeConfig` from this story.

## Acceptance Criteria
- AC1: `EnvSettings` reads all vars from architecture §3.1; `NAGBOT_DRY_RUN` defaults **true**.
- AC2: `AppConfig` parses `config/nagbot.example.yaml` (timezone, schedule, thresholds, holidays, channels, glpi, owners, groups, fallback) with the documented defaults.
- AC3: `load_config()` returns a frozen `RuntimeConfig`; effective `dry_run = env OR yaml` (both must be false to go live).
- AC4: Email enabled without `SMTP_HOST`/`SMTP_FROM` → startup raises `ConfigError` naming the missing vars; same pattern for teams/whatsapp when enabled.
- AC5: `config/nagbot.example.yaml` and `.env.example` committed and in sync with the models.

## Tasks
- [ ] src/nagbot/config.py: EnvSettings, ScheduleCfg, Thresholds, ChannelsCfg, GlpiTuning, OwnerCfg, FallbackCfg, AppConfig, RuntimeConfig, ConfigError, load_config() — AC1..AC4
- [ ] config/nagbot.example.yaml — AC2, AC5
- [ ] .env.example — AC5
- [ ] tests/unit/test_config.py — AC1..AC4

## Dev Notes
pydantic-settings `BaseSettings` (env only, no .env auto-load in prod code — compose
injects). Thresholds defaults: fresh_max_age_bd=2, aging_stale_bd=2, hot_stale_bd=5,
on_fire_stale_bd=7, sla_due_soon_hours=24, escalation_red_days=3. `ChannelsCfg.enabled`
validated against {"email","teams","whatsapp"}. Timezone validated with `zoneinfo`.
YAML via `yaml.safe_load`.

## Testing
tests/unit/test_config.py: dry-run truth table (env×yaml), missing-SMTP failure message,
example YAML round-trips, bad timezone/cron rejected. Env isolation via monkeypatch.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
