from datetime import datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from nagbot.channels.email import EmailAdapter
from nagbot.channels.teams import TeamsAdapter
from nagbot.channels.whatsapp import WhatsAppAdapter
from nagbot.digest.builder import build_digests
from nagbot.digest.renderer import Renderer
from nagbot.engine.aging import SlaStatus, TicketMetrics
from nagbot.engine.ownership import Owner, ScoredTicket
from nagbot.engine.tiers import Tier
from nagbot.glpi.models import Ticket

GYE = ZoneInfo("America/Guayaquil")
NOW = datetime(2026, 7, 9, 8, 0, tzinfo=GYE)
RENDERER = Renderer(GYE, glpi_web_base="https://glpi.example.com")

OWNER = Owner(
    key="tech:jdoe",
    kind="tech",
    display_name="Juan Doe",
    email="jdoe@example.com",
    whatsapp="+593999999999",
    manager_email="boss@example.com",
)


class FakeSmtp:
    """Records the SMTP conversation; usable as a context manager like smtplib.SMTP."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.messages: list[EmailMessage] = []

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *exc: object) -> None:
        self.calls.append("quit")

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login:{user}")

    def send_message(self, message: EmailMessage) -> None:
        self.calls.append("send_message")
        self.messages.append(message)


class FailingSmtp(FakeSmtp):
    def send_message(self, message: EmailMessage) -> None:
        raise ConnectionResetError("smtp gone")


def make_digest(*, escalated: bool = False, owner: Owner = OWNER):
    st = ScoredTicket(
        ticket=Ticket(
            id=1,
            title="Broken VPN",
            status=2,
            date_opened=NOW - timedelta(days=10),
            date_mod=NOW - timedelta(days=8),
            url="https://glpi.example.com/front/ticket.form.php?id=1",
        ),
        metrics=TicketMetrics(
            age_bd=8, stale_bd=7.2, sla_status=SlaStatus.NO_SLA, sla_due=None
        ),
        tier=Tier.ON_FIRE,
    )
    (digest,) = build_digests(
        {owner: [st]}, escalated_ids={1} if escalated else set(), now=NOW
    )
    return digest


def make_adapter(smtp: FakeSmtp) -> EmailAdapter:
    return EmailAdapter(
        RENDERER,
        sender="nagbot@example.com",
        smtp_factory=lambda: smtp,  # type: ignore[arg-type,return-value]
        username="bot",
        password="pw",
        rollup_recipients=["boss@example.com"],
    )


def test_live_send_builds_correct_mime() -> None:
    smtp = FakeSmtp()
    result = make_adapter(smtp).send_digest(make_digest(escalated=True), dry_run=False)
    assert result.status == "sent"
    assert smtp.calls == ["starttls", "login:bot", "send_message", "quit"]
    (msg,) = smtp.messages
    assert msg["To"] == "jdoe@example.com"
    assert msg["Cc"] == "boss@example.com"  # escalation CCs the manager
    assert msg["From"] == "nagbot@example.com"
    assert "1 open ticket" in msg["Subject"]
    parts = {p.get_content_type() for p in msg.walk()}
    assert {"text/plain", "text/html"} <= parts


def test_no_escalation_means_no_cc() -> None:
    smtp = FakeSmtp()
    make_adapter(smtp).send_digest(make_digest(escalated=False), dry_run=False)
    assert smtp.messages[0]["Cc"] is None


def test_dry_run_never_touches_smtp() -> None:
    invoked = False

    def factory() -> FakeSmtp:
        nonlocal invoked
        invoked = True
        return FakeSmtp()

    adapter = EmailAdapter(
        RENDERER, sender="nagbot@example.com", smtp_factory=factory  # type: ignore[arg-type]
    )
    result = adapter.send_digest(make_digest(escalated=True), dry_run=True)
    assert result.status == "dry_run"
    assert "to=jdoe@example.com" in result.detail and "cc=boss@example.com" in result.detail
    assert invoked is False


def test_owner_without_email_is_skipped() -> None:
    owner = Owner(key="tech:noemail", kind="tech", display_name="No Mail")
    result = make_adapter(FakeSmtp()).send_digest(make_digest(owner=owner), dry_run=False)
    assert result.status == "skipped"


def test_smtp_failure_returns_failed_not_raises() -> None:
    result = make_adapter(FailingSmtp()).send_digest(make_digest(), dry_run=False)
    assert result.status == "failed"
    assert "smtp gone" in result.detail


def test_teams_stub_renders_card() -> None:
    adapter = TeamsAdapter(RENDERER)
    assert adapter.send_digest(make_digest(), dry_run=True).status == "dry_run"
    assert adapter.send_digest(make_digest(), dry_run=False).status == "skipped"


def test_whatsapp_stub_payload_and_optout() -> None:
    adapter = WhatsAppAdapter(RENDERER)
    payload = adapter.build_payload(make_digest())
    texts = [p["text"] for p in payload["template"]["components"][0]["parameters"]]
    assert texts == ["Juan Doe", "1", "0", "#1", "8"]
    assert adapter.send_digest(make_digest(), dry_run=True).status == "dry_run"
    no_number = Owner(key="tech:x", kind="tech", display_name="X", email="x@x.com")
    assert adapter.send_digest(make_digest(owner=no_number), dry_run=True).status == "skipped"


# --- E5-S1: Teams live POST -----------------------------------------------------

import json  # noqa: E402

import httpx  # noqa: E402
import respx  # noqa: E402

WEBHOOK = "https://prod-1.westus.logic.azure.com/workflows/abc/triggers/manual/paths/invoke"


def teams_adapter() -> TeamsAdapter:
    return TeamsAdapter(RENDERER, WEBHOOK, sleep=lambda _s: None)


@respx.mock
def test_teams_live_posts_envelope() -> None:
    route = respx.post(WEBHOOK).mock(return_value=httpx.Response(202))
    result = teams_adapter().send_digest(make_digest(), dry_run=False)
    assert result.status == "sent"
    body = json.loads(route.calls[0].request.content)
    assert body["type"] == "message"
    (attachment,) = body["attachments"]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert attachment["content"]["type"] == "AdaptiveCard"


@respx.mock
def test_teams_retries_on_429_then_succeeds() -> None:
    respx.post(WEBHOOK).mock(side_effect=[httpx.Response(429), httpx.Response(202)])
    assert teams_adapter().send_digest(make_digest(), dry_run=False).status == "sent"


@respx.mock
def test_teams_permanent_400_fails_with_detail() -> None:
    respx.post(WEBHOOK).mock(return_value=httpx.Response(400, text="bad trigger schema"))
    result = teams_adapter().send_digest(make_digest(), dry_run=False)
    assert result.status == "failed"
    assert "bad trigger schema" in result.detail


@respx.mock
def test_teams_gives_up_after_retries() -> None:
    respx.post(WEBHOOK).mock(return_value=httpx.Response(503))
    result = teams_adapter().send_digest(make_digest(), dry_run=False)
    assert result.status == "failed"
    assert "gave up after 3 attempts" in result.detail


@respx.mock
def test_teams_dry_run_no_network() -> None:
    route = respx.post(WEBHOOK).mock(return_value=httpx.Response(202))
    result = teams_adapter().send_digest(make_digest(), dry_run=True)
    assert result.status == "dry_run"
    assert not route.called


def test_teams_without_webhook_skips() -> None:
    adapter = TeamsAdapter(RENDERER, "")
    assert adapter.send_digest(make_digest(), dry_run=False).status == "skipped"


@respx.mock
def test_teams_rollup_card_posts() -> None:
    from nagbot.digest.builder import build_rollup
    from nagbot.store.repo import SnapshotRow

    route = respx.post(WEBHOOK).mock(return_value=httpx.Response(202))
    snap = SnapshotRow(
        run_id=1, ticket_id=1, title="T1", status=2, date_opened=None, date_mod=None,
        sla_due=None, owner_key="tech:jdoe", owner_name="Juan Doe", tier="on_fire",
        age_bd=12, stale_bd=8, sla_status="no_sla",
    )
    rollup = build_rollup([snap], now=NOW)
    result = teams_adapter().send_rollup(rollup, dry_run=False)
    assert result.status == "sent"
    body = json.loads(route.calls[0].request.content)
    assert "Weekly WIP rollup" in json.dumps(body)


# --- E5-S2: mentions + deep links ---------------------------------------------------

def test_card_mentions_owner_with_teams_id() -> None:
    owner = Owner(
        key="tech:jdoe", kind="tech", display_name="Juan Doe",
        email="jdoe@example.com", teams_id="jdoe@corp.example.com",
    )
    card = RENDERER.teams_card(make_digest(owner=owner))
    assert "<at>Juan Doe</at>" in card["body"][1]["text"]
    (entity,) = card["msteams"]["entities"]
    assert entity["type"] == "mention"
    assert entity["mentioned"] == {"id": "jdoe@corp.example.com", "name": "Juan Doe"}


def test_card_without_teams_id_has_no_mention() -> None:
    owner = Owner(key="tech:x", kind="tech", display_name="No Teams", email="x@x.com")
    card = RENDERER.teams_card(make_digest(owner=owner))
    assert "msteams" not in card
    assert "<at>" not in card["body"][1]["text"]
    assert "No Teams" in card["body"][1]["text"]


def test_card_rows_deep_link_to_glpi() -> None:
    card = RENDERER.teams_card(make_digest())
    fact = card["body"][2]["facts"][0]
    assert "https://glpi.example.com/front/ticket.form.php?id=1" in fact["value"]


# --- E6-S1: WhatsApp Cloud API live send ---------------------------------------------

WA_ENDPOINT = "https://graph.facebook.com/v20.0/12345/messages"


def whatsapp_adapter(**kw: object) -> WhatsAppAdapter:
    defaults: dict[str, object] = {
        "token": "wa-token", "phone_number_id": "12345", "template_name": "nag_digest",
    }
    defaults.update(kw)
    return WhatsAppAdapter(RENDERER, **defaults)  # type: ignore[arg-type]


@respx.mock
def test_whatsapp_live_send_success() -> None:
    route = respx.post(WA_ENDPOINT).mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.XYZ"}]})
    )
    result = whatsapp_adapter().send_digest(make_digest(), dry_run=False)
    assert result.status == "sent"
    assert "wamid.XYZ" in result.detail
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer wa-token"
    body = json.loads(request.content)
    assert body["to"] == "+593999999999"
    assert body["template"]["name"] == "nag_digest"


@respx.mock
def test_whatsapp_400_fails_with_detail() -> None:
    respx.post(WA_ENDPOINT).mock(
        return_value=httpx.Response(400, json={"error": {"message": "param mismatch"}})
    )
    result = whatsapp_adapter().send_digest(make_digest(), dry_run=False)
    assert result.status == "failed"
    assert "param mismatch" in result.detail


@respx.mock
def test_whatsapp_401_fails() -> None:
    respx.post(WA_ENDPOINT).mock(return_value=httpx.Response(401, text="bad token"))
    result = whatsapp_adapter().send_digest(make_digest(), dry_run=False)
    assert result.status == "failed" and "401" in result.detail


@respx.mock
def test_whatsapp_dry_run_no_network() -> None:
    route = respx.post(WA_ENDPOINT).mock(return_value=httpx.Response(200))
    result = whatsapp_adapter().send_digest(make_digest(), dry_run=True)
    assert result.status == "dry_run"
    assert not route.called


def test_whatsapp_unconfigured_skips_live() -> None:
    adapter = WhatsAppAdapter(RENDERER)  # no creds
    result = adapter.send_digest(make_digest(), dry_run=False)
    assert result.status == "skipped"
    assert "not configured" in result.detail


def test_e164_validation() -> None:
    import pytest

    from nagbot.config import OwnerCfg

    assert OwnerCfg(name="x", whatsapp="+593999999999").whatsapp == "+593999999999"
    with pytest.raises(ValueError, match="E.164"):
        OwnerCfg(name="x", whatsapp="0999999999")
    with pytest.raises(ValueError, match="E.164"):
        OwnerCfg(name="x", whatsapp="+0999")
