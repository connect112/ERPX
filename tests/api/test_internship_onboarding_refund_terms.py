"""
Internship onboarding: the per-internship "Allow refund requests" switch (off by default), the refund terms kept with
each acceptance, the student refund-request workflow, the organization's saved bank/UPI accounts and the UPI payment
QR code. Synthetic data only.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.audit.models import AuditLog
from modules.internship_onboarding.models import OnboardingApplication, PaymentTransaction
from modules.our_internships.models import InternshipSelection
from tests.api.test_internship_onboarding import BASE, PDF, PUBLIC, configure, link, settings, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import claim
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

ACCOUNTS = "/api/v1/internship-onboarding-payment-accounts"
POLICY_ON = {"allow_refund_requests": True, "refund_policy": "Synthetic policy P1.", "refund_policy_version": "1", "refund_request_days": 30}
BANK = {"holder": "GIR Technologies", "bank": "Test Bank", "account_number": "123456789012", "ifsc": "TEST0123456"}


async def accepted(client, headers, internship, student, refund_policy_version=None) -> str:
    token = await link(client, headers, internship, student)
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))
    for key in ("college_id", "signed_offer_letter"):
        r = await client.post(f"{PUBLIC}/documents/{key}", files={"file": (f"{key}.pdf", PDF, "application/pdf")}, headers=tok(token))
        assert r.status_code == 201, r.text
    body = {"confirmed": True, "terms_version": "1", "refund_policy_version": refund_policy_version}
    r = await client.post(f"{PUBLIC}/accept", json=body, headers=tok(token))
    assert r.status_code == 200, r.text
    return token


async def paid(client, headers, db, internship, token, reference="UTR123456789"):
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token, reference=reference))).status_code == 201
    tx = (await db.execute(select(PaymentTransaction).where(PaymentTransaction.reference == reference))).scalar_one()
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/verify", json={"approve": True}, headers=headers)
    assert r.status_code == 200, r.text
    return tx


async def application_of(db, student) -> OnboardingApplication:
    selection = (await db.execute(select(InternshipSelection).where(InternshipSelection.student_id == student.id))).scalar_one()
    application = (await db.execute(select(OnboardingApplication).where(OnboardingApplication.selection_id == selection.id))).scalar_one()
    await db.refresh(application)
    return application


# ------------------------------------------------------------------ refund requests off (the default)


async def test_with_refund_requests_off_students_see_a_neutral_notice_and_staff_refunds_still_work(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)  # no refund switch: off, and no policy wording needed
    token = await accepted(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["acceptance"]["refund_policy"] is None and view["acceptance"]["refund_policy_version"] is None
    notice = view["acceptance"]["payment_terms_notice"]
    assert "does not affect any refund you are entitled to by law" in notice and "non-refundable" not in notice
    application = await application_of(db_session, s0)
    assert application.refund_terms == {"allow_refund_requests": False, "notice": notice}
    assert application.declaration_text.endswith(f"Payment terms:\n{notice}")

    tx = await paid(client, auth_headers, db_session, internship, token)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["refund"] == {"requests_offered": False, "can_request": False, "until": None, "request": None}
    r = await client.post(f"{PUBLIC}/refund-request", json={"reason": "Changed plans"}, headers=tok(token))
    assert r.status_code == 409 and "not part of the terms you accepted" in r.text
    # authorised staff refunds and corrections are unaffected by the switch
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/refund", json={"amount": "500", "reason": "Correction"}, headers=auth_headers)
    assert r.status_code == 201


# ------------------------------------------------------------------ refund requests on


async def test_with_refund_requests_on_the_accepted_policy_is_kept_and_requests_go_to_finance(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship, policies=POLICY_ON)
    token = await link(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["acceptance"]["refund_policy"] == "Synthetic policy P1." and view["acceptance"]["payment_terms_notice"] is None
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))
    stale = await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))
    assert stale.status_code == 409 and "refund policy" in stale.text  # the policy version must be the one shown
    token = await accepted(client, auth_headers, internship, s0, refund_policy_version="1")
    application = await application_of(db_session, s0)
    assert application.refund_terms["allow_refund_requests"] is True and application.refund_terms["policy_version"] == "1"
    assert application.refund_terms["request_days"] == 30 and len(application.refund_terms["policy_sha256"]) == 64
    assert "Synthetic policy P1." in application.declaration_text
    assert (await client.post(f"{PUBLIC}/refund-request", json={"reason": "x"}, headers=tok(token))).status_code == 409  # nothing paid yet

    tx = await paid(client, auth_headers, db_session, internship, token)
    # staff change the policy and switch requests off: this student's accepted terms do not change
    await configure(client, auth_headers, internship, policies={"allow_refund_requests": False, "refund_policy": "P2"})
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["refund"]["requests_offered"] is True and view["refund"]["can_request"] is True and view["refund"]["until"]
    application = await application_of(db_session, s0)
    assert application.refund_terms["policy_version"] == "1" and "P2" not in application.declaration_text

    r = await client.post(f"{PUBLIC}/refund-request", json={"reason": "Cannot attend"}, headers=tok(token))
    assert r.status_code == 200 and r.json()["refund"]["request"]["status"] == "open"
    assert (await client.post(f"{PUBLIC}/refund-request", json={"reason": "again"}, headers=tok(token))).status_code == 409
    board = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/dashboard", headers=auth_headers)).json()
    assert board["refund_requests_open"] == 1
    detail = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}", headers=auth_headers)).json()
    assert detail["refund_request"]["reason"] == "Cannot attend" and detail["acceptance"]["refund_terms"]["policy_version"] == "1"

    decline = f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/refund-request/decline"
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    assert (await client.post(decline, json={"note": "no"}, headers=manager)).status_code == 403
    assert (await client.post(decline, json={"note": "Outside the policy"}, headers=auth_headers)).status_code == 200
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["refund"]["request"]["status"] == "declined" and view["refund"]["request"]["note"] == "Outside the policy"

    # asked again, finance refunds through the usual route: the request is linked to that refund, no money moved by itself
    await client.post(f"{PUBLIC}/refund-request", json={"reason": "Medical reasons"}, headers=tok(token))
    refunds_before = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "refund"))).scalars().all()
    assert refunds_before == []
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/refund", json={"amount": "5000", "reason": "Approved request"}, headers=auth_headers)
    application = await application_of(db_session, s0)
    assert application.refund_request["status"] == "refund_started" and application.refund_request["refund_id"] == r.json()["id"]

    # a student accepting after the switch went off gets no request option
    other = await accepted(client, auth_headers, internship, s1)
    assert (await application_of(db_session, s1)).refund_terms["allow_refund_requests"] is False
    assert (await client.get(PUBLIC, headers=tok(other))).json()["refund"]["requests_offered"] is False


async def test_refund_requests_close_when_the_accepted_window_ends(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, policies={**POLICY_ON, "refund_request_days": 1})
    token = await accepted(client, auth_headers, internship, s0, refund_policy_version="1")
    tx = await paid(client, auth_headers, db_session, internship, token)
    row = await db_session.get(PaymentTransaction, tx.id)
    row.verified_at = row.verified_at - timedelta(days=2)
    await db_session.flush()
    assert (await client.get(PUBLIC, headers=tok(token))).json()["refund"]["can_request"] is False
    r = await client.post(f"{PUBLIC}/refund-request", json={"reason": "late"}, headers=tok(token))
    assert r.status_code == 409 and "period" in r.text


# ------------------------------------------------------------------ saved payment accounts


async def test_saved_accounts_are_finance_only_audited_and_shown_to_students_once_verified_and_enabled(client, auth_headers, db_session, organization, storage):
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    viewer = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.finance.view"))
    body = {"kind": "bank", "label": "Main account", "details": BANK}
    assert (await client.post(ACCOUNTS, json=body, headers=manager)).status_code == 403
    assert (await client.get(ACCOUNTS, headers=manager)).status_code == 403
    assert (await client.post(ACCOUNTS, json={**body, "details": {**BANK, "ifsc": "bad"}}, headers=auth_headers)).status_code in (400, 422)
    created = await client.post(ACCOUNTS, json=body, headers=auth_headers)
    assert created.status_code == 201 and created.json()["verified"] is False
    account_id = created.json()["id"]
    assert (await client.post(ACCOUNTS, json=body, headers=auth_headers)).status_code == 409  # names are unique
    masked = (await client.get(ACCOUNTS, headers=viewer)).json()[0]["details"]["account_number"]
    assert masked.endswith("9012") and "12345678" not in masked

    internship, (s0, _) = await world(db_session, organization)
    url = f"{BASE}/{internship.id}/onboarding-flow/config"
    r = await client.put(url, json={"settings": settings(payment_accounts={"bank": None, "bank_account_id": "00000000-0000-0000-0000-000000000001"})}, headers=auth_headers)
    assert r.status_code in (400, 422) and "does not exist" in r.text
    await configure(client, auth_headers, internship, payment_accounts={"bank": None, "bank_account_id": account_id})
    token = await accepted(client, auth_headers, internship, s0)

    # not verified yet: the method is not offered and a claim for it is refused
    pay = (await client.get(PUBLIC, headers=tok(token))).json()["payment"]
    assert pay["open"] and pay["methods"] == [] and pay["bank"] is None
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code in (400, 422)

    assert (await client.post(f"{ACCOUNTS}/{account_id}/verify", headers=manager)).status_code == 403
    assert (await client.post(f"{ACCOUNTS}/{account_id}/verify", headers=auth_headers)).json()["verified"] is True
    pay = (await client.get(PUBLIC, headers=tok(token))).json()["payment"]
    assert pay["methods"] == ["bank_transfer"] and pay["bank"]["account_number"] == "123456789012"
    # a submitted UTR and screenshot are a claim, never a payment, until finance confirms the money arrived
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code == 201
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.payment_status.value != "paid"

    # new details must be checked again; a switched-off account disappears and cannot be chosen again
    edited = await client.patch(f"{ACCOUNTS}/{account_id}", json={"details": {**BANK, "account_number": "999999999999"}}, headers=auth_headers)
    assert edited.json()["verified"] is False
    assert (await client.get(PUBLIC, headers=tok(token))).json()["payment"]["bank"] is None
    await client.post(f"{ACCOUNTS}/{account_id}/verify", headers=auth_headers)
    await client.patch(f"{ACCOUNTS}/{account_id}", json={"enabled": False}, headers=auth_headers)
    assert (await client.get(PUBLIC, headers=tok(token))).json()["payment"]["bank"] is None
    r = await client.put(url, json={"settings": settings(payment_accounts={"bank": None, "bank_account_id": account_id})}, headers=auth_headers)
    assert r.status_code in (400, 422) and "switched off" in r.text

    logged = (await db_session.execute(select(AuditLog).where(AuditLog.entity_type == "internship_payment_accounts"))).scalars().all()
    assert len(logged) >= 4  # created, verified, edited, re-verified, switched off


async def test_the_upi_qr_code_asks_for_exactly_what_the_student_owes(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    upi = {"vpa": "gir.tech@testbank", "beneficiary": "GIR Technologies"}
    await configure(client, auth_headers, internship, fees={"base_amount": "2000", "methods": ["upi"]}, payment_accounts={"bank": None, "upi": upi})
    token = await accepted(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    shown = view["payment"]["upi"]
    assert shown["link"] == f"upi://pay?pa=gir.tech@testbank&pn=GIR%20Technologies&am=2000.00&cu=INR&tn={view['reference']}"
    assert shown["qr"].startswith("data:image/png;base64,") and Decimal(view["payment"]["balance"]) == Decimal("2000.00")

    await configure(client, auth_headers, internship, fees={"base_amount": "2000", "methods": ["upi"]}, payment_accounts={"bank": None, "upi": {**upi, "show_qr": False}})
    shown = (await client.get(PUBLIC, headers=tok(token))).json()["payment"]["upi"]
    assert shown["qr"] is None and shown["link"].startswith("upi://pay?")
