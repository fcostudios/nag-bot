from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from nagbot.glpi.client import GlpiClient, GlpiError
from nagbot.glpi.fields import FieldMap

BASE = "https://glpi.example.com/apirest.php"
GYE = ZoneInfo("America/Guayaquil")


def make_client(**kwargs: object) -> GlpiClient:
    return GlpiClient(
        BASE,
        "app-token",
        "user-token",
        server_timezone=GYE,
        sleep=lambda _s: None,
        **kwargs,  # type: ignore[arg-type]
    )


def row(ticket_id: int, tech: object = "jdoe", group: object = "Networking") -> dict[str, object]:
    return {
        "2": ticket_id,
        "1": f"Ticket {ticket_id}",
        "12": 2,
        "15": "2026-07-01 09:00:00",
        "19": "2026-07-07 15:30:00",
        "18": "2026-07-10 09:00:00",
        "5": tech,
        "8": group,
    }


def mock_init_session(version: str = "10.0.15") -> None:
    respx.post(f"{BASE}/initSession").mock(
        return_value=httpx.Response(
            200, json={"session_token": "sess-1"}, headers={"X-GLPI-Version": version}
        )
    )
    respx.get(f"{BASE}/killSession").mock(return_value=httpx.Response(200, json={}))


@respx.mock
def test_session_lifecycle_headers() -> None:
    mock_init_session()
    search = respx.get(f"{BASE}/search/Ticket").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    with make_client() as client:
        client.search_open_tickets(FieldMap())
    init_req = respx.calls[0].request
    assert init_req.headers["App-Token"] == "app-token"
    assert init_req.headers["Authorization"] == "user_token user-token"
    assert search.calls[0].request.headers["Session-Token"] == "sess-1"
    assert respx.calls[-1].request.url.path.endswith("/killSession")


@respx.mock
def test_pagination_spans_pages() -> None:
    mock_init_session()
    pages = [
        httpx.Response(206, json={"data": [row(1), row(2)]}, headers={"Content-Range": "0-1/3"}),
        httpx.Response(200, json={"data": [row(3)]}),
    ]
    respx.get(f"{BASE}/search/Ticket").mock(side_effect=pages)
    with make_client(page_size=2) as client:
        tickets = client.search_open_tickets(FieldMap())
    assert [t.id for t in tickets] == [1, 2, 3]
    second = respx.calls[-2].request  # last search call before killSession
    assert "range=2-3" in str(second.url)


@respx.mock
def test_retry_on_500_then_success() -> None:
    mock_init_session()
    respx.get(f"{BASE}/search/Ticket").mock(
        side_effect=[
            httpx.Response(500, text="boom"),
            httpx.Response(200, json={"data": [row(7)]}),
        ]
    )
    with make_client() as client:
        tickets = client.search_open_tickets(FieldMap())
    assert [t.id for t in tickets] == [7]


@respx.mock
def test_retries_exhausted_raises() -> None:
    mock_init_session()
    respx.get(f"{BASE}/search/Ticket").mock(return_value=httpx.Response(503, text="down"))
    with make_client() as client, pytest.raises(GlpiError, match="after 3 attempts"):
        client.search_open_tickets(FieldMap())


@respx.mock
def test_reauth_on_invalid_session_token() -> None:
    respx.post(f"{BASE}/initSession").mock(
        side_effect=[
            httpx.Response(200, json={"session_token": "sess-1"}),
            httpx.Response(200, json={"session_token": "sess-2"}),
        ]
    )
    respx.get(f"{BASE}/killSession").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{BASE}/search/Ticket").mock(
        side_effect=[
            httpx.Response(401, json=["ERROR_SESSION_TOKEN_INVALID", "session expired"]),
            httpx.Response(200, json={"data": [row(9)]}),
        ]
    )
    with make_client() as client:
        tickets = client.search_open_tickets(FieldMap())
    assert [t.id for t in tickets] == [9]
    replay = [c.request for c in respx.calls if c.request.url.path.endswith("/search/Ticket")][-1]
    assert replay.headers["Session-Token"] == "sess-2"


@respx.mock
def test_row_normalization() -> None:
    mock_init_session()
    respx.get(f"{BASE}/search/Ticket").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    row(1, tech=["jdoe", "asmith"]),
                    row(2, tech="jdoe$#$asmith", group=None),
                    {**row(3), "18": None, "1": None},
                ]
            },
        )
    )
    with make_client() as client:
        t1, t2, t3 = client.search_open_tickets(FieldMap())
    # multi-assignee: list form and $#$ form both split
    assert t1.tech_names == ["jdoe", "asmith"]
    assert t2.tech_names == ["jdoe", "asmith"]
    assert t2.group_names == []
    # naive GLPI datetime in America/Guayaquil (UTC-5) -> aware UTC
    assert t1.date_opened.isoformat() == "2026-07-01T14:00:00+00:00"
    assert t1.time_to_resolve is not None
    assert t3.time_to_resolve is None
    assert t3.title == "(untitled #3)"
    assert t1.url == "https://glpi.example.com/front/ticket.form.php?id=1"


@respx.mock
def test_glpi11_version_warning(caplog: pytest.LogCaptureFixture) -> None:
    mock_init_session(version="11.0.2")
    respx.get(f"{BASE}/search/Ticket").mock(return_value=httpx.Response(200, json={"data": []}))
    with caplog.at_level("WARNING"), make_client() as client:
        client.search_open_tickets(FieldMap())
    assert any("deprecated in GLPI 11+" in r.message for r in caplog.records)


@respx.mock
def test_get_ticket_single_fetch() -> None:
    mock_init_session()
    respx.get(f"{BASE}/search/Ticket").mock(
        return_value=httpx.Response(200, json={"data": [row(7)]})
    )
    with make_client() as client:
        t = client.get_ticket(7, FieldMap())
    assert t is not None and t.id == 7


@respx.mock
def test_get_ticket_missing_returns_none() -> None:
    mock_init_session()
    respx.get(f"{BASE}/search/Ticket").mock(return_value=httpx.Response(200, json={"data": []}))
    with make_client() as client:
        assert client.get_ticket(999, FieldMap()) is None
