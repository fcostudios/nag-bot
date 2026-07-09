"""End-to-end pipeline tests: mocked GLPI + tmp SQLite + fake SMTP email adapter."""

from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

import nagbot.run as run_module
from nagbot.channels.email import EmailAdapter
from nagbot.config import AppConfig, EnvSettings, RuntimeConfig
from nagbot.digest.renderer import Renderer
from nagbot.glpi.client import GlpiClient
from nagbot.run import execute_nag_run
from nagbot.store.repo import Store
from tests.unit.test_channels import FakeSmtp  # reuse the recording fake

BASE = "https://glpi.example.com/apirest.php"
GYE = ZoneInfo("America/Guayaquil")
NOW = datetime(2026, 7, 9, 8, 0, tzinfo=GYE)  # Thursday


@pytest.fixture
def cfg(tmp_path: Path) -> RuntimeConfig:
    env = EnvSettings(
        glpi_base_url=BASE,
        glpi_app_token="app",  # noqa: S106
        glpi_user_token="user",  # noqa: S106
        smtp_host="smtp.example.com",
        smtp_from="nagbot@example.com",
        nagbot_config_path=tmp_path / "unused.yaml",
        nagbot_db_path=tmp_path / "nagbot.db",
    )
    app = AppConfig.model_validate(
        {
            "timezone": "America/Guayaquil",
            "owners": {
                "jdoe": {
                    "name": "Juan Doe",
                    "email": "jdoe@x.com",
                    "manager": "boss@x.com",
                },
            },
            "fallback": {"email": "lead@x.com"},
        }
    )
    return RuntimeConfig(env=env, app=app, dry_run=True)


@pytest.fixture
def store(cfg: RuntimeConfig) -> Store:
    return Store(cfg.env.nagbot_db_path)


def glpi_factory() -> GlpiClient:
    return GlpiClient(
        BASE, "app", "user", server_timezone=GYE, sleep=lambda _s: None
    )


def row(tid: int, opened: str, mod: str, tech: str | None = "jdoe") -> dict[str, object]:
    return {
        "2": tid,
        "1": f"Ticket {tid}",
        "12": 2,
        "15": opened,
        "19": mod,
        "18": None,
        "5": tech,
        "8": None,
    }


def mock_glpi(rows: list[dict[str, object]]) -> None:
    respx.post(f"{BASE}/initSession").mock(
        return_value=httpx.Response(200, json={"session_token": "s"})
    )
    respx.get(f"{BASE}/killSession").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{BASE}/listSearchOptions/Ticket").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get(f"{BASE}/search/Ticket").mock(
        return_value=httpx.Response(200, json={"data": rows})
    )


ROWS = [
    row(1, "2026-06-20 09:00:00", "2026-06-26 09:00:00"),  # stale ~9bd -> on_fire
    row(2, "2026-07-06 09:00:00", "2026-07-08 16:00:00"),  # fresh
    row(3, "2026-07-01 09:00:00", "2026-07-01 09:00:00", tech="ghost"),  # unmapped -> fallback
]


def make_email_adapter(smtp: FakeSmtp, cfg: RuntimeConfig) -> EmailAdapter:
    renderer = Renderer(GYE, glpi_web_base=cfg.glpi_web_base)
    return EmailAdapter(
        renderer,
        sender="nagbot@example.com",
        smtp_factory=lambda: smtp,  # type: ignore[arg-type,return-value]
    )


@respx.mock
def test_dry_run_end_to_end(cfg: RuntimeConfig, store: Store) -> None:
    mock_glpi(ROWS)
    smtp = FakeSmtp()
    report = execute_nag_run(
        cfg, store, [make_email_adapter(smtp, cfg)], glpi_factory,
        dry_run=True, trigger="cron", now=NOW,
    )
    assert report.status == "ok"
    assert report.tickets_seen == 3
    assert report.digests_built == 2  # jdoe + fallback
    # SMTP never touched in dry-run
    assert smtp.calls == []
    # snapshots written for all tickets
    run, snaps = store.latest_snapshot()
    assert run is not None and run.dry_run
    assert {s.ticket_id for s in snaps} == {1, 2, 3}
    assert {s.tier for s in snaps if s.ticket_id == 1} == {"on_fire"}
    # send log has dry_run rows only
    sends = store.recent_sends()
    assert sends and all(s.status == "dry_run" for s in sends)
    # unmapped tech surfaced as warning
    assert any("ghost" in w for w in report.warnings)


