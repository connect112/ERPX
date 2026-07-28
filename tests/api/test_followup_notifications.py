"""
API tests verifying that scheduling a CRM follow-up dispatches a real
WhatsApp/SMS reminder task — not just that the follow-up row gets
created. The autouse `_no_background_email` fixture normally no-ops
`.delay()` for these tasks; each test here overrides that with a
capturing spy so it can assert the dispatch actually happened with the
right arguments.
"""

import pytest

pytestmark = pytest.mark.api


async def _create_lead(client, auth_headers, phone: str | None = "+91 98765 43210"):
    payload = {
        "full_name": "Notify Lead",
        "email": "notify.lead@example.com",
        "source": "website",
    }
    if phone:
        payload["phone"] = phone
    response = await client.post("/api/v1/crm/leads", json=payload, headers=auth_headers)
    assert response.status_code == 201
    return response.json()


async def test_whatsapp_followup_dispatches_reminder(client, auth_headers, monkeypatch):
    from modules.crm.followups import tasks as followup_tasks

    calls = []
    monkeypatch.setattr(
        followup_tasks.send_followup_whatsapp_task, "delay", lambda *a: calls.append(a)
    )

    lead = await _create_lead(client, auth_headers)
    response = await client.post(
        f"/api/v1/crm/leads/{lead['id']}/followups",
        json={"follow_up_type": "whatsapp", "scheduled_at": "2026-08-01T10:00:00Z"},
        headers=auth_headers,
    )
    assert response.status_code == 201

    assert len(calls) == 1
    phone, name, scheduled_at_iso = calls[0]
    assert phone == "+91 98765 43210"
    assert name == "Notify Lead"
    assert "2026-08-01" in scheduled_at_iso


async def test_sms_followup_dispatches_reminder(client, auth_headers, monkeypatch):
    from modules.crm.followups import tasks as followup_tasks

    calls = []
    monkeypatch.setattr(followup_tasks.send_followup_sms_task, "delay", lambda *a: calls.append(a))

    lead = await _create_lead(client, auth_headers)
    response = await client.post(
        f"/api/v1/crm/leads/{lead['id']}/followups",
        json={"follow_up_type": "sms", "scheduled_at": "2026-08-01T10:00:00Z"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert len(calls) == 1


async def test_call_followup_does_not_dispatch_any_reminder(client, auth_headers, monkeypatch):
    from modules.crm.followups import tasks as followup_tasks

    whatsapp_calls = []
    sms_calls = []
    monkeypatch.setattr(
        followup_tasks.send_followup_whatsapp_task, "delay", lambda *a: whatsapp_calls.append(a)
    )
    monkeypatch.setattr(followup_tasks.send_followup_sms_task, "delay", lambda *a: sms_calls.append(a))

    lead = await _create_lead(client, auth_headers)
    response = await client.post(
        f"/api/v1/crm/leads/{lead['id']}/followups",
        json={"follow_up_type": "call", "scheduled_at": "2026-08-01T10:00:00Z"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert whatsapp_calls == []
    assert sms_calls == []


async def test_followup_without_lead_phone_does_not_dispatch(client, auth_headers, monkeypatch):
    from modules.crm.followups import tasks as followup_tasks

    calls = []
    monkeypatch.setattr(
        followup_tasks.send_followup_whatsapp_task, "delay", lambda *a: calls.append(a)
    )

    lead = await _create_lead(client, auth_headers, phone=None)
    response = await client.post(
        f"/api/v1/crm/leads/{lead['id']}/followups",
        json={"follow_up_type": "whatsapp", "scheduled_at": "2026-08-01T10:00:00Z"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert calls == []
