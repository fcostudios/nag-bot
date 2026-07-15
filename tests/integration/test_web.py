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

    def snap(
        tid: int, owner: str, name: str, tier: str, age: float, stale: float, snoozed: bool = False
    ) -> SnapshotRow:
        return SnapshotRow(
            run_id=rid,
            ticket_id=tid,
            title=f"Ticket {tid}",
            status=2,
            date_opened=NOW,
            date_mod=NOW,
            sla_due=None,
            owner_key=owner,
            owner_name=name,
            tier=tier,
            age_bd=age,
            stale_bd=stale,
            sla_status="no_sla",
            snoozed=snoozed,
        )

    store.save_snapshots(
        [
            snap(1, "tech:jdoe", "Juan Doe", "on_fire", 12, 8),
            snap(2, "tech:jdoe", "Juan Doe", "fresh", 1, 0.1),
            snap(3, "tech:asmith", "Ana Smith", "hot", 6, 5, snoozed=True),
        ]
    )
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
    rt.store.save_snapshots(
        [
            SnapshotRow(
                run_id=rid2,
                ticket_id=9,
                title="Only ticket",
                status=2,
                date_opened=NOW,
                date_mod=NOW,
                sla_due=None,
                owner_key="tech:jdoe",
                owner_name="Juan Doe",
                tier="aging",
                age_bd=3,
                stale_bd=2.5,
                sla_status="no_sla",
            )
        ]
    )
    html = client.get("/", auth=AUTH).text
    assert "1</strong> open tickets" in html
    assert "Only ticket" in html and "Ana Smith" not in html


def test_wip_empty_state(client: TestClient) -> None:
    html = client.get("/", auth=AUTH).text
    assert "No data yet" in html


# --- E3-S3: ops dashboard + ticket history --------------------------------------


def seed_sends(store: Store, rid: int) -> None:
    store.log_send(
        run_id=rid,
        kind="digest",
        channel="email",
        recipient="jdoe@x.com",
        status="dry_run",
        now=NOW,
        ticket_ids=[1, 2],
        detail="to=jdoe@x.com",
    )
    store.log_send(
        run_id=rid,
        kind="digest",
        channel="teams",
        recipient="tech:jdoe",
        status="skipped",
        now=NOW,
        ticket_ids=[1],
        detail="stub",
    )
    store.log_send(
        run_id=rid,
        kind="escalation",
        channel="email",
        recipient="boss@x.com",
        status="sent",
        now=NOW,
        ticket_ids=[1],
        detail="manager CC",
    )


def test_ops_dashboard_lists_runs_and_sends(client: TestClient, rt: Runtime) -> None:
    rid = seed_snapshots(rt.store)
    rt.store.finish_run(
        rid,
        status="ok",
        now=NOW,
        tickets_seen=3,
        digests_built=2,
        sends_attempted=3,
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

    return Runtime(
        cfg=rt.cfg, store=rt.store, renderer=rt.renderer, adapters=[], glpi_factory=factory
    )


def mock_glpi_rows(rows: list[dict[str, object]]) -> None:
    respx.post(f"{BASE}/initSession").mock(
        return_value=httpx.Response(200, json={"session_token": "s"})
    )
    respx.get(f"{BASE}/killSession").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{BASE}/listSearchOptions/Ticket").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{BASE}/search/Ticket").mock(return_value=httpx.Response(200, json={"data": rows}))


GLPI_ROW = {
    "2": 1,
    "1": "Stale thing",
    "12": 2,
    "15": "2026-06-20 09:00:00",
    "19": "2026-06-26 09:00:00",
    "18": None,
    "5": "jdoe",
    "8": None,
}


