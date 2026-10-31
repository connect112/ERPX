"""
Internship onboarding release hardening: Cashfree can only be offered when the installation enables it, the refund
policy and retention period reach the student, uploads are never stored past a failing virus scanner, and a payment
claim or refund cannot be duplicated by a repeated request. Synthetic data only.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings as app_settings
from modules.internship_onboarding import scan
from modules.internship_onboarding.models import OnboardingApplication, OnboardingDocument, PaymentTransaction
from tests.api.test_internship_onboarding import BASE, PDF, PUBLIC, configure, link, settings, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import claim, ready_to_pay

pytestmark = pytest.mark.api

ID_DOCS = [
    {"key": "college_id", "label": "College ID card"},
    {"key": "id_proof", "label": "Government ID", "sensitive": True, "required": False},
]


@pytest.fixture
def scanner(monkeypatch):
    """A switched-on scanner whose reply each test chooses (the clamd protocol itself is covered by the unit tests)."""
    replies = {"reply": "stream: OK"}

    async def fake(host, port, data, timeout):
        if replies["reply"] is None:
            raise scan.ScanError("ConnectionRefusedError")
        return replies["reply"]

    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
    monkeypatch.setattr(scan, "clamd_instream", fake)
    return replies


async def test_cashfree_cannot_be_offered_while_it_is_not_set_up(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization, n=1)
    r = await client.put(f"{BASE}/{internship.id}/onboarding-flow/config",
                         json={"settings": settings(fees={"methods": ["cashfree"]}, payment_accounts={"bank": None})}, headers=auth_headers)  # fmt: skip
    assert r.status_code in (400, 422) and "not set up" in r.text
    view = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()
    assert view["cashfree_available"] is False and view["settings"]["issuer"]["legal_name"] == "GIR Technologies"


async def test_the_refund_policy_is_shown_before_acceptance_and_kept_with_it(client, auth_headers, db_session, organization, storage, scanner):
    internship, (s0, s1) = await world(db_session, organization)
    policy = "Synthetic policy text for the test."
    await configure(client, auth_headers, internship, documents=ID_DOCS,
                    policies={"refund_policy": policy, "identity_document_retention_days": 180})  # fmt: skip
    token = await ready_to_pay_with(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["acceptance"]["refund_policy"] == policy and view["identity_document_retention_days"] == 180
    application = (await db_session.execute(select(OnboardingApplication).where(OnboardingApplication.accepted_at.is_not(None)))).scalar_one()
    assert application.declaration_text.endswith(f"Refund policy:\n{policy}")

    # a student who leaves: their identity document shows when its retention period ends
    other = await link(client, auth_headers, internship, s1)
    up = await client.post(f"{PUBLIC}/documents/id_proof", files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(other))
    assert up.status_code == 201
    await client.post(f"{PUBLIC}/decline", json={}, headers=tok(other))
    student = f"{BASE}/{internship.id}/onboarding-flow/students/{s1.id}"
    detail = (await client.get(student, headers=auth_headers)).json()
    doc = next(d for d in detail["documents"] if d["key"] == "id_proof")
    declined = detail["acceptance"]["declined_at"]
    assert doc["scan_status"] == "clean" and doc["keep_until"][:10] == _plus_days(declined, 180) and doc["removed_at"] is None

    # nothing is deleted automatically, and not before the period ends
    remove = f"{BASE}/{internship.id}/onboarding-flow/documents/{doc['id']}/remove-file"
    assert (await client.post(remove, headers=auth_headers)).status_code == 409
    board = f"{BASE}/{internship.id}/onboarding-flow/dashboard"
    assert (await client.get(board, headers=auth_headers)).json()["identity_documents_due_for_removal"] == 0

    # once it has ended, the overdue file is counted (never silent) and a reviewer removes it; the record stays
    app_row = (await db_session.execute(select(OnboardingApplication).where(OnboardingApplication.declined_at.is_not(None)))).scalar_one()
    app_row.declined_at = app_row.declined_at - timedelta(days=181)
    await db_session.flush()
    assert (await client.get(board, headers=auth_headers)).json()["identity_documents_due_for_removal"] == 1
    from tests.api.test_storage_manager import admin_headers

    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    assert (await client.post(remove, headers=manager)).status_code == 403
    stored = (await db_session.execute(select(OnboardingDocument).where(OnboardingDocument.id == doc["id"]))).scalar_one()
    assert stored.storage_key in storage.objects
    assert (await client.post(remove, headers=auth_headers)).status_code == 200
    assert stored.storage_key not in storage.objects
    assert (await client.post(remove, headers=auth_headers)).status_code == 409
    preview = f"{BASE}/{internship.id}/onboarding-flow/documents/{doc['id']}/preview"
    assert (await client.get(preview, headers=auth_headers)).status_code == 409
    assert (await client.get(board, headers=auth_headers)).json()["identity_documents_due_for_removal"] == 0
    detail = (await client.get(student, headers=auth_headers)).json()
    assert next(d for d in detail["documents"] if d["key"] == "id_proof")["removed_at"]
    assert any(e["event"] == "identity_document_removed" for e in detail["events"])


async def test_identity_documents_and_paid_consent_cannot_rest_on_missing_safeguards(client, auth_headers, db_session, organization, storage, monkeypatch):
    internship, (s0,) = await world(db_session, organization, n=1)
    url = f"{BASE}/{internship.id}/onboarding-flow/config"

    async def save(**over):
        return await client.put(url, json={"settings": settings(**over)}, headers=auth_headers)

    with_retention = {"refund_policy": "Synthetic refund policy for tests.", "identity_document_retention_days": 90}
    # no virus scanner: identity documents cannot be requested at all
    r = await save(documents=ID_DOCS, policies=with_retention)
    assert r.status_code in (400, 422) and "virus scanning" in r.text
    # an Aadhaar requirement must be marked sensitive (so it falls under the rule above)
    r = await save(documents=[{"key": "aadhaar", "label": "Aadhaar card"}])
    assert r.status_code in (400, 422) and "sensitive" in r.text
    # paid self-service onboarding needs the refund policy the student agrees to
    r = await save(policies={"refund_policy": ""})
    assert r.status_code in (400, 422) and "refund policy" in r.text
    # with a scanner: identity documents still need a retention period
    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
    r = await save(documents=ID_DOCS)
    assert r.status_code in (400, 422) and "kept" in r.text
    assert (await save(documents=ID_DOCS, policies=with_retention)).status_code == 200

    # if the scanner is switched off later, identity uploads stop rather than going in unscanned
    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", False)
    token = await link(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert {d["key"]: d["accepting"] for d in view["documents"]} == {"college_id": True, "id_proof": False}
    r = await client.post(f"{PUBLIC}/documents/id_proof", files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert r.status_code == 503
    assert (await db_session.execute(select(func.count(OnboardingDocument.id)))).scalar() == 0 and storage.objects == {}


async def ready_to_pay_with(client, headers, internship, student) -> str:
    token = await link(client, headers, internship, student)
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))
    r = await client.post(f"{PUBLIC}/documents/college_id", files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert r.status_code == 201, r.text
    r = await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))
    assert r.status_code == 200, r.text
    return token


def _plus_days(iso: str, days: int) -> str:
    from datetime import datetime

    return (datetime.fromisoformat(iso) + timedelta(days=days)).date().isoformat()


async def test_uploads_are_scanned_when_a_scanner_is_configured_and_refused_when_it_fails(client, auth_headers, db_session, organization, storage, scanner):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    url = f"{PUBLIC}/documents/college_id"

    scanner["reply"] = None  # unreachable: fail closed
    r = await client.post(url, files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert r.status_code == 503
    scanner["reply"] = "stream: Eicar-Signature FOUND"
    r = await client.post(url, files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert r.status_code in (400, 422) and "virus scanner" in r.text
    assert storage.objects == {} and (await db_session.execute(select(func.count(OnboardingDocument.id)))).scalar() == 0

    scanner["reply"] = "stream: OK"
    r = await client.post(url, files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert r.status_code == 201
    assert (await db_session.execute(select(OnboardingDocument.scan_status))).scalar_one() == "clean"


async def test_an_infected_payment_proof_is_refused_and_nothing_is_recorded(client, auth_headers, db_session, organization, storage, scanner):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    before = dict(storage.objects)
    scanner["reply"] = "stream: Eicar-Signature FOUND"
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code in (400, 422)
    assert storage.objects == before
    assert (await db_session.execute(select(func.count(PaymentTransaction.id)))).scalar() == 0
    scanner["reply"] = "stream: OK"
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code == 201
    assert (await db_session.execute(select(PaymentTransaction.proof_scan_status))).scalar_one() == "clean"


async def test_manual_shortcuts_need_finance_or_reviewer_permission_once_students_onboard_themselves(client, auth_headers, db_session, organization):
    from tests.api.test_storage_manager import admin_headers

    (selfserve, (s0, _)), (staff_only, (t0, _)) = await world(db_session, organization), await world(db_session, organization)
    await configure(client, auth_headers, selfserve)
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))

    def patch(internship, student, body):
        return client.patch(f"{BASE}/{internship.id}/selected/{student.id}/onboarding", json=body, headers=manager)

    assert (await patch(selfserve, s0, {"payment_status": "paid"})).status_code == 403
    assert (await patch(selfserve, s0, {"verification_status": "verified"})).status_code == 403
    bulk = await client.post(f"{BASE}/{selfserve.id}/onboarding/bulk", json={"student_ids": [str(s0.id)], "payment_status": "paid"}, headers=manager)
    assert bulk.status_code == 403
    assert (await patch(selfserve, s0, {"offer_response": "accepted"})).status_code == 200  # not a money or review decision
    # an internship onboarded by staff alone keeps the existing process unchanged
    assert (await patch(staff_only, t0, {"payment_status": "paid"})).status_code == 200
    # an Administrator holds both permissions
    assert (await client.patch(f"{BASE}/{selfserve.id}/selected/{s0.id}/onboarding", json={"payment_status": "paid"}, headers=auth_headers)).status_code == 200
