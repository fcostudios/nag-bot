from pathlib import Path

import pytest

from nagbot.config import AppConfig, ConfigError, EnvSettings, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_env(tmp_path: Path, **overrides: object) -> EnvSettings:
    yaml_path = overrides.pop("config_path", None) or (REPO_ROOT / "config/nagbot.example.yaml")
    defaults: dict[str, object] = {
        "glpi_base_url": "https://glpi.example.com/apirest.php",
        "glpi_app_token": "app-token",
        "glpi_user_token": "user-token",
        "smtp_host": "smtp.example.com",
        "smtp_from": "nagbot@example.com",
        "nagbot_config_path": yaml_path,
        "nagbot_db_path": tmp_path / "nagbot.db",
    }
    defaults.update(overrides)
    return EnvSettings(**defaults)  # type: ignore[arg-type]


def write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "nagbot.yaml"
    p.write_text(body)
    return p


def test_example_yaml_parses_and_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NAGBOT_DRY_RUN", raising=False)
    cfg = load_config(make_env(tmp_path))
    assert cfg.app.timezone == "America/Guayaquil"
    assert cfg.app.thresholds.hot_stale_bd == 5
    assert cfg.app.owners["jdoe"].email == "jdoe@example.com"
    assert cfg.glpi_web_base == "https://glpi.example.com"


def test_dry_run_defaults_true(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    assert env.nagbot_dry_run is True
    assert load_config(env).dry_run is True


@pytest.mark.parametrize(
    ("env_dry", "yaml_dry", "effective"),
    [(True, True, True), (True, False, True), (False, True, True), (False, False, False)],
)
def test_dry_run_truth_table(
    tmp_path: Path, env_dry: bool, yaml_dry: bool, effective: bool
) -> None:
    yaml_path = write_yaml(
        tmp_path, f"channels:\n  dry_run: {str(yaml_dry).lower()}\n  enabled: [email]\n"
    )
    env = make_env(tmp_path, config_path=yaml_path, nagbot_dry_run=env_dry)
    assert load_config(env).dry_run is effective


def test_email_enabled_requires_smtp(tmp_path: Path) -> None:
    env = make_env(tmp_path, smtp_host=None, smtp_from=None)
    with pytest.raises(ConfigError) as exc:
        load_config(env)
    assert "SMTP_HOST" in str(exc.value)
    assert "SMTP_FROM" in str(exc.value)


def test_teams_enabled_requires_webhook(tmp_path: Path) -> None:
    yaml_path = write_yaml(tmp_path, "channels:\n  enabled: [email, teams]\n")
    with pytest.raises(ConfigError, match="TEAMS_WEBHOOK_URL"):
        load_config(make_env(tmp_path, config_path=yaml_path))


def test_missing_glpi_vars_fail_fast(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="GLPI_APP_TOKEN"):
        load_config(make_env(tmp_path, glpi_app_token=""))


def test_missing_yaml_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(make_env(tmp_path, config_path=tmp_path / "nope.yaml"))


def test_bad_timezone_rejected() -> None:
    with pytest.raises(ValueError, match="unknown timezone"):
        AppConfig.model_validate({"timezone": "Mars/Olympus"})


def test_bad_cron_rejected() -> None:
    with pytest.raises(ValueError, match="5 fields"):
        AppConfig.model_validate({"schedule": {"digest_cron": "8am daily"}})


def test_bad_channel_rejected() -> None:
    with pytest.raises(ValueError):
        AppConfig.model_validate({"channels": {"enabled": ["email", "pigeon"]}})
