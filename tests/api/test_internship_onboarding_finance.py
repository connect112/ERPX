"""
Internship onboarding, milestone F and the rest of G: receipts / tax invoices / credit notes, refunds (manual and
Cashfree, mocked HTTP), cancellation, CSV exports and the completion email. Synthetic data only.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.internship_onboarding.models import FinancialDocument, OnboardingApplication, PaymentTransaction
from tests.api.test_internship_onboarding import BASE, PUBLIC, configure, link, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import claim, gateway, online, payment_event, ready_to_pay, signed  # noqa: F401
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api


async def paid_by_bank(client, headers, db, internship, student, _amount="5000.00", **over):
    await configure(client, headers, internship, **over)
    token = await ready_to_pay(client, headers, internship, student)
    await client.post(f"{PUBLIC}/payments/manual", **claim(token, amount=_amount))
    tx = (await db.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalars().all()[-1]
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/verify", json={"approve": True}, headers=headers)
    assert r.status_code == 200, r.text
    return token, tx


async def test_a_confirmed_payment_gets_one_receipt_the_student_can_download(client, auth_headers, db_session, organization, storage):
    from modules.internship_onboarding.financial import issue

    internship, (s0, s1) = await world(db_session, organization)
    token, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    docs = (await db_session.execute(select(FinancialDocument))).scalars().all()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.kind == "receipt" and doc.number.startswith("RCPT-") and doc.number.endswith("-000001") and doc.amount == Decimal("5000.00")
    assert storage.objects[doc.storage_key].startswith(b"%PDF") and doc.details["tax"] is None  # no GSTIN: no tax lines invented
    assert (await issue(db_session, tx)).id == doc.id  # never twice

    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert [d["number"] for d in view["financial_documents"]] == [doc.number]
    assert "exp=300" in (await client.get(f"{PUBLIC}/financial-documents/{doc.id}", headers=tok(token))).json()["url"]
    other = await link(client, auth_headers, internship, s1)
    assert (await client.get(f"{PUBLIC}/financial-documents/{doc.id}", headers=tok(other))).status_code == 404

    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    assert (await client.get(f"{BASE}/{internship.id}/onboarding-flow/financial-documents", headers=manager)).status_code == 403
    listed = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/financial-documents", headers=auth_headers)).json()
    assert listed[0]["number"] == doc.number
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/financial-documents/{doc.id}/resend", headers=auth_headers)).status_code == 202


async def test_a_tax_invoice_needs_a_gstin_and_splits_tax_from_the_accepted_fee(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    bad = await client.put(f"{BASE}/{internship.id}/onboarding-flow/config", json={"settings": {
        **_settings(), "issuer": {"legal_name": "GIR Technologies Pvt Ltd", "gstin": "36ABCDE1234F1Z5"}}}, headers=auth_headers)
    assert bad.status_code in (400, 422) and "tax treatment" in bad.text  # a GSTIN with no tax treatment is refused
    await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00",
                       fees={"tax_mode": "exclusive", "tax_rate_percent": "18"},
                       issuer={"legal_name": "GIR Technologies Pvt Ltd", "address": "Hyderabad", "gstin": "36ABCDE1234F1Z5"})  # fmt: skip
    doc = (await db_session.execute(select(FinancialDocument))).scalar_one()
    assert doc.kind == "tax_invoice" and doc.details["tax"] == {"label": "GST", "rate_percent": "18", "taxable": "5000.00", "tax": "900.00"}
    assert doc.details["issuer"]["gstin"] == "36ABCDE1234F1Z5"


def _settings():
    from tests.api.test_internship_onboarding import settings

    return settings()


async def test_a_manual_refund_waits_for_the_transfer_and_issues_a_credit_note(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    token, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    url = f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/refund"
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    assert (await client.post(url, json={"amount": "100", "reason": "x"}, headers=manager)).status_code == 403
    assert (await client.post(url, json={"amount": "6000", "reason": "too much"}, headers=auth_headers)).status_code in (400, 422)
    r = await client.post(url, json={"amount": "2000", "reason": "Partial withdrawal"}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["status"] == "awaiting_verification"
    refund_id = r.json()["id"]
    # what is still being refunded counts: only 3000 more can be asked for
    assert (await client.post(url, json={"amount": "3500", "reason": "again"}, headers=auth_headers)).status_code in (400, 422)
    decide = f"{BASE}/{internship.id}/onboarding-flow/refunds/{refund_id}/decide"
    assert (await client.post(decide, json={"approve": True}, headers=auth_headers)).status_code in (400, 422)  # needs the transfer reference
    assert (await client.post(decide, json={"approve": True, "reference": "NEFT-REF-1"}, headers=auth_headers)).json()["status"] == "confirmed"
    docs = {d.kind: d for d in (await db_session.execute(select(FinancialDocument))).scalars().all()}
    assert docs["credit_note"].number.startswith("RCPT-CN-") and docs["credit_note"].amount == Decimal("2000.00")
    assert docs["credit_note"].details["against"] == f"Receipt {docs['receipt'].number}"
    original = await db_session.get(PaymentTransaction, tx.id)
    assert original.status == "confirmed" and original.amount == Decimal("5000.00")  # the payment itself is never changed
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["statuses"]["payment"] == "partially_refunded" and len(view["financial_documents"]) == 2
    # an agreed refund lowers what is owed: the student is not asked to pay it again
    assert view["payment"]["balance"] == "0.00" and view["payment"]["open"] is False
    assert view["payment"]["payable"] == "3000.00" and view["statuses"]["overall"] != "awaiting_payment"


async def test_an_online_refund_goes_through_the_gateway_and_confirms_on_its_notification(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id))
    await client.post("/api/v1/public/payments/cashfree/webhook", content=raw, headers=headers)
    payment = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()

    def refunds(request):
        if request.method == "POST" and request.url.path.endswith("/refunds"):
            body = json.loads(request.content)
            import httpx

            return httpx.Response(200, json={"refund_id": body["refund_id"], "cf_refund_id": "cf1", "refund_status": "PENDING", "refund_amount": body["refund_amount"]})
        return original_handler(request)

    original_handler = gateway.handler
    gateway.handler = refunds  # noqa: B023
    from modules.internship_onboarding import payments as payments_module
    from modules.internship_onboarding.providers.cashfree import CashfreeProvider
    import httpx

    payments_module.get_provider = lambda name: CashfreeProvider("TEST_APP", "test-secret-key-not-real", "sandbox", "2023-08-01", transport=httpx.MockTransport(refunds))
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{payment.id}/refund", json={"amount": "5000", "reason": "Programme cancelled"}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    refund = await db_session.get(PaymentTransaction, r.json()["id"])
    event = {"type": "REFUND_STATUS_WEBHOOK", "data": {"refund": {"order_id": order_id, "refund_id": f"RF{refund.id.hex[:30]}", "refund_status": "SUCCESS", "refund_amount": 5000.0}}}
    raw, headers = signed(event)
    out = (await client.post("/api/v1/public/payments/cashfree/webhook", content=raw, headers=headers)).json()
    assert out["outcome"] == "refund confirmed"
    await db_session.refresh(refund)
    assert refund.status == "confirmed"
    assert {d.kind for d in (await db_session.execute(select(FinancialDocument))).scalars().all()} == {"receipt", "credit_note"}
    assert (await client.get(PUBLIC, headers=tok(token))).json()["statuses"]["payment"] == "refunded"


async def test_cancelling_stops_the_link_and_keeps_the_money_records(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    token, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    url = f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/cancel"
    assert (await client.post(url, json={"reason": ""}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.post(url, json={"reason": "Withdrew for health reasons"}, headers=auth_headers)).status_code == 200
    assert (await client.get(PUBLIC, headers=tok(token))).status_code == 404
    assert (await db_session.get(PaymentTransaction, tx.id)).status == "confirmed"
    detail = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}", headers=auth_headers)).json()
    assert detail["statuses"]["overall"] == "cancelled"


async def test_csv_exports_are_safe_in_spreadsheets_and_hide_money_without_finance(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    s0.name = "=HYPERLINK(\"http://evil\")"
    await db_session.flush()
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    out = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/export.csv", headers=auth_headers)).text
    assert "'=HYPERLINK" in out and "Outstanding" in out
    viewer = await admin_headers(db_session, organization, permissions=("our_internships.view",))
    assert "Outstanding" not in (await client.get(f"{BASE}/{internship.id}/onboarding-flow/export.csv", headers=viewer)).text
    assert (await client.get(f"{BASE}/{internship.id}/onboarding-flow/payments.csv", headers=viewer)).status_code == 403
    assert "UTR123456789" in (await client.get(f"{BASE}/{internship.id}/onboarding-flow/payments.csv", headers=auth_headers)).text


async def test_the_completion_email_goes_once(client, auth_headers, db_session, organization, storage, monkeypatch):
    from modules.internship_onboarding.completion import follow_up
    from modules.internship_onboarding.models import OnboardingDocument
    from packages.email import service as email_module

    sent: list = []

    async def fake_send(to, subject, text, html, **kw):
        sent.append((to, subject))
        return True

    monkeypatch.setattr(email_module.email_service, "send", fake_send)
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    for d in (await db_session.execute(select(OnboardingDocument))).scalars().all():
        await client.post(f"{BASE}/{internship.id}/onboarding-flow/documents/{d.id}/review", json={"approve": True}, headers=auth_headers)
    application = (await db_session.execute(select(OnboardingApplication))).scalar_one()
    assert application.completed_at is not None
    await follow_up(db_session, application.id)
    await follow_up(db_session, application.id)
    completion = [s for s in sent if "onboarded" in s[1]]
    assert len(completion) == 1 and completion[0][0] == s0.email
