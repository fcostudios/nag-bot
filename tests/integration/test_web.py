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


# --- E3-S3: ops dashboard + ticket history --------------------------------------

def seed_sends(store: Store, rid: int) -> None:
    store.log_send(run_id=rid, kind="digest", channel="email", recipient="jdoe@x.com",
                   status="dry_run", now=NOW, ticket_ids=[1, 2], detail="to=jdoe@x.com")
    store.log_send(run_id=rid, kind="digest", channel="teams", recipient="tech:jdoe",
                   status="skipped", now=NOW, ticket_ids=[1], detail="stub")
    store.log_send(run_id=rid, kind="escalation", channel="email", recipient="boss@x.com",
                   status="sent", now=NOW, ticket_ids=[1], detail="manager CC")


def test_ops_dashboard_lists_runs_and_sends(client: TestClient, rt: Runtime) -> None:
    rid = seed_snapshots(rt.store)
    rt.store.finish_run(
        rid, status="ok", now=NOW, tickets_seen=3, digests_built=2, sends_attempted=3,
        warnings=["ticket #7: technician 'ghost' not in owner map"],
    )
    seed_sends(rt.store, rid)
    html = client.get("/ops", auth=AUTH).text
    assert "DRY-RUN" in html and ">ok<" in html
    assert "jdoe@x.com" in html and "boss@x.com" in html
    assert "Unmapped owners" in html and "ghost" in html


def test_ops_send_log_filters(client: TestClient, rt: Runtime) -> None:
    rid = seed_snapshots(rt.store)
    seed_sends(rt.store, rid)
    html = client.get("/ops?channel=teams", auth=AUTH).text
    assert "stub" in html and "manager CC" not in html
    html = client.get("/ops?status=sent", auth=AUTH).text
    assert "manager CC" in html and "stub" not in html


def test_ticket_history_page(client: TestClient, rt: Runtime) -> None:
    rid = seed_snapshots(rt.store)
    seed_sends(rt.store, rid)
    html = client.get("/tickets/1", auth=AUTH).text
    assert "Ticket 1" in html
    assert "manager CC" in html  # escalation send listed
    assert "snooze until" in html  # snooze form shown when not snoozed


def test_unknown_ticket_404(client: TestClient) -> None:
    response = client.get("/tickets/999", auth=AUTH)
    assert response.status_code == 404
    assert "never seen this ticket" in response.text


# --- E3-S4: snooze / run-now / preview -------------------------------------------

import httpx  # noqa: E402
import respx  # noqa: E402

from nagbot.glpi.client import GlpiClient  # noqa: E402

BASE = "https://glpi.example.com/apirest.php"


def make_glpi_runtime(tmp_path: Path) -> Runtime:
    rt = make_runtime(tmp_path)

    def factory() -> GlpiClient:
        return GlpiClient(BASE, "app", "user", server_timezone=GYE, sleep=lambda _s: None)

    return Runtime(cfg=rt.cfg, store=rt.store, renderer=rt.renderer,
                   adapters=[], glpi_factory=factory)


def mock_glpi_rows(rows: list[dict[str, object]]) -> None:
    respx.post(f"{BASE}/initSession").mock(
        return_value=httpx.Response(200, json={"session_token": "s"}))
    respx.get(f"{BASE}/killSession").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{BASE}/listSearchOptions/Ticket").mock(
        return_value=httpx.Response(200, json={}))
    respx.get(f"{BASE}/search/Ticket").mock(
        return_value=httpx.Response(200, json={"data": rows}))


GLPI_ROW = {
    "2": 1, "1": "Stale thing", "12": 2, "15": "2026-06-20 09:00:00",
    "19": "2026-06-26 09:00:00", "18": None, "5": "jdoe", "8": None,
}


def test_snooze_roundtrip_via_forms(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    response = client.post(
        "/snooze",
        data={"ticket_id": "1", "until": "2099-12-31", "reason": "vendor"},
        auth=AUTH, follow_redirects=False,
    )
    assert response.status_code == 303
    assert rt.store.snooze_for(1) is not None
    html = client.get("/tickets/1", auth=AUTH).text
    assert "Snoozed until" in html and "2099-12-31" in html
    client.post("/unsnooze", data={"ticket_id": "1"}, auth=AUTH)
    assert rt.store.snooze_for(1) is None


def test_snooze_validation_errors(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    r = client.post("/snooze", data={"ticket_id": "1", "until": "not-a-date"},
                    auth=AUTH, follow_redirects=False)
    assert "invalid+date" in r.headers["location"]
    r = client.post("/snooze", data={"ticket_id": "1", "until": "2001-01-01"},
                    auth=AUTH, follow_redirects=False)
    assert "past" in r.headers["location"]
    assert rt.store.snooze_for(1) is None


@respx.mock
def test_preview_renders_digests_without_writes(tmp_path: Path) -> None:
    mock_glpi_rows([GLPI_ROW])
    rt = make_glpi_runtime(tmp_path)
    client = TestClient(create_app(rt, with_scheduler=False))
    html = client.get("/preview", auth=AUTH).text
    assert "Juan Doe" in html and "Stale thing" in html
    assert "Subject:" in html
    assert rt.store.last_run() is None  # no run rows written
    assert rt.store.recent_sends() == []


@respx.mock
def test_preview_glpi_failure_shows_error(tmp_path: Path) -> None:
    respx.post(f"{BASE}/initSession").mock(return_value=httpx.Response(500, text="down"))
    rt = make_glpi_runtime(tmp_path)
    client = TestClient(create_app(rt, with_scheduler=False))
    response = client.get("/preview", auth=AUTH)
    assert response.status_code == 502
    assert "GLPI fetch failed" in response.text


@respx.mock
def test_run_now_defaults_to_dry_run(tmp_path: Path) -> None:
    mock_glpi_rows([GLPI_ROW])
    rt = make_glpi_runtime(tmp_path)
    app = create_app(rt, with_scheduler=False)
    client = TestClient(app)
    response = client.post("/run-now", data={}, auth=AUTH, follow_redirects=False)
    assert response.status_code == 303 and "/ops" in response.headers["location"]
    app.state.last_run_thread.join(timeout=10)
    last = rt.store.last_run()
    assert last is not None and last.trigger == "manual" and last.dry_run is True


def test_run_now_busy_flash(client: TestClient) -> None:
    from nagbot.run import _RUN_LOCK

    assert _RUN_LOCK.acquire(blocking=False)
    try:
        response = client.post("/run-now", data={}, auth=AUTH, follow_redirects=False)
        assert "busy" in response.headers["location"]
    finally:
        _RUN_LOCK.release()