@respx.mock
def test_live_run_sends_email(cfg: RuntimeConfig, store: Store) -> None:
    mock_glpi(ROWS)
    smtp = FakeSmtp()
    report = execute_nag_run(
        cfg, store, [make_email_adapter(smtp, cfg)], glpi_factory,
        dry_run=False, trigger="manual", now=NOW,
    )
    assert report.status == "ok"
    assert "send_message" in smtp.calls
    recipients = {m["To"] for m in smtp.messages}
    assert recipients == {"jdoe@x.com", "lead@x.com"}
    assert all(s.status == "sent" for s in store.recent_sends())


@respx.mock
def test_snoozed_ticket_excluded_but_snapshotted(cfg: RuntimeConfig, store: Store) -> None:
    mock_glpi(ROWS)
    store.snooze(1, until=date(2026, 7, 15), now=NOW.astimezone(UTC), reason="vendor")
    smtp = FakeSmtp()
    report = execute_nag_run(
        cfg, store, [make_email_adapter(smtp, cfg)], glpi_factory,
        dry_run=True, trigger="cron", now=NOW,
    )
    _, snaps = store.latest_snapshot()
    snoozed_snap = next(s for s in snaps if s.ticket_id == 1)
    assert snoozed_snap.snoozed is True
    digest_sends = [s for s in store.recent_sends() if s.kind == "digest"]
    assert all(1 not in s.ticket_ids for s in digest_sends)
    assert report.digests_built == 2


@respx.mock
def test_escalation_ccs_manager_after_streak(cfg: RuntimeConfig, store: Store) -> None:
    # a ticket already deep in red on every simulated day (stale since mid-June)
    mock_glpi([row(1, "2026-06-10 09:00:00", "2026-06-15 09:00:00")])
    smtp = FakeSmtp()
    adapter = make_email_adapter(smtp, cfg)
    days = [datetime(2026, 7, 6 + i, 8, 0, tzinfo=GYE) for i in range(3)]
    for day in days:
        execute_nag_run(
            cfg, store, [adapter], glpi_factory, dry_run=False, trigger="cron", now=day
        )
    # third consecutive red run-day -> manager CC exactly once
    ccs = [m["Cc"] for m in smtp.messages]
    assert ccs == [None, None, "boss@x.com"]
    escalation_rows = [s for s in store.recent_sends() if s.kind == "escalation"]
    assert len(escalation_rows) == 1
    assert escalation_rows[0].recipient == "boss@x.com"


def test_overlap_guard_returns_busy(cfg: RuntimeConfig, store: Store) -> None:
    acquired = run_module._RUN_LOCK.acquire(blocking=False)
    assert acquired
    try:
        report = execute_nag_run(
            cfg, store, [], glpi_factory, dry_run=True, trigger="manual", now=NOW
        )
        assert report.status == "busy"
        assert store.last_run() is None  # nothing was written
    finally:
        run_module._RUN_LOCK.release()


@respx.mock
def test_glpi_failure_marks_run_failed(cfg: RuntimeConfig, store: Store) -> None:
    respx.post(f"{BASE}/initSession").mock(return_value=httpx.Response(500, text="down"))
    report = execute_nag_run(
        cfg, store, [], glpi_factory, dry_run=True, trigger="cron", now=NOW
    )
    assert report.status == "failed"
    last = store.last_run()
    assert last is not None and last.status == "failed" and last.error


# --- E4-S2: manager rollup ----------------------------------------------------------

from nagbot.run import execute_rollup_run  # noqa: E402


