"""The live email adapter — SMTP with STARTTLS, manager CC on escalation.

Dry-run still renders everything (template errors must surface) but never
touches the network: the smtp_factory is not even invoked.
"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable
from email.message import EmailMessage

from nagbot.channels.base import SendResult
from nagbot.config import RuntimeConfig
from nagbot.digest.builder import Digest, Rollup
from nagbot.digest.renderer import Renderer

logger = logging.getLogger(__name__)

SmtpFactory = Callable[[], smtplib.SMTP]


class EmailAdapter:
    name = "email"

    def __init__(
        self,
        renderer: Renderer,
        *,
        sender: str,
        smtp_factory: SmtpFactory,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = True,
        rollup_recipients: list[str] | None = None,
    ) -> None:
        self.renderer = renderer
        self.sender = sender
        self.smtp_factory = smtp_factory
        self.username = username
        self.password = password
        self.starttls = starttls
        self.rollup_recipients = rollup_recipients or []

    @classmethod
    def from_config(cls, cfg: RuntimeConfig, renderer: Renderer) -> EmailAdapter:
        env = cfg.env
        host, port = env.smtp_host or "", env.smtp_port

        def factory() -> smtplib.SMTP:
            return smtplib.SMTP(host, port, timeout=30)

        return cls(
            renderer,
            sender=env.smtp_from or "",
            smtp_factory=factory,
            username=env.smtp_username,
            password=env.smtp_password.get_secret_value() if env.smtp_password else None,
            starttls=env.smtp_starttls,
            rollup_recipients=cfg.app.fallback.rollup_recipients,
        )

    # -- digest ---------------------------------------------------------------

    def send_digest(self, digest: Digest, *, dry_run: bool) -> SendResult:
        recipient = digest.owner.email
        if not recipient:
            return SendResult(
                self.name,
                digest.owner.key,
                "skipped",
                detail=f"owner {digest.owner.display_name!r} has no email configured",
            )
        cc = digest.owner.manager_email if digest.escalated else None
        subject = self.renderer.email_subject(digest)
        html = self.renderer.email_html(digest)
        text = self.renderer.email_text(digest)
        detail = f"to={recipient}" + (f" cc={cc}" if cc else "") + f" subject={subject}"
        if dry_run:
            return SendResult(self.name, recipient, "dry_run", detail=detail, cc=cc)
        message = self._build_message(subject, recipient, cc, text, html)
        return self._deliver(message, recipient, cc, detail)

    # -- rollup (E4 uses this; plumbing complete now) ---------------------------

    def send_rollup(self, rollup: Rollup, *, dry_run: bool) -> SendResult:
        if not self.rollup_recipients:
            return SendResult(self.name, "-", "skipped", detail="no rollup_recipients configured")
        recipient = ", ".join(self.rollup_recipients)
        subject = self.renderer.rollup_subject(rollup)
        html = self.renderer.rollup_html(rollup)
        detail = f"to={recipient} subject={subject}"
        if dry_run:
            return SendResult(self.name, recipient, "dry_run", detail=detail)
        message = self._build_message(subject, recipient, None, "See HTML version.", html)
        return self._deliver(message, recipient, None, detail)

    # -- internals -----------------------------------------------------------------

    def _build_message(
        self, subject: str, to: str, cc: str | None, text: str, html: str
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        if cc:
            message["Cc"] = cc
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        return message

    def _deliver(
        self, message: EmailMessage, recipient: str, cc: str | None, detail: str
    ) -> SendResult:
        try:
            with self.smtp_factory() as smtp:
                if self.starttls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
        except Exception as exc:  # noqa: BLE001 - one owner's failure must not kill the run
            logger.exception("email delivery to %s failed", recipient)
            return SendResult(self.name, recipient, "failed", detail=f"{detail} error={exc}", cc=cc)
        return SendResult(self.name, recipient, "sent", detail=detail, cc=cc)
