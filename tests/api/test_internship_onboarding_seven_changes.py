"""
Regression tests for the onboarding update: an optional WhatsApp group link, the Sensitive document setting, the in-page document
viewer, declining only when allowed, the student's confirmed mobile number, and the personal link ending an hour after completion.
Synthetic data only; the payment gateway and object storage are fakes.
"""

import importlib.util
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update

from app.core.config import settings as app_settings
from modules.internship_onboarding import scan
from modules.internship_onboarding.completion import check, sweep
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.models import (
    FinancialDocument,
    OnboardingApplication,
    OnboardingDocument,
    OnboardingEvent,
    PaymentOrder,
    PaymentTransaction,
)
from modules.internship_onboarding.service import LINK_WINDOW, ApplicationService, hash_token
from modules.institutions.models import InstitutionStudent
from modules.our_internships.models import InternshipSelection
from tests.api.test_internship_onboarding import BASE, PDF, PUBLIC, configure, iso, link, settings, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import gateway, payment_event, ready_to_pay, signed  # noqa: F401
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

HOOK = "/api/v1/public/payments/cashfree/webhook"
FLOW = "onboarding-flow"
FREE = dict(modes={"require_payment": False}, fees={"base_amount": "0", "methods": [], "late_fee": {"mode": "none", "value": "0"}})
ONLINE = dict(fees={"methods": ["cashfree"]}, payment_accounts={"bank": None})
REVIEWER = ("our_internships.view", "our_internships.onboarding.review")
MESSAGE = (
    "This onboarding link has expired. Your onboarding information has been saved. "
    "Please contact the internship team if you need assistance."
)


async def config_view(client, headers, internship) -> dict:
    return (await client.get(f"{BASE}/{internship.id}/{FLOW}/config", headers=headers)).json()


async def verify_all(client, headers, db, internship, approve=True):
    ids = [d.id for d in (await db.execute(select(OnboardingDocument).where(OnboardingDocument.status != "superseded"))).scalars().all()]
    for document_id in ids:
        await client.post(f"{BASE}/{internship.id}/{FLOW}/documents/{document_id}/review", json={"approve": approve, "note": "again"}, headers=headers)


async def application_of(db, student_id=None) -> OnboardingApplication:
    query = select(OnboardingApplication)
    if student_id is not None:
        query = query.join(InternshipSelection, InternshipSelection.id == OnboardingApplication.selection_id).where(InternshipSelection.student_id == student_id)
    application = (await db.execute(query)).scalars().first()
    await db.refresh(application)
    return application


async def complete_free(client, headers, db, internship, student) -> str:
    """A zero-fee internship: link, form, documents, acceptance, then a reviewer verifies the documents."""
    await configure(client, headers, internship, **FREE)
    token = await ready_to_pay(client, headers, internship, student)
    await verify_all(client, headers, db, internship)
    assert (await application_of(db, student.id)).completed_at is not None
    return token


# ------------------------------------------------------------------ 1. optional WhatsApp group link


@pytest.mark.parametrize("empty", ["", "   ", None])
async def test_the_whatsapp_group_link_can_be_left_empty_and_is_stored_as_empty(client, auth_headers, db_session, organization, empty):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship, communication={"whatsapp_link": empty})
    assert (await config_view(client, auth_headers, internship))["settings"]["communication"]["whatsapp_link"] is None


def test_a_whatsapp_link_is_trimmed_and_other_links_are_still_refused():
    assert OnboardingConfig.model_validate({"communication": {"whatsapp_link": "  https://chat.whatsapp.com/abc  "}}).communication.whatsapp_link == "https://chat.whatsapp.com/abc"
    assert OnboardingConfig.model_validate({}).communication.whatsapp_link is None
    with pytest.raises(ValueError, match="chat.whatsapp.com"):
        OnboardingConfig.model_validate({"communication": {"whatsapp_link": "https://example.com/join"}})