@respx.mock
def test_rollup_sends_to_recipients(cfg: RuntimeConfig, store: Store) -> None:
    mock_glpi(ROWS)
    smtp = FakeSmtp()
    renderer = Renderer(GYE, glpi_web_base=cfg.glpi_web_base)
    adapter = EmailAdapter(
        renderer, sender="nagbot@example.com",
        smtp_factory=lambda: smtp,  # type: ignore[arg-type,return-value]
        rollup_recipients=["boss@x.com", "cto@x.com"],
    )
    # a digest run first, to populate snapshots
    execute_nag_run(cfg, store, [adapter], glpi_factory, dry_run=True, trigger="cron", now=NOW)
    report = execute_rollup_run(cfg, store, [adapter], dry_run=False, now=NOW)
    assert report.status == "ok"
    (msg,) = smtp.messages  # digest run was dry; only the rollup hit SMTP
    assert msg["To"] == "boss@x.com, cto@x.com"
    assert "Weekly WIP rollup" in msg["Subject"]
    rollup_rows = store.recent_sends(kind="rollup")
    assert len(rollup_rows) == 1 and rollup_rows[0].status == "sent"
    assert rollup_rows[0].ticket_ids  # leaderboard ids recorded
    last = store.last_run()
    assert last is not None and last.trigger == "rollup" and last.status == "ok"


@respx.mock
def test_rollup_respects_dry_run(cfg: RuntimeConfig, store: Store) -> None:
    mock_glpi(ROWS)
    smtp = FakeSmtp()
    renderer = Renderer(GYE, glpi_web_base=cfg.glpi_web_base)
    adapter = EmailAdapter(
        renderer, sender="nagbot@example.com",
        smtp_factory=lambda: smtp,  # type: ignore[arg-type,return-value]
        rollup_recipients=["boss@x.com"],
    )
    execute_nag_run(cfg, store, [adapter], glpi_factory, dry_run=True, trigger="cron", now=NOW)
    report = execute_rollup_run(cfg, store, [adapter], dry_run=True, now=NOW)
    assert report.status == "ok"
    assert smtp.calls == []
    assert store.recent_sends(kind="rollup")[0].status == "dry_run"


def test_rollup_skips_without_snapshots(cfg: RuntimeConfig, store: Store) -> None:
    report = execute_rollup_run(cfg, store, [], dry_run=True, now=NOW)
    assert report.status == "skipped"
    assert store.last_run() is None  # no run row for a skipped rollup


# --- E6-S2 close-out: all three channels through build_adapters -----------------------

from nagbot.channels.base import build_adapters  # noqa: E402


@respx.mock
def test_all_channels_dry_run_end_to_end(tmp_path: Path) -> None:
    mock_glpi(ROWS)
    env = EnvSettings(
        glpi_base_url=BASE,
        glpi_app_token="app",  # noqa: S106
        glpi_user_token="user",  # noqa: S106
        smtp_host="smtp.example.com",
        smtp_from="nagbot@example.com",
        teams_webhook_url="https://prod-1.westus.logic.azure.com/wf/x",
        whatsapp_token="wa-token",  # noqa: S106
        whatsapp_phone_number_id="12345",
        whatsapp_template_name="nag_digest",
        nagbot_config_path=tmp_path / "unused.yaml",
        nagbot_db_path=tmp_path / "all.db",
    )
    app = AppConfig.model_validate(
        {
            "channels": {"enabled": ["email", "teams", "whatsapp"]},
            "owners": {"jdoe": {"name": "Juan Doe", "email": "jdoe@x.com",
                                "teams_id": "jdoe@corp.x.com", "whatsapp": "+593999999999"}},
            "fallback": {"email": "lead@x.com"},
        }
    )
    cfg = RuntimeConfig(env=env, app=app, dry_run=True)
    store = Store(cfg.env.nagbot_db_path)
    renderer = Renderer(GYE, glpi_web_base=cfg.glpi_web_base)
    adapters = build_adapters(cfg, renderer)
    assert [a.name for a in adapters] == ["email", "teams", "whatsapp"]
    report = execute_nag_run(
        cfg, store, adapters, glpi_factory, dry_run=True, trigger="cron", now=NOW
    )
    assert report.status == "ok"
    channels = {(s.channel, s.status) for s in store.recent_sends()}
    assert {("email", "dry_run"), ("teams", "dry_run")} <= channels
    # whatsapp: jdoe digest dry_run; fallback owner has no number -> skipped
    assert ("whatsapp", "dry_run") in channels and ("whatsapp", "skipped") in channels
