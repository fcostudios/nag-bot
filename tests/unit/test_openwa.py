"""E7-S1: OpenWA adapter — respx-mocked send_alert tests."""

import httpx
import respx

from nagbot.channels.base import EscalationAlert
from nagbot.channels.openwa import OpenWaAdapter, to_chat_id

URL = "http://openwa:8085"
ALERT = EscalationAlert(recipient="+593999999999", text="P0: payments down — #44968")


def test_chatid_normalization() -> None:
    assert to_chat_id("+593999999999") == "593999999999@c.us"
    assert to_chat_id("593999999999") == "593999999999@c.us"


@respx.mock
def test_send_alert_success() -> None:
    respx.post(f"{URL}/sendText").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    res = OpenWaAdapter(URL).send_alert(ALERT, dry_run=False)
    assert res.status == "sent"
    assert res.channel == "openwa" and res.recipient == "+593999999999"
    body = respx.calls[0].request
    assert b"593999999999@c.us" in body.content


@respx.mock
def test_dry_run_no_network() -> None:
    route = respx.post(f"{URL}/sendText").mock(return_value=httpx.Response(200))
    res = OpenWaAdapter(URL).send_alert(ALERT, dry_run=True)
    assert res.status == "dry_run"
    assert not route.called


def test_not_configured_skipped() -> None:
    res = OpenWaAdapter("").send_alert(ALERT, dry_run=False)
    assert res.status == "skipped"


def test_empty_recipient_skipped() -> None:
    res = OpenWaAdapter(URL).send_alert(EscalationAlert(recipient="", text="x"), dry_run=False)
    assert res.status == "skipped"


@respx.mock
def test_http_5xx_failed_not_raises() -> None:
    respx.post(f"{URL}/sendText").mock(return_value=httpx.Response(503, text="down"))
    res = OpenWaAdapter(URL).send_alert(ALERT, dry_run=False)
    assert res.status == "failed" and "503" in res.detail


@respx.mock
def test_transport_error_failed_not_raises() -> None:
    respx.post(f"{URL}/sendText").mock(side_effect=httpx.ConnectError("boom"))
    res = OpenWaAdapter(URL).send_alert(ALERT, dry_run=False)
    assert res.status == "failed"


@respx.mock
def test_non_json_2xx_sent() -> None:
    respx.post(f"{URL}/sendText").mock(return_value=httpx.Response(200, text="OK"))
    assert OpenWaAdapter(URL).send_alert(ALERT, dry_run=False).status == "sent"


@respx.mock
def test_success_key_absent_defaults_sent() -> None:
    respx.post(f"{URL}/sendText").mock(return_value=httpx.Response(200, json={}))
    assert OpenWaAdapter(URL).send_alert(ALERT, dry_run=False).status == "sent"


@respx.mock
def test_non_object_json_2xx_never_raises_sent() -> None:
    # a 2xx body that isn't an object ([], true, null) must NOT raise (AC5)
    respx.post(f"{URL}/sendText").mock(return_value=httpx.Response(200, json=[]))
    assert OpenWaAdapter(URL).send_alert(ALERT, dry_run=False).status == "sent"


@respx.mock
def test_openwa_error_body_failed() -> None:
    respx.post(f"{URL}/sendText").mock(
        return_value=httpx.Response(200, json={"success": False, "error": "not logged in"})
    )
    res = OpenWaAdapter(URL).send_alert(ALERT, dry_run=False)
    assert res.status == "failed"
