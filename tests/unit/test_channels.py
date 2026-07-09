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
