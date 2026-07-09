"""Single Jinja2 environment for every rendered surface (email, Teams card, rollup)."""

from __future__ import annotations

import json
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader

from nagbot.digest.builder import Digest, Rollup
from nagbot.engine.tiers import TIER_EMOJI, TIER_LABEL, Tier


class Renderer:
    def __init__(self, tz: ZoneInfo, glpi_web_base: str = "") -> None:
        self.tz = tz
        self.env = Environment(
            loader=PackageLoader("nagbot.digest", "templates"),
            # autoescape HTML templates only; the Teams card template emits JSON
            autoescape=lambda name: bool(name and name.endswith(".html.j2")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["localdt"] = self._localdt
        self.env.filters["days"] = self._days
        self.env.globals.update(
            tier_emoji=TIER_EMOJI,
            tier_label=TIER_LABEL,
            Tier=Tier,
            glpi_web_base=glpi_web_base,
        )

    def _localdt(self, dt: Any) -> str:
        if dt is None:
            return "—"
        return dt.astimezone(self.tz).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _days(value: float) -> str:
        """1 decimal, but drop '.0' — reads as '12d' / '2.5d'."""
        rounded = round(value, 1)
        text = f"{rounded:.1f}".removesuffix(".0")
        return f"{text}d"

    # -- digest (per owner) -----------------------------------------------------

    def email_subject(self, digest: Digest) -> str:
        n = len(digest.tickets)
        subject = f"⏰ {n} open ticket{'s' if n != 1 else ''}"
        red = digest.counts[Tier.ON_FIRE]
        if digest.breached_count:
            subject += f" — {digest.breached_count} OVERDUE"
        elif red:
            subject += f" — {red} on fire"
        if digest.oldest is not None:
            subject += f", oldest {self._days(digest.oldest.metrics.age_bd)}"
        return subject + " (please act)"

    def email_html(self, digest: Digest) -> str:
        return self.env.get_template("email_digest.html.j2").render(d=digest)

    def email_text(self, digest: Digest) -> str:
        return self.env.get_template("digest.txt.j2").render(
            d=digest, subject=self.email_subject(digest)
        )

    def teams_card(self, digest: Digest) -> dict[str, Any]:
        raw = self.env.get_template("teams_card.json.j2").render(
            d=digest, subject=self.email_subject(digest)
        )
        card: dict[str, Any] = json.loads(raw)  # invalid JSON fails loudly here
        return card

    # -- rollup (managers) ---------------------------------------------------------

    def rollup_html(self, rollup: Rollup) -> str:
        return self.env.get_template("manager_rollup.html.j2").render(r=rollup)

    def rollup_subject(self, rollup: Rollup) -> str:
        red = rollup.distribution[Tier.ON_FIRE]
        return f"📊 Weekly WIP rollup — {rollup.total_open} open, {red} on fire"
