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


def test_escalation_job_added_only_when_enabled() -> None:
    cfg = RuntimeConfig(
        env=make_cfg().env,
        app=AppConfig.model_validate({"escalation": {"enabled": True, "cadence_seconds": 30}}),
        dry_run=True,
    )
    scheduler = build_scheduler(cfg, lambda: None, lambda: None, lambda: None)
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "escalation" in jobs
    assert jobs["escalation"].max_instances == 1
    assert jobs["escalation"].trigger.interval.total_seconds() == 30


def test_no_escalation_job_when_disabled() -> None:
    # default AppConfig → escalation.enabled is False → no job even if one is passed
    scheduler = build_scheduler(make_cfg(), lambda: None, lambda: None, lambda: None)
    assert "escalation" not in {job.id for job in scheduler.get_jobs()}
