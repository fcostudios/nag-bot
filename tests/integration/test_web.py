"""Web app tests: auth, healthz, and (in later stories) the dashboards."""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from nagbot.config import AppConfig, EnvSettings, RuntimeConfig
from nagbot.digest.renderer import Renderer
from nagbot.runtime import Runtime
from nagbot.store.repo import Store
from nagbot.web.app import create_app

GYE = ZoneInfo("America/Guayaquil")
NOW = datetime(2026, 7, 9, 13, 0, tzinfo=UTC)
AUTH = ("nagbot", "sekret")


def make_runtime(tmp_path: Path, *, password: str | None = "sekret") -> Runtime:
    env = EnvSettings(
        glpi_base_url="https://glpi.example.com/apirest.php",
        glpi_app_token="app",  # noqa: S106
        glpi_user_token="user",  # noqa: S106
        dashboard_password=password,
        nagbot_config_path=tmp_path / "unused.yaml",
        nagbot_db_path=tmp_path / "web.db",
    )
    app_cfg = AppConfig.model_validate(
        {"owners": {"jdoe": {"name": "Juan Doe", "email": "jdoe@x.com"}}}
    )
    cfg = RuntimeConfig(env=env, app=app_cfg, dry_run=True)
    store = Store(cfg.env.nagbot_db_path)

    def no_glpi() -> object:
        raise AssertionError("web tests must not hit GLPI unless mocked")

    return Runtime(
        cfg=cfg,
        store=store,
        renderer=Renderer(GYE, glpi_web_base=cfg.glpi_web_base),
        adapters=[],
        glpi_factory=no_glpi,  # type: ignore[arg-type]
    )


@pytest.fixture
def rt(tmp_path: Path) -> Runtime:
    return make_runtime(tmp_path)


@pytest.fixture
def client(rt: Runtime) -> TestClient:
    return TestClient(create_app(rt, with_scheduler=False))


def test_healthz_is_auth_exempt(client: TestClient, rt: Runtime) -> None:
    rt.store.start_run(trigger="cron", dry_run=True, now=NOW)
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["dry_run"] is True
    assert body["last_run"]["id"] == 1


def test_routes_require_basic_auth(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Basic realm="nagbot"'
    assert client.get("/", auth=("anyuser", "wrong")).status_code == 401
    # correct password (any username) passes auth; / itself lands in E3-S2
    assert client.get("/", auth=AUTH).status_code != 401


def test_missing_password_returns_503(tmp_path: Path) -> None:
    rt = make_runtime(tmp_path, password=None)
    client = TestClient(create_app(rt, with_scheduler=False))
    response = client.get("/")
    assert response.status_code == 503
    assert "DASHBOARD_PASSWORD" in response.text
    assert client.get("/healthz").status_code == 200  # healthz still works


def test_static_is_auth_exempt(client: TestClient) -> None:
    assert client.get("/static/style.css").status_code == 200


# --- E3-S2: WIP dashboard -----------------------------------------------------

from nagbot.store.repo import SnapshotRow  # noqa: E402


def seed_snapshots(store: Store, run_id: int | None = None) -> int:
    rid = run_id or store.start_run(trigger="cron", dry_run=True, now=NOW)

    def snap(tid: int, owner: str, name: str, tier: str, age: float, stale: float,
             snoozed: bool = False) -> SnapshotRow:
        return SnapshotRow(
            run_id=rid, ticket_id=tid, title=f"Ticket {tid}", status=2,
            date_opened=NOW, date_mod=NOW, sla_due=None,
            owner_key=owner, owner_name=name, tier=tier,
            age_bd=age, stale_bd=stale, sla_status="no_sla", snoozed=snoozed,
        )

    store.save_snapshots([
        snap(1, "tech:jdoe", "Juan Doe", "on_fire", 12, 8),
        snap(2, "tech:jdoe", "Juan Doe", "fresh", 1, 0.1),
        snap(3, "tech:asmith", "Ana Smith", "hot", 6, 5, snoozed=True),
    ])
    return rid


def test_wip_dashboard_renders(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    html = client.get("/", auth=AUTH).text
    assert "3</strong> open tickets" in html
    assert "Juan Doe" in html and "Ana Smith" in html
    assert html.index("Juan Doe") < html.index("Ana Smith")  # worst owner first
    assert "💤" in html  # snoozed marker
    assert "DRY-RUN" in html
    assert "/front/ticket.form.php?id=1" in html  # GLPI deep link


def test_wip_newest_run_wins(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    rid2 = rt.store.start_run(trigger="cron", dry_run=False, now=NOW)
    rt.store.save_snapshots([SnapshotRow(
        run_id=rid2, ticket_id=9, title="Only ticket", status=2,
        date_opened=NOW, date_mod=NOW, sla_due=None,
        owner_key="tech:jdoe", owner_name="Juan Doe", tier="aging",
        age_bd=3, stale_bd=2.5, sla_status="no_sla",
    )])
    html = client.get("/", auth=AUTH).text
    assert "1</strong> open tickets" in html
    assert "Only ticket" in html and "Ana Smith" not in html


def test_wip_empty_state(client: TestClient) -> None:
    html = client.get("/", auth=AUTH).text
    assert "No data yet" in html