async def test_the_student_portal_shows_no_group_link_unless_one_is_set_and_visible(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    # no link configured: nothing about a group, before or after completion
    token = await complete_free(client, auth_headers, db_session, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["completion"]["completed"] is True and view["completion"]["whatsapp_link"] is None
    # a link is configured: the existing visibility setting decides (after completion here)
    await configure(client, auth_headers, internship, communication={"whatsapp_link": "https://chat.whatsapp.com/abc123"}, **FREE)
    assert (await client.get(PUBLIC, headers=tok(token))).json()["completion"]["whatsapp_link"] == "https://chat.whatsapp.com/abc123"


# ------------------------------------------------------------------ 3. the Sensitive document setting

ID_DOCS = [{"key": "college_id", "label": "College ID card"}, {"key": "id_proof", "label": "Government ID", "sensitive": True, "required": False}]


async def test_sensitive_documents_are_refused_with_a_clear_reason_while_virus_scanning_is_off(client, auth_headers, db_session, organization, monkeypatch):
    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", False)
    internship, _ = await world(db_session, organization)
    assert (await config_view(client, auth_headers, internship))["virus_scanning_available"] is False
    r = await client.put(f"{BASE}/{internship.id}/{FLOW}/config", json={"settings": settings(documents=ID_DOCS, policies={"identity_document_retention_days": 365})}, headers=auth_headers)
    assert r.status_code in (400, 422) and "virus scanning" in r.text


async def test_the_sensitive_setting_works_persists_and_needs_a_retention_period_when_scanning_is_available(client, auth_headers, db_session, organization, monkeypatch):
    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
    internship, _ = await world(db_session, organization)
    assert (await config_view(client, auth_headers, internship))["virus_scanning_available"] is True
    # identity documents also need a retention period: the refusal says so
    refused = await client.put(f"{BASE}/{internship.id}/{FLOW}/config", json={"settings": settings(documents=ID_DOCS)}, headers=auth_headers)
    assert refused.status_code in (400, 422) and "how long they are kept" in refused.text
    ok = await client.put(f"{BASE}/{internship.id}/{FLOW}/config", json={"settings": settings(documents=ID_DOCS, policies={"identity_document_retention_days": 365})}, headers=auth_headers)
    assert ok.status_code == 200, ok.text
    for _ in range(2):  # a refresh (a second read) shows the same thing
        saved = (await config_view(client, auth_headers, internship))["settings"]
        assert {d["key"]: d["sensitive"] for d in saved["documents"]} == {"college_id": False, "id_proof": True}
        assert saved["policies"]["identity_document_retention_days"] == 365
    # switching it off again persists too
    plain = [{**d, "sensitive": False} for d in ID_DOCS]
    assert (await client.put(f"{BASE}/{internship.id}/{FLOW}/config", json={"settings": settings(documents=plain, policies={"identity_document_retention_days": 365})}, headers=auth_headers)).status_code == 200
    assert not any(d["sensitive"] for d in (await config_view(client, auth_headers, internship))["settings"]["documents"])


async def test_an_aadhaar_document_cannot_be_saved_as_not_sensitive_even_when_scanning_is_available(client, auth_headers, db_session, organization, monkeypatch):
    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
    internship, _ = await world(db_session, organization)
    docs = [{"key": "aadhaar", "label": "Aadhaar card", "sensitive": False}]
    r = await client.put(f"{BASE}/{internship.id}/{FLOW}/config", json={"settings": settings(documents=docs, policies={"identity_document_retention_days": 365})}, headers=auth_headers)
    assert r.status_code in (400, 422) and "sensitive" in r.text


async def test_a_sensitive_document_keeps_its_reviewer_only_access_and_retention_date(client, auth_headers, db_session, organization, storage, monkeypatch):
    async def clean(*args):
        return "stream: OK"

    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
    monkeypatch.setattr(scan, "clamd_instream", clean)
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, documents=ID_DOCS, policies={"identity_document_retention_days": 365})
    token = await link(client, auth_headers, internship, s0)
    assert (await client.post(f"{PUBLIC}/documents/id_proof", files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))).status_code == 201
    document = (await db_session.execute(select(OnboardingDocument).where(OnboardingDocument.requirement_key == "id_proof"))).scalar_one()
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    docs = f"{BASE}/{internship.id}/{FLOW}/documents"
    assert (await client.get(f"{docs}/{document.id}/file", headers=manager)).status_code == 403  # no reviewer permission, no access
    assert (await client.get(f"{docs}/{document.id}/preview", headers=manager)).status_code == 403
    reviewer = await admin_headers(db_session, organization, permissions=REVIEWER)
    assert (await client.get(f"{docs}/{document.id}/file", headers=reviewer)).status_code == 200


# ------------------------------------------------------------------ 4. the in-page document viewer


