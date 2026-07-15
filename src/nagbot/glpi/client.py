"""GLPI REST API client (apirest.php): session lifecycle, search, pagination, retries.

Read-only by design. One session per nag run — the client is a context manager.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from types import TracebackType
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from nagbot.glpi.fields import FieldMap
from nagbot.glpi.models import Ticket

logger = logging.getLogger(__name__)

RETRIABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
CONTENT_RANGE_RE = re.compile(r"(\d+)-(\d+)/(\d+)")


class GlpiError(Exception):
    """Raised when GLPI keeps failing after retries or returns an unusable payload."""


class GlpiClient:
    def __init__(
        self,
        base_url: str,
        app_token: str,
        user_token: str,
        *,
        http: httpx.Client | None = None,
        page_size: int = 100,
        server_timezone: ZoneInfo,
        web_base: str = "",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_token = app_token
        self.user_token = user_token
        self.page_size = page_size
        self.server_tz = server_timezone
        self.web_base = web_base or self.base_url.removesuffix("/apirest.php")
        self._sleep = sleep
        self._http = http or httpx.Client(timeout=30)
        self._owns_http = http is None
        self.session_token: str | None = None
        self.server_version: str | None = None

    # -- session lifecycle ---------------------------------------------------

    def __enter__(self) -> GlpiClient:
        self._init_session()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if self.session_token:
                self._request("GET", "/killSession")
        except Exception:  # noqa: BLE001 - best-effort teardown
            logger.debug("killSession failed (ignored)", exc_info=True)
        finally:
            self.session_token = None
            if self._owns_http:
                self._http.close()

    def _init_session(self) -> None:
        resp = self._raw_request(
            "POST",
            "/initSession",
            headers={
                "App-Token": self.app_token,
                "Authorization": f"user_token {self.user_token}",
            },
            retry=True,
        )
        data = resp.json()
        if not isinstance(data, dict) or "session_token" not in data:
            raise GlpiError(f"initSession: unexpected response {data!r}")
        self.session_token = data["session_token"]
        self.server_version = resp.headers.get("X-GLPI-Version") or None
        self._warn_if_deprecated_api()

    def _warn_if_deprecated_api(self) -> None:
        if self.server_version and self.server_version.split(".")[0].isdigit():
            major = int(self.server_version.split(".")[0])
            if major >= 11:
                logger.warning(
                    "GLPI %s detected: apirest.php is deprecated in GLPI 11+; "
                    "plan the migration to the high-level API (see docs/prd.md R1)",
                    self.server_version,
                )

    # -- transport with retry / re-auth ---------------------------------------

    def _raw_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry: bool = True,
    ) -> httpx.Response:
        last_error: Exception | None = None
        attempts = MAX_ATTEMPTS if retry else 1
        for attempt in range(1, attempts + 1):
            try:
                resp = self._http.request(
                    method, f"{self.base_url}{path}", params=params, headers=headers
                )
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning("GLPI %s %s transport error (attempt %d)", method, path, attempt)
            else:
                if resp.status_code not in RETRIABLE_STATUS:
                    return resp
                last_error = GlpiError(f"{method} {path} -> HTTP {resp.status_code}")
                logger.warning(
                    "GLPI %s %s -> %d (attempt %d)", method, path, resp.status_code, attempt
                )
            if attempt < attempts:
                self._sleep(2 ** (attempt - 1))
        raise GlpiError(f"GLPI request failed after {attempts} attempts: {last_error}")

    def _request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Authenticated request; re-authenticates once on an invalidated session."""
        if not self.session_token:
            raise GlpiError("no session — use GlpiClient as a context manager")
        headers = {"App-Token": self.app_token, "Session-Token": self.session_token}
        resp = self._raw_request(method, path, params=params, headers=headers)
        if resp.status_code == 401 and "ERROR_SESSION_TOKEN_INVALID" in resp.text:
            logger.info("GLPI session expired; re-authenticating once")
            self._init_session()
            headers["Session-Token"] = self.session_token or ""
            resp = self._raw_request(method, path, params=params, headers=headers)
        if resp.status_code >= 400 and resp.status_code != 206:
            raise GlpiError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
        return resp

    # -- API calls -------------------------------------------------------------

    def list_search_options(self, itemtype: str = "Ticket") -> dict[str, Any]:
        resp = self._request("GET", f"/listSearchOptions/{itemtype}")
        data = resp.json()
        if not isinstance(data, dict):
            raise GlpiError(f"listSearchOptions: unexpected response {type(data)}")
        return data

    def get_ticket(self, ticket_id: int, field_map: FieldMap) -> Ticket | None:
        """Single-ticket re-fetch (E7-S4 / AD-6). Filters to OPEN (`notold`) so a ticket
        that was solved/closed since the batch fetch returns None — the re-validation must
        catch a *resolution*, not just a priority downgrade."""
        params: dict[str, Any] = {
            "criteria[0][field]": 2,  # id
            "criteria[0][searchtype]": "equals",
            "criteria[0][value]": ticket_id,
            "criteria[1][link]": "AND",
            "criteria[1][field]": 12,  # status
            "criteria[1][searchtype]": "equals",
            "criteria[1][value]": "notold",
            **field_map.forcedisplay_params(),
            "range": "0-0",
        }
        resp = self._request("GET", "/search/Ticket", params=params)
        payload = resp.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not rows:
            return None
        try:
            return field_map.to_ticket(rows[0], server_tz=self.server_tz, web_base=self.web_base)
        except (ValueError, KeyError) as exc:
            logger.warning("get_ticket %d: unparseable row %r: %s", ticket_id, rows[0], exc)
            return None

    def search_open_tickets(self, field_map: FieldMap) -> list[Ticket]:
        """All tickets with status 'notold' (not solved/closed), across all pages."""
        base_params: dict[str, Any] = {
            "criteria[0][field]": 12,
            "criteria[0][searchtype]": "equals",
            "criteria[0][value]": "notold",
            **field_map.forcedisplay_params(),
        }
        tickets: list[Ticket] = []
        start = 0
        while True:
            params = {**base_params, "range": f"{start}-{start + self.page_size - 1}"}
            resp = self._request("GET", "/search/Ticket", params=params)
            payload = resp.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            for row in rows:
                try:
                    tickets.append(
                        field_map.to_ticket(row, server_tz=self.server_tz, web_base=self.web_base)
                    )
                except (ValueError, KeyError) as exc:
                    logger.warning("skipping unparseable ticket row %r: %s", row, exc)
            if resp.status_code != 206:
                break
            match = CONTENT_RANGE_RE.search(resp.headers.get("Content-Range", ""))
            if not match:
                break
            end, total = int(match.group(2)), int(match.group(3))
            if end + 1 >= total:
                break
            start = end + 1
        return tickets
