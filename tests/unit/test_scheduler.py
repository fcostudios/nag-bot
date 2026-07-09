from pathlib import Path

from nagbot.config import AppConfig, EnvSettings, RuntimeConfig
from nagbot.scheduler import build_scheduler


def make_cfg() -> RuntimeConfig:
    env = EnvSettings(
        glpi_base_url="https://x/apirest.php",
        glpi_app_token="a",  # noqa: S106
        glpi_user_token="u",  # noqa: S106
        nagbot_config_path=Path("/nonexistent"),
    )
    return RuntimeConfig(env=env, app=AppConfig(), dry_run=True)


def test_scheduler_registers_both_crons() -> None:
    fired: list[str] = []
    scheduler = build_scheduler(
        make_cfg(), lambda: fired.append("nag"), lambda: fired.append("rollup")
    )
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"digest", "rollup"}
    assert jobs["digest"].max_instances == 1
    assert jobs["digest"].misfire_grace_time == 3600
    # default YAML crons: weekday 08:00 digest, Monday 08:30 rollup, in app tz
    assert str(jobs["digest"].trigger.timezone) == "America/Guayaquil"
    fields = {f.name: str(f) for f in jobs["digest"].trigger.fields}
    assert fields["hour"] == "8" and fields["day_of_week"] == "mon-fri"
    rollup_fields = {f.name: str(f) for f in jobs["rollup"].trigger.fields}
    assert rollup_fields["day_of_week"] == "mon" and rollup_fields["minute"] == "30"