async def upload_pdf(client, token, key="college_id"):
    r = await client.post(f"{PUBLIC}/documents/{key}", files={"file": (f"{key}.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert r.status_code == 201, r.text


async def test_a_reviewer_gets_the_document_inline_with_safe_headers_and_the_view_is_logged(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    await upload_pdf(client, token)
    document = (await db_session.execute(select(OnboardingDocument))).scalar_one()
    reviewer = await admin_headers(db_session, organization, permissions=REVIEWER)
    r = await client.get(f"{BASE}/{internship.id}/{FLOW}/documents/{document.id}/file", headers=reviewer)
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")  # shown, not downloaded
    assert "college_id" not in r.headers["content-disposition"]  # the stored file name is not echoed
    assert r.headers["cache-control"] == "private, no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in r.headers["content-security-policy"]
    viewed = (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.event == "document_viewed"))).scalars().all()
    assert len(viewed) == 1 and viewed[0].actor_user_id is not None
    detail = (await client.get(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}", headers=reviewer)).json()
    assert detail["documents"][0]["content_type"] == "application/pdf" and detail["documents"][0]["viewable"] is True


async def test_the_document_viewer_endpoint_is_not_public_and_never_crosses_organizations(client, auth_headers, db_session, organization, storage):
    from modules.organizations.repository import OrganizationRepository

    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    await upload_pdf(client, await link(client, auth_headers, internship, s0))
    document = (await db_session.execute(select(OnboardingDocument))).scalar_one()
    url = f"{BASE}/{internship.id}/{FLOW}/documents/{document.id}/file"
    assert (await client.get(url)).status_code in (401, 403)  # no login, no document
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    outsider = await admin_headers(db_session, other, permissions=REVIEWER)
    assert (await client.get(url, headers=outsider)).status_code == 404
    # the right document id under a different internship of the same organization is also not found
    sibling, _ = await world(db_session, organization, n=1)
    reviewer = await admin_headers(db_session, organization, permissions=REVIEWER)
    assert (await client.get(f"{BASE}/{sibling.id}/{FLOW}/documents/{document.id}/file", headers=reviewer)).status_code == 404


async def test_a_removed_file_and_an_unsupported_type_are_not_served_inline(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    await upload_pdf(client, await link(client, auth_headers, internship, s0))
    document = (await db_session.execute(select(OnboardingDocument))).scalar_one()
    reviewer = await admin_headers(db_session, organization, permissions=REVIEWER)
    url = f"{BASE}/{internship.id}/{FLOW}/documents/{document.id}/file"
    document.content_type = "text/html"
    await db_session.flush()
    refused = await client.get(url, headers=reviewer)
    assert refused.status_code == 409 and "Download" in refused.text
    detail = (await client.get(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}", headers=reviewer)).json()
    assert detail["documents"][0]["viewable"] is False
    document.content_type, document.removed_at = "application/pdf", datetime.now(timezone.utc)
    await db_session.flush()
    assert (await client.get(url, headers=reviewer)).status_code == 409


async def test_the_existing_signed_download_link_still_works_for_the_download_button(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    await upload_pdf(client, await link(client, auth_headers, internship, s0))
    document = (await db_session.execute(select(OnboardingDocument))).scalar_one()
    r = await client.get(f"{BASE}/{internship.id}/{FLOW}/documents/{document.id}/preview", headers=auth_headers)
    assert r.status_code == 200 and "exp=180" in r.json()["url"]


# ------------------------------------------------------------------ 5. declining is optional


async def test_declining_is_off_by_default_and_the_api_refuses_a_direct_request(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    off = dict(modes={"allow_decline": False})
    assert OnboardingConfig().modes.allow_decline is False  # also for an internship saved before the setting existed
    await configure(client, auth_headers, internship, **off)
    token = await link(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["acceptance"]["decline_allowed"] is False
    refused = await client.post(f"{PUBLIC}/decline", json={"reason": "no"}, headers=tok(token))
    assert refused.status_code == 403
    application = await application_of(db_session)
    assert application.declined_at is None
    assert (await client.get(PUBLIC, headers=tok(token))).json()["statuses"]["offer"] == "awaiting_response"


async def test_declining_works_when_allowed_and_old_declines_stay_visible_when_it_is_switched_off(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship)  # the shared test settings opt in
    declined_token, other_token = await link(client, auth_headers, internship, s0), await link(client, auth_headers, internship, s1)
    assert (await client.get(PUBLIC, headers=tok(declined_token))).json()["acceptance"]["decline_allowed"] is True
    done = await client.post(f"{PUBLIC}/decline", json={"reason": "Joining another programme"}, headers=tok(declined_token))
    assert done.status_code == 200 and done.json()["statuses"]["offer"] == "declined"
    await configure(client, auth_headers, internship, modes={"allow_decline": False})
    after = (await client.get(PUBLIC, headers=tok(declined_token))).json()
    assert after["statuses"]["offer"] == "declined" and after["acceptance"]["declined_at"] and after["acceptance"]["decline_allowed"] is False
    detail = (await client.get(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}", headers=auth_headers)).json()
    assert detail["acceptance"]["decline_reason"] == "Joining another programme"  # the historical record is untouched
    assert (await client.post(f"{PUBLIC}/decline", json={}, headers=tok(other_token))).status_code == 403


async def test_staff_can_still_withdraw_a_student_whatever_the_decline_setting_is(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, modes={"allow_decline": False})
    await link(client, auth_headers, internship, s0)
    r = await client.post(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}/cancel", json={"reason": "Withdrawn at their request"}, headers=auth_headers)
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ 6. the confirmed mobile number


def mobile(token, phone="81234 56789", confirmed=True):
    return {"json": {"phone": phone, "confirmed": confirmed}, "headers": tok(token)}


async def test_a_mobile_number_is_only_saved_when_confirmed_and_valid(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    assert (await client.put(f"{PUBLIC}/mobile", **mobile(token, confirmed=False))).status_code == 422
    for bad in ("12345", "5123456789", "98765 4321", "abcdefghij", "+44 7911 123456", "98765432101234"):
        r = await client.put(f"{PUBLIC}/mobile", **mobile(token, bad))
        assert r.status_code == 422, bad
    assert (await application_of(db_session)).confirmed_phone is None


async def test_the_student_can_correct_the_number_before_and_after_submitting_and_after_the_deadline(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await ready_to_pay(client, auth_headers, internship, s0)  # documents submitted and the offer accepted
    r = await client.put(f"{PUBLIC}/mobile", **mobile(token, "+91 81234-56789"))
    assert r.status_code == 200, r.text
    assert r.json()["mobile"] == {"number": "8123456789", "confirmed": True, "valid": True, "record_review_pending": True, "editable": True}
    # onboarding closes for new submissions: the number can still be corrected while the link is valid
    await configure(client, auth_headers, internship, deadlines={"opens_at": iso(-10), "closes_at": iso(-1)})
    assert (await client.get(PUBLIC, headers=tok(token))).json()["open"] is False
    again = await client.put(f"{PUBLIC}/mobile", **mobile(token, "9123456780"))
    assert again.status_code == 200 and again.json()["mobile"]["number"] == "9123456780"
    # nothing else restarted: the acceptance and the documents are as they were
    view = again.json()
    assert view["statuses"]["offer"] == "accepted" and view["statuses"]["documents"] == "submitted"


async def test_staff_still_review_the_change_to_the_student_record(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    view = (await client.put(f"{PUBLIC}/mobile", **mobile(token, "8123456789"))).json()
    assert view["information"]["review"] == "pending" and view["information"]["proposed"] == {"phone_change": True}
    student = await db_session.get(InstitutionStudent, s0.id)
    await db_session.refresh(student)
    assert student.phone == "9876543210"  # the record only changes when staff apply it
    r = await client.post(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}/info-review", json={"approve": True}, headers=auth_headers)
    assert r.status_code == 200
    await db_session.refresh(student)
    assert student.phone == "8123456789"
    # the number already on the record needs no review
    same = (await client.put(f"{PUBLIC}/mobile", **mobile(token, "+91 81234 56789"))).json()
    assert same["mobile"]["record_review_pending"] is False and same["information"]["review"] == "approved"


async def test_confirming_the_number_on_the_record_makes_no_review_request(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    view = (await client.put(f"{PUBLIC}/mobile", **mobile(token, "98765 43210"))).json()
    assert view["information"]["review"] == "none" and view["information"]["proposed"] == {}
    assert view["mobile"]["confirmed"] is True and view["mobile"]["record_review_pending"] is False
    app = await application_of(db_session)
    assert app.confirmed_phone == "9876543210" and app.phone_changed_at is None  # confirmed, but nothing changed


async def test_new_payment_orders_use_the_confirmed_number_and_existing_orders_are_never_changed(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **ONLINE)
    token = await ready_to_pay(client, auth_headers, internship, s0)

    def sent_phones():
        return [json.loads(r.content)["customer_details"]["customer_phone"] for r in gateway.requests if r.method == "POST" and r.url.path == "/pg/orders"]

    first = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert sent_phones() == ["9876543210"]  # the number on the record, as before a student could confirm one
    again = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert again["order_id"] == first["order_id"]  # nothing changed: the same order is resumed
    before = (await db_session.execute(select(PaymentOrder).where(PaymentOrder.merchant_order_id == first["order_id"]))).scalar_one()
    snapshot = (before.status, before.amount, before.payment_session_id, before.provider_order_id)

    assert (await client.put(f"{PUBLIC}/mobile", **mobile(token, "8123456789"))).status_code == 200
    second = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert second["order_id"] != first["order_id"] and sent_phones() == ["9876543210", "8123456789"]
    await db_session.refresh(before)
    assert (before.status, before.amount, before.payment_session_id, before.provider_order_id) == snapshot  # the first order is untouched
    # the new order is resumed from now on; re-confirming the same number changes nothing
    assert (await client.put(f"{PUBLIC}/mobile", **mobile(token, "81234 56789"))).status_code == 200
    third = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert third["order_id"] == second["order_id"] and len(sent_phones()) == 2


async def test_changing_the_number_never_touches_receipts_the_ledger_or_a_settled_payment(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **ONLINE)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, payment_id=31))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"

    async def money():
        rows = (await db_session.execute(select(PaymentTransaction.id, PaymentTransaction.kind, PaymentTransaction.amount, PaymentTransaction.status).order_by(PaymentTransaction.id))).all()
        docs = (await db_session.execute(select(FinancialDocument.id, FinancialDocument.number, FinancialDocument.sha256).order_by(FinancialDocument.id))).all()
        orders = (await db_session.execute(select(PaymentOrder.id, PaymentOrder.status, PaymentOrder.amount).order_by(PaymentOrder.id))).all()
        return rows, docs, orders

    before = await money()
    assert len(before[1]) == 1
    assert (await client.put(f"{PUBLIC}/mobile", **mobile(token, "8123456789"))).status_code == 200
    assert await money() == before


async def test_the_mobile_number_is_kept_out_of_the_timeline_and_the_audit_trail(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    assert (await client.put(f"{PUBLIC}/mobile", **mobile(token, "8123456789"))).status_code == 200
    event = (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.event == "mobile_confirmed"))).scalar_one()
    assert event.detail == {"last4": "6789", "changed": True} and event.actor == "student"
    assert "8123456789" not in json.dumps([e.detail for e in (await db_session.execute(select(OnboardingEvent))).scalars()])
    audit = (await db_session.execute(text("select count(*) from audit_logs where changes::text like :c"), {"c": "%8123456789%"})).scalar_one()
    assert audit == 0  # not in any audit entry (the review request is a marker, not the number)


async def test_a_declined_or_cancelled_student_cannot_save_a_number_and_the_link_is_required(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    declined, cancelled = await link(client, auth_headers, internship, s0), await link(client, auth_headers, internship, s1)
    await client.post(f"{PUBLIC}/decline", json={}, headers=tok(declined))
    assert (await client.put(f"{PUBLIC}/mobile", **mobile(declined))).status_code == 409
    await client.post(f"{BASE}/{internship.id}/{FLOW}/students/{s1.id}/cancel", json={"reason": "x"}, headers=auth_headers)
    assert (await client.put(f"{PUBLIC}/mobile", **mobile(cancelled))).status_code == 404  # the cancelled link is dead
    assert (await client.put(f"{PUBLIC}/mobile", json={"phone": "8123456789", "confirmed": True})).status_code == 404  # no token


async def test_the_draft_endpoint_no_longer_changes_the_phone_so_the_confirmation_cannot_be_skipped(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    r = await client.put(f"{PUBLIC}/draft", json={"info": {"name": "Student 0", "phone": "8123456789"}}, headers=tok(token))
    assert r.status_code == 200
    app = await application_of(db_session)
    assert app.confirmed_phone is None and "phone" not in (app.info_proposed or {})


# ------------------------------------------------------------------ 7. the personal link ends an hour after completion


async def expire(db, application):
    application.link_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    await db.flush()


async def test_free_onboarding_starts_the_hour_at_the_recorded_completion_time(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **FREE)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    app = await application_of(db_session)
    assert app.completed_at is None and app.link_expires_at is None  # documents are still being checked: nothing expires
    await verify_all(client, auth_headers, db_session, internship)
    app = await application_of(db_session)
    assert app.completed_at is not None and app.link_expires_at == app.completed_at + LINK_WINDOW == app.completed_at + timedelta(hours=1)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["completion"]["completed"] is True and view["completion"]["link_expires_at"] is not None


async def test_paid_onboarding_starts_the_hour_only_when_the_payment_is_confirmed(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **ONLINE)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    await verify_all(client, auth_headers, db_session, internship)  # documents are done, payment is not
    app = await application_of(db_session)
    assert app.completed_at is None and app.link_expires_at is None
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    assert (await application_of(db_session)).link_expires_at is None  # an open checkout does not start the clock
    raw, headers = signed(payment_event(order_id, payment_id=41))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"
    app = await application_of(db_session)
    assert app.completed_at is not None and app.link_expires_at == app.completed_at + LINK_WINDOW


ENDPOINTS = [
    ("get", "", {}),
    ("put", "/draft", {"json": {"answers": {"tshirt": "L"}}}),
    ("put", "/mobile", {"json": {"phone": "8123456789", "confirmed": True}}),
    ("post", "/accept", {"json": {"confirmed": True, "terms_version": "1"}}),
    ("post", "/decline", {"json": {}}),
    ("post", "/refund-request", {"json": {"reason": "x"}}),
    ("post", "/payments/checkout", {}),
    ("post", "/payments/refresh", {}),
    ("post", "/documents/college_id", {"files": {"file": ("a.pdf", PDF, "application/pdf")}}),
    ("get", f"/financial-documents/{uuid.uuid4()}", {}),
]


async def test_after_the_hour_every_student_endpoint_refuses_the_link_with_a_clear_message(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    token = await complete_free(client, auth_headers, db_session, internship, s0)
    for method, path, kwargs in ENDPOINTS:
        assert (await getattr(client, method)(f"{PUBLIC}{path}", headers=tok(token), **kwargs)).status_code != 410, (method, path)
    await expire(db_session, await application_of(db_session))
    for method, path, kwargs in ENDPOINTS:
        r = await getattr(client, method)(f"{PUBLIC}{path}", headers=tok(token), **kwargs)
        assert r.status_code == 410, (method, path, r.status_code)
        assert r.json()["error"]["code"] == "onboarding_link_expired" and r.json()["error"]["message"] == MESSAGE
    # an expired link is not the same thing as an unknown one
    assert (await client.get(PUBLIC, headers=tok("x" * 43))).status_code == 404


async def test_expiry_deletes_nothing_and_staff_see_everything_as_before(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    token = await complete_free(client, auth_headers, db_session, internship, s0)
    counts = lambda: db_session.execute(select(func.count(OnboardingDocument.id)))  # noqa: E731
    before = (await counts()).scalar_one()
    await expire(db_session, await application_of(db_session))
    assert (await client.get(PUBLIC, headers=tok(token))).status_code == 410
    assert (await counts()).scalar_one() == before == 2
    detail = (await client.get(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}", headers=auth_headers)).json()
    assert detail["statuses"]["overall"] == "completed" and len(detail["documents"]) == 2 and detail["link_expires_at"] is not None
    board = (await client.get(f"{BASE}/{internship.id}/{FLOW}/dashboard", headers=auth_headers)).json()
    assert board["metrics"]["completed"] == 1
    # staff can still preview a document and read the timeline
    doc = detail["documents"][0]["id"]
    assert (await client.get(f"{BASE}/{internship.id}/{FLOW}/documents/{doc}/file", headers=auth_headers)).status_code == 200


async def test_the_link_is_not_expired_while_something_is_outstanding_and_the_hour_restarts_when_it_is_met_again(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    token = await complete_free(client, auth_headers, db_session, internship, s0)
    docs = (await db_session.execute(select(OnboardingDocument))).scalars().all()
    # a reviewer sends a document back after completion: the student has something to do again
    r = await client.post(f"{BASE}/{internship.id}/{FLOW}/documents/{docs[0].id}/review", json={"approve": False, "note": "Blurred photo"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    await expire(db_session, await application_of(db_session))
    view = await client.get(PUBLIC, headers=tok(token))
    assert view.status_code == 200 and view.json()["statuses"]["documents"] == "changes_requested"
    app = await application_of(db_session)
    assert app.link_expires_at is None and app.completed_at is not None  # the window is paused, the completion record kept
    assert (await client.post(f"{PUBLIC}/documents/{docs[0].requirement_key}", files={"file": ("again.pdf", PDF, "application/pdf")}, headers=tok(token))).status_code == 201
    # the reviewer approves the new version: complete again, and a fresh hour starts
    newest = (await db_session.execute(select(OnboardingDocument).where(OnboardingDocument.status == "submitted"))).scalars().one()
    assert (await client.post(f"{BASE}/{internship.id}/{FLOW}/documents/{newest.id}/review", json={"approve": True}, headers=auth_headers)).status_code == 200
    app = await application_of(db_session)
    assert app.link_expires_at is not None and app.link_expires_at > datetime.now(timezone.utc) + timedelta(minutes=55)
    events = [e.event for e in (await db_session.execute(select(OnboardingEvent).order_by(OnboardingEvent.created_at))).scalars()]
    assert "link_window_paused" in events and "link_window_restarted" in events and events.count("onboarding_completed") == 1
    await expire(db_session, app)
    assert (await client.get(PUBLIC, headers=tok(token))).status_code == 410


async def test_the_background_sweep_restarts_a_paused_window(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await complete_free(client, auth_headers, db_session, internship, s0)
    app = await application_of(db_session)
    app.link_expires_at = None  # as left by a student visit while something was outstanding
    await db_session.flush()
    await sweep(db_session)
    await db_session.refresh(app)
    assert app.link_expires_at is not None and app.link_expires_at > datetime.now(timezone.utc)


async def test_completion_is_recorded_once_even_when_another_worker_got_there_first(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **FREE)
    await ready_to_pay(client, auth_headers, internship, s0)
    # the reviewers' approvals are done by hand here so this test controls the order
    for d in (await db_session.execute(select(OnboardingDocument))).scalars().all():
        d.status = "verified"
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    await db_session.flush()
    app = await application_of(db_session, s0.id)
    first_worker = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    stale = app  # this request still sees "not completed"
    await db_session.execute(
        update(OnboardingApplication).where(OnboardingApplication.id == app.id)
        .values(completed_at=first_worker, link_expires_at=first_worker + LINK_WINDOW).execution_options(synchronize_session=False)
    )
    assert stale.completed_at is None
    assert await check(db_session, stale) is False  # it loses the race and changes nothing
    await db_session.refresh(app)
    assert app.completed_at == first_worker and app.link_expires_at == first_worker + LINK_WINDOW
    events = (await db_session.execute(select(func.count(OnboardingEvent.id)).where(OnboardingEvent.event == "onboarding_completed"))).scalar_one()
    assert events == 0
    assert selection is not None


async def test_a_pending_email_link_cannot_be_used_to_get_around_the_expiry(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    old = await complete_free(client, auth_headers, db_session, internship, s0)
    app = await application_of(db_session)
    pending = "pending-token-" + uuid.uuid4().hex
    app.pending_token_hash, app.pending_token_issued_at, app.pending_token_ref = hash_token(pending), datetime.now(timezone.utc), "ol:x:y"
    await expire(db_session, app)
    assert (await client.get(PUBLIC, headers=tok(pending))).status_code == 410
    await db_session.refresh(app)
    assert app.token_hash != hash_token(pending) and app.pending_token_hash == hash_token(pending)  # it was not promoted
    assert (await client.get(PUBLIC, headers=tok(old))).status_code == 410


async def test_a_replaced_link_stays_dead_and_only_staff_can_open_a_new_window(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    first = await complete_free(client, auth_headers, db_session, internship, s0)
    app = await application_of(db_session)
    await expire(db_session, app)
    # an automatic email link keeps the existing end time: the system can never keep a link alive
    internship_row = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    from modules.our_internships.models import OurInternship

    issued = await ApplicationService(db_session).issue_link(await db_session.get(OurInternship, app.internship_id), internship_row, None, "email")
    ended = issued.application.link_expires_at
    assert ended is not None and ended < datetime.now(timezone.utc)
    assert (await client.get(PUBLIC, headers=tok(first))).status_code == 404  # replaced
    assert (await client.get(PUBLIC, headers=tok(issued.link.split("#t=")[1]))).status_code == 410
    # a staff member deliberately issuing a link for a finished student gives that link its own hour
    renewed = await link(client, auth_headers, internship, s0)
    r = await client.get(PUBLIC, headers=tok(renewed))
    assert r.status_code == 200
    await db_session.refresh(app)
    assert app.link_expires_at > datetime.now(timezone.utc) + timedelta(minutes=55)
    assert (await client.get(PUBLIC, headers=tok(first))).status_code == 404 and (await client.get(PUBLIC, headers=tok(issued.link.split("#t=")[1]))).status_code == 404


async def test_the_webhook_and_staff_actions_keep_working_after_a_students_link_expired(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **ONLINE)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    await verify_all(client, auth_headers, db_session, internship)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, payment_id=51))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"
    await expire(db_session, await application_of(db_session))
    assert (await client.get(PUBLIC, headers=tok(token))).status_code == 410
    # a repeated signed notification after expiry is still accepted, and idempotent: no second payment, receipt or email
    again = await client.post(HOOK, content=raw, headers=headers)
    assert again.status_code == 200 and again.json()["outcome"] == "duplicate"
    assert (await db_session.execute(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.kind == "payment"))).scalar_one() == 1
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar_one() == 1
    # finance can still list and download the receipt, and staff still see the full ledger
    receipts = (await client.get(f"{BASE}/{internship.id}/{FLOW}/financial-documents", headers=auth_headers)).json()
    assert len(receipts) == 1
    assert (await client.get(f"{BASE}/{internship.id}/{FLOW}/financial-documents/{receipts[0]['id']}/download", headers=auth_headers)).status_code == 200
    detail = (await client.get(f"{BASE}/{internship.id}/{FLOW}/students/{s0.id}", headers=auth_headers)).json()
    assert [p["status"] for p in detail["payments"] if p["kind"] == "payment"] == ["confirmed"]


async def test_a_new_pending_payment_checkout_survives_expiry_of_the_personal_link(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, **ONLINE)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    app = await application_of(db_session)
    assert app.link_expires_at is None  # an unpaid student's link never starts counting down
    order = (await db_session.execute(select(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id))).scalar_one()
    assert order.status == "active" and order.payment_session_id


# ------------------------------------------------------------------ the migration's transition for students who are already complete


def _migration():
    path = next(Path(__file__).resolve().parents[2].glob("apps/api/alembic/versions/0102_*.py"))
    spec = importlib.util.spec_from_file_location("migration_0102", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_the_migration_gives_students_who_are_already_complete_one_last_day_and_touches_no_one_else(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1, s2) = await world(db_session, organization, n=3)
    await configure(client, auth_headers, internship, **FREE)
    for s in (s0, s1, s2):
        await link(client, auth_headers, internship, s)
    apps = {a.selection_id: a for a in (await db_session.execute(select(OnboardingApplication))).scalars().all()}
    selections = {s.student_id: s.id for s in (await db_session.execute(select(InternshipSelection))).scalars().all()}
    done, cancelled, open_ = (apps[selections[s.id]] for s in (s0, s1, s2))
    long_ago = datetime.now(timezone.utc) - timedelta(days=30)
    done.completed_at = cancelled.completed_at = long_ago
    cancelled.cancelled_at = long_ago
    await db_session.flush()
    await db_session.execute(text(_migration().BACKFILL_SQL))
    for a in (done, cancelled, open_):
        await db_session.refresh(a)
    assert done.link_expires_at is not None and timedelta(hours=23) < done.link_expires_at - datetime.now(timezone.utc) <= timedelta(hours=24)
    assert cancelled.link_expires_at is None and open_.link_expires_at is None  # a student with something left to do is not given an end
    assert done.completed_at == long_ago  # no history is rewritten


def test_the_migration_is_additive_only():
    source = (Path(__file__).resolve().parents[2] / "apps/api/alembic/versions/0102_onboarding_link_expiry_and_mobile.py").read_text(encoding="utf-8")
    upgrade = source.split("def upgrade")[1].split("def downgrade")[0].lower()
    assert upgrade.count("add_column") == 3 and "drop_" not in upgrade and "delete" not in upgrade
    assert "completed_at is not null" in _migration().BACKFILL_SQL.lower()