def test_snooze_roundtrip_via_forms(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    response = client.post(
        "/snooze",
        data={"ticket_id": "1", "until": "2099-12-31", "reason": "vendor"},
        auth=AUTH,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert rt.store.snooze_for(1) is not None
    html = client.get("/tickets/1", auth=AUTH).text
    assert "Snoozed until" in html and "2099-12-31" in html
    client.post("/unsnooze", data={"ticket_id": "1"}, auth=AUTH)
    assert rt.store.snooze_for(1) is None


def test_snooze_validation_errors(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    r = client.post(
        "/snooze", data={"ticket_id": "1", "until": "not-a-date"}, auth=AUTH, follow_redirects=False
    )
    assert "invalid+date" in r.headers["location"]
    r = client.post(
        "/snooze", data={"ticket_id": "1", "until": "2001-01-01"}, auth=AUTH, follow_redirects=False
    )
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


# --- E4-S1: escalation surfacing ---------------------------------------------------

from datetime import date  # noqa: E402


def test_ops_shows_escalation_streaks(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    for d in (date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)):
        rt.store.bump_red_streaks({1}, run_date=d, threshold=3, now=NOW)
    html = client.get("/ops", auth=AUTH).text
    assert "Escalation streaks" in html
    assert 'href="/tickets/1"' in html
    assert "⚠️" in html  # escalated_at stamped on day 3


def test_wip_marks_escalated_tickets(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    for d in (date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)):
        rt.store.bump_red_streaks({1}, run_date=d, threshold=3, now=NOW)
    html = client.get("/", auth=AUTH).text
    assert "manager CC" in html  # ⚠️ title on the leaderboard row


def test_ops_hides_escalations_when_none(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    assert "Escalation streaks" not in client.get("/ops", auth=AUTH).text


# --- E4-S2: rollup view + ops card ---------------------------------------------------


def test_rollup_view_renders(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    html = client.get("/rollup", auth=AUTH).text
    assert "Weekly WIP rollup" in html and "Juan Doe" in html
    assert "Subject:" in html


def test_rollup_view_empty_state(client: TestClient) -> None:
    assert "No snapshot data yet" in client.get("/rollup", auth=AUTH).text


def test_ops_rollup_card(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    rt.store.log_send(
        run_id=None, kind="rollup", channel="email", recipient="boss@x.com", status="sent", now=NOW
    )
    html = client.get("/ops", auth=AUTH).text
    assert "manager rollup" in html
    assert "last sent" in html


# --- E3-S5: WIP per-person ticket detail ---------------------------------------------


def test_wip_detail_lists_only_that_owner(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)  # jdoe: #1 on_fire age12, #2 fresh age1; asmith: #3 hot
    html = client.get("/wip/tech:jdoe", auth=AUTH).text
    assert "Juan Doe" in html
    # both of jdoe's tickets present with GLPI deep links...
    assert "id=1" in html and "id=2" in html
    # ...and the other owner's ticket is absent
    assert "id=3" not in html
    assert "Ana Smith" not in html
    # AC2: worst-first — on_fire (#1) appears before fresh (#2)
    assert html.index("id=1") < html.index("id=2")


def test_wip_detail_shows_snooze_marker(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)  # asmith's ticket #3 is snoozed
    html = client.get("/wip/tech:asmith", auth=AUTH).text
    assert "id=3" in html
    assert "💤" in html


def test_wip_dashboard_links_to_detail(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    html = client.get("/", auth=AUTH).text
    # owner name cell now links to the drill-down, url-encoded key
    assert 'href="/wip/tech%3Ajdoe"' in html


def test_wip_detail_url_encoded_owner_with_space(client: TestClient, rt: Runtime) -> None:
    rid = seed_snapshots(rt.store)
    rt.store.save_snapshots(
        [
            SnapshotRow(
                run_id=rid,
                ticket_id=99,
                title="Group ticket",
                status=2,
                date_opened=NOW,
                date_mod=NOW,
                sla_due=None,
                owner_key="group:Service Desk",
                owner_name="Service Desk",
                tier="hot",
                age_bd=4,
                stale_bd=3,
                sla_status="no_sla",
                snoozed=False,
            )
        ]
    )
    # dashboard link is encoded (space -> %20, colon -> %3A)
    home = client.get("/", auth=AUTH).text
    assert "/wip/group%3AService%20Desk" in home
    # and the encoded path resolves to that owner's ticket
    detail = client.get("/wip/group%3AService%20Desk", auth=AUTH).text
    assert "id=99" in detail and "Service Desk" in detail


def test_wip_detail_unknown_owner_empty_state(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    resp = client.get("/wip/tech:nobody", auth=AUTH)
    assert resp.status_code == 200
    assert "No open tickets" in resp.text


def test_wip_detail_no_snapshot_empty_state(client: TestClient) -> None:
    resp = client.get("/wip/tech:jdoe", auth=AUTH)
    assert resp.status_code == 200
    assert "No" in resp.text  # renders empty state, not a 500


def test_wip_detail_requires_auth(client: TestClient) -> None:
    resp = client.get("/wip/tech:jdoe")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="nagbot"'


def test_wip_detail_escapes_html_xss(client: TestClient, rt: Runtime) -> None:
    """Stored (title/owner_name) and reflected (owner_key) values must be HTML-escaped."""
    rid = seed_snapshots(rt.store)
    rt.store.save_snapshots(
        [
            SnapshotRow(
                run_id=rid,
                ticket_id=77,
                title="<img src=x onerror=alert(1)>",
                status=2,
                date_opened=NOW,
                date_mod=NOW,
                sla_due=None,
                owner_key="tech:evil",
                owner_name="Evil <b>Doe</b>",
                tier="on_fire",
                age_bd=5,
                stale_bd=3,
                sla_status="no_sla",
                snoozed=False,
            )
        ]
    )
    # stored XSS: title/owner_name escaped, not rendered as live markup
    stored = client.get("/wip/tech:evil", auth=AUTH).text
    assert "<img src=x onerror=alert(1)>" not in stored
    assert "&lt;img src=x onerror=alert(1)&gt;" in stored
    # reflected XSS: unknown owner_key echoed into the page must be escaped
    reflected = client.get('/wip/"><script>alert(1)</script>', auth=AUTH).text
    assert "<script>alert(1)</script>" not in reflected


# --- E3-S6: public embeddable WIP wallboard ------------------------------------------


def test_public_dashboard_no_auth(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    resp = client.get("/public")  # no auth header
    assert resp.status_code == 200
    body = resp.text
    assert "Juan Doe" in body  # owner name
    assert "Ticket 1" in body  # a ticket title
    assert "open tickets" in body


def test_public_dashboard_public_when_password_unset(tmp_path: Path) -> None:
    rt = make_runtime(tmp_path, password=None)
    seed_snapshots(rt.store)
    client = TestClient(create_app(rt, with_scheduler=False))
    assert client.get("/", auth=AUTH).status_code == 503  # internal gated
    assert client.get("/public").status_code == 200  # public still serves


def test_public_dashboard_is_chromeless(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    body = client.get("/public").text
    assert 'href="/ops"' not in body
    assert 'href="/preview"' not in body
    assert "/wip/" not in body  # no drill-down link into authenticated area


def test_public_dashboard_framing_allowed(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    resp = client.get("/public")
    xfo = resp.headers.get("x-frame-options", "")
    assert xfo.upper() not in ("DENY", "SAMEORIGIN")


def test_public_dashboard_autorefresh_and_cache(client: TestClient, rt: Runtime) -> None:
    seed_snapshots(rt.store)
    resp = client.get("/public")
    assert 'http-equiv="refresh"' in resp.text
    assert "max-age" in resp.headers.get("cache-control", "")


def test_public_dashboard_escapes_html(client: TestClient, rt: Runtime) -> None:
    rid = seed_snapshots(rt.store)
    rt.store.save_snapshots(
        [
            SnapshotRow(
                run_id=rid,
                ticket_id=88,
                title="<img src=x onerror=alert(1)>",
                status=2,
                date_opened=NOW,
                date_mod=NOW,
                sla_due=None,
                owner_key="tech:jdoe",
                owner_name="Juan Doe",
                tier="on_fire",
                age_bd=9,
                stale_bd=9,
                sla_status="no_sla",
                snoozed=False,
            )
        ]
    )
    body = client.get("/public").text
    assert "<img src=x onerror=alert(1)>" not in body
    assert "&lt;img src=x onerror=alert(1)&gt;" in body


def test_public_dashboard_empty_state(client: TestClient) -> None:
    resp = client.get("/public")
    assert resp.status_code == 200
    assert "wait" in resp.text.lower() or "no data" in resp.text.lower()


def test_auth_exemption_is_not_bare_prefix(client: TestClient) -> None:
    """A path merely starting with an exempt prefix (e.g. /publicfoo) must NOT be
    exempt — it requires auth like any other route (hardening, E3-S6 review)."""
    assert client.get("/public").status_code in (200,)  # exact match exempt
    assert client.get("/publicfoo").status_code == 401  # bare-prefix NOT exempt
    assert client.get("/healthzz").status_code == 401
    assert client.get("/static/style.css").status_code == 200  # true sub-path still exempt


# --- E7-S4: OpenWA inbound-ack webhook ------------------------------------------------


def _webhook_runtime(tmp_path: Path) -> Runtime:
    env = EnvSettings(
        glpi_base_url="https://glpi.example.com/apirest.php",
        glpi_app_token="app",
        glpi_user_token="user",  # noqa: S106
        dashboard_password="sekret",
        openwa_webhook_secret="whook",  # noqa: S106
        nagbot_config_path=tmp_path / "u.yaml",
        nagbot_db_path=tmp_path / "wh.db",
    )
    app_cfg = AppConfig.model_validate(
        {
            # SEC-HIGH-1: the ack webhook only records inbound while escalation is live.
            "escalation": {"enabled": True, "transparency_notice_given": True},
            "owners": {"jdoe": {"name": "Juan Doe", "whatsapp": "+593999999991"}},
        }
    )
    cfg = RuntimeConfig(env=env, app=app_cfg, dry_run=True)
    return Runtime(
        cfg=cfg,
        store=Store(cfg.env.nagbot_db_path),
        renderer=Renderer(GYE),
        adapters=[],
        glpi_factory=lambda: (_ for _ in ()).throw(AssertionError("no glpi")),
    )


def test_webhook_rejects_without_secret(tmp_path: Path) -> None:
    rt = _webhook_runtime(tmp_path)
    client = TestClient(create_app(rt, with_scheduler=False))
    assert client.post("/webhooks/openwa", json={"from": "x", "body": "y"}).status_code == 401
    assert (
        client.post(
            "/webhooks/openwa", json={"from": "x"}, headers={"X-Webhook-Secret": "wrong"}
        ).status_code
        == 401
    )


def test_webhook_roster_sender_writes_inbox(tmp_path: Path) -> None:
    rt = _webhook_runtime(tmp_path)
    client = TestClient(create_app(rt, with_scheduler=False))
    resp = client.post(
        "/webhooks/openwa",
        json={"from": "593999999991@c.us", "body": "on it"},
        headers={"X-Webhook-Secret": "whook"},
    )
    assert resp.status_code == 200
    acks = rt.store.unprocessed_acks()
    assert len(acks) == 1 and acks[0].sender == "+593999999991" and acks[0].text == "on it"


def test_webhook_non_roster_sender_ignored(tmp_path: Path) -> None:
    rt = _webhook_runtime(tmp_path)
    client = TestClient(create_app(rt, with_scheduler=False))
    resp = client.post(
        "/webhooks/openwa",
        json={"from": "999999999999@c.us", "body": "spam"},
        headers={"X-Webhook-Secret": "whook"},
    )
    assert resp.status_code == 200
    assert rt.store.unprocessed_acks() == []  # not in roster → no inbox write


def test_webhook_401_when_secret_unconfigured(tmp_path: Path) -> None:
    rt = _webhook_runtime(tmp_path)
    rt.cfg.env.openwa_webhook_secret = None  # no secret configured → path must 401, never open
    client = TestClient(create_app(rt, with_scheduler=False))
    resp = client.post(
        "/webhooks/openwa", json={"from": "593999999991@c.us", "body": "x"},
        headers={"X-Webhook-Secret": "whook"},
    )
    assert resp.status_code == 401


def test_webhook_ignores_ack_before_golive(tmp_path: Path) -> None:
    """SEC-HIGH-1: with escalation not live, an authenticated roster ack is dropped (not
    recorded) so a public webhook can't grow the inbox before go-live."""
    rt = _webhook_runtime(tmp_path)
    rt.cfg.app.escalation.transparency_notice_given = False  # not live yet
    client = TestClient(create_app(rt, with_scheduler=False))
    resp = client.post(
        "/webhooks/openwa",
        json={"from": "593999999991@c.us", "body": "on it"},
        headers={"X-Webhook-Secret": "whook"},
    )
    assert resp.status_code == 200  # still 200 (don't leak state to caller)
    assert rt.store.unprocessed_acks() == []  # but nothing recorded
