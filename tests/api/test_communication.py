"""
API tests for the Communication module: a real send (through the same
packages.email/sms/whatsapp clients every other module uses) that also
writes an audit-log row. The underlying provider calls are monkeypatched
here purely to avoid hitting real SMTP/SMS/WhatsApp providers in CI —
the module's own code path (send -> log -> list) is exercised for real.
"""

import pytest

pytestmark = pytest.mark.api


async def test_successful_email_send_is_logged(client, auth_headers, monkeypatch):
    import modules.communication.service as service_module

    async def fake_send(*args, **kwargs):
        return True

    monkeypatch.setattr(service_module.email_service, "send", fake_send)

    response = await client.post(
        "/api/v1/communication/send",
        json={
            "channel": "email",
            "recipient": "student@example.com",
            "subject": "Welcome",
            "body": "Thanks for enrolling.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "sent"
    assert body["channel"] == "email"
    assert body["error_message"] is None


async def test_failed_sms_send_is_logged_with_error(client, auth_headers, monkeypatch):
    import modules.communication.service as service_module

    async def fake_send(*args, **kwargs):
        return False

    monkeypatch.setattr(service_module.sms_service, "send", fake_send)

    response = await client.post(
        "/api/v1/communication/send",
        json={"channel": "sms", "recipient": "+919876543210", "body": "Reminder."},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] is not None


async def test_email_requires_subject(client, auth_headers):
    response = await client.post(
        "/api/v1/communication/send",
        json={"channel": "email", "recipient": "student@example.com", "body": "No subject."},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_staff_without_permission_cannot_send(client, staff_headers):
    response = await client.post(
        "/api/v1/communication/send",
        json={"channel": "sms", "recipient": "+919876543210", "body": "Hi."},
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_list_logs_filters_by_channel_and_status(client, auth_headers, monkeypatch):
    import modules.communication.service as service_module

    async def fake_send_ok(*args, **kwargs):
        return True

    async def fake_send_fail(*args, **kwargs):
        return False

    monkeypatch.setattr(service_module.whatsapp_service, "send_text", fake_send_ok)
    await client.post(
        "/api/v1/communication/send",
        json={"channel": "whatsapp", "recipient": "+919876543210", "body": "Hi there."},
        headers=auth_headers,
    )

    monkeypatch.setattr(service_module.sms_service, "send", fake_send_fail)
    await client.post(
        "/api/v1/communication/send",
        json={"channel": "sms", "recipient": "+919876543211", "body": "Reminder."},
        headers=auth_headers,
    )

    whatsapp_response = await client.get(
        "/api/v1/communication/logs", params={"channel": "whatsapp"}, headers=auth_headers
    )
    assert whatsapp_response.status_code == 200
    assert all(item["channel"] == "whatsapp" for item in whatsapp_response.json()["items"])

    failed_response = await client.get(
        "/api/v1/communication/logs", params={"status": "failed"}, headers=auth_headers
    )
    assert failed_response.status_code == 200
    assert all(item["status"] == "failed" for item in failed_response.json()["items"])
    assert len(failed_response.json()["items"]) >= 1
