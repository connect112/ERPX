"""
Unit tests for the SMS (Fast2SMS) and WhatsApp (Meta Cloud API) clients —
pure request-construction logic, no database. Network calls are
intercepted with `httpx.MockTransport` so these verify exactly what our
code sends without depending on (or paying for) a real provider account.
"""

import httpx
import pytest

from app.core.exceptions import ServiceUnavailableError
from packages.sms.client import SMSService
from packages.whatsapp.client import WhatsAppService

pytestmark = pytest.mark.unit


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    class _FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


# ---- SMS ----


async def test_sms_send_raises_when_not_configured():
    service = SMSService()
    service.api_key = ""
    with pytest.raises(ServiceUnavailableError):
        await service.send("9876543210", "hello")


async def test_sms_send_builds_correct_request_and_returns_true(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"return": True, "request_id": "abc123"})

    _patch_transport(monkeypatch, handler)

    service = SMSService()
    service.api_key = "test-key"
    service.sender_id = "ERPXTX"

    result = await service.send("+91 98765-43210", "Your OTP is 123456")

    assert result is True
    assert captured["url"] == "https://www.fast2sms.com/dev/bulkV2"
    assert captured["headers"]["authorization"] == "test-key"
    assert "numbers=9876543210" in captured["body"]
    assert "sender_id=ERPXTX" in captured["body"]


async def test_sms_send_returns_false_on_provider_rejection(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return": False, "message": "Invalid sender_id"})

    _patch_transport(monkeypatch, handler)

    service = SMSService()
    service.api_key = "test-key"

    result = await service.send("9876543210", "hello")
    assert result is False


async def test_sms_send_returns_false_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_transport(monkeypatch, handler)

    service = SMSService()
    service.api_key = "test-key"

    result = await service.send("9876543210", "hello")
    assert result is False


# ---- WhatsApp ----


async def test_whatsapp_send_text_raises_when_not_configured():
    service = WhatsAppService()
    service.api_key = ""
    service.phone_number_id = ""
    with pytest.raises(ServiceUnavailableError):
        await service.send_text("+919876543210", "hello")


async def test_whatsapp_send_text_builds_correct_request(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})

    _patch_transport(monkeypatch, handler)

    service = WhatsAppService()
    service.api_key = "test-token"
    service.phone_number_id = "1234567890"

    result = await service.send_text("+91 98765 43210", "Reminder: your call is at 5 PM")

    assert result is True
    assert captured["url"] == "https://graph.facebook.com/v18.0/1234567890/messages"
    assert captured["headers"]["authorization"] == "Bearer test-token"
    assert captured["payload"]["to"] == "+919876543210"
    assert captured["payload"]["type"] == "text"
    assert captured["payload"]["text"]["body"] == "Reminder: your call is at 5 PM"


async def test_whatsapp_send_template_builds_correct_request(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})

    _patch_transport(monkeypatch, handler)

    service = WhatsAppService()
    service.api_key = "test-token"
    service.phone_number_id = "1234567890"

    result = await service.send_template(
        "+919876543210", "followup_reminder", "en", ["Jordan", "5 PM"]
    )

    assert result is True
    template = captured["payload"]["template"]
    assert template["name"] == "followup_reminder"
    assert template["language"]["code"] == "en"
    assert [p["text"] for p in template["components"][0]["parameters"]] == ["Jordan", "5 PM"]


async def test_whatsapp_send_returns_false_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid token"}})

    _patch_transport(monkeypatch, handler)

    service = WhatsAppService()
    service.api_key = "bad-token"
    service.phone_number_id = "1234567890"

    result = await service.send_text("9876543210", "hello")
    assert result is False
