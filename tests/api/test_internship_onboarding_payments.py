"""
Internship onboarding payments: bank/UPI claims and finance verification, the ledger, payment-order modes, zero-fee
internships, and the Cashfree adapter (mocked HTTP; no real gateway, no real money).
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings as app_settings
from modules.internship_onboarding import payments as payments_module
from modules.internship_onboarding.models import PaymentOrder, PaymentTransaction
from modules.internship_onboarding.providers import ProviderError
from modules.internship_onboarding.providers.cashfree import CashfreeProvider
from modules.our_internships.models import InternshipSelection
from tests.api.test_internship_onboarding import BASE, PDF, PNG, PUBLIC, configure, link, storage, tok, world  # noqa: F401
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

SECRET = "test-secret-key-not-real"


async def ready_to_pay(client, headers, internship, student, **over) -> str:
    """Link -> form -> both documents -> acceptance."""
    token = await link(client, headers, internship, student)
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))
    for key in ("college_id", "signed_offer_letter"):
        r = await client.post(f"{PUBLIC}/documents/{key}", files={"file": (f"{key}.pdf", PDF, "application/pdf")}, headers=tok(token))
        assert r.status_code == 201, r.text
    r = await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))
    assert r.status_code == 200, r.text
    return token


def claim(token, reference="UTR123456789", amount="5000.00", method="bank_transfer"):
    return dict(
        data={"method": method, "reference": reference, "paid_on": date.today().isoformat(), "amount": amount},
        files={"proof": ("receipt.png", PNG, "image/png")},
        headers=tok(token),
    )


# ------------------------------------------------------------------ bank transfer / UPI


async def test_a_bank_payment_is_only_paid_after_finance_confirms_the_money_arrived(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship, fees={"methods": ["bank_transfer", "upi"]},
                    payment_accounts={"bank": {"holder": "GIR", "bank": "B", "account_number": "123456789012", "ifsc": "TEST0123456"},
                                      "upi": {"vpa": "gir@testbank", "beneficiary": "GIR"}})  # fmt: skip
    token = await ready_to_pay(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["payment"]["open"] and view["payment"]["bank"]["account_number"] == "123456789012" and view["payment"]["upi"]["vpa"] == "gir@testbank"

    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token, amount="100.00"))).status_code in (400, 422)  # not the amount due
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token, reference="12"))).status_code in (400, 422)
    no_proof = await client.post(f"{PUBLIC}/payments/manual", data=claim(token)["data"], headers=tok(token))
    assert no_proof.status_code == 422
    fake = await client.post(f"{PUBLIC}/payments/manual", data=claim(token)["data"], files={"proof": ("r.png", b"not an image", "image/png")}, headers=tok(token))
    assert fake.status_code in (400, 422)
    submitted = await client.post(f"{PUBLIC}/payments/manual", **claim(token))
    assert submitted.status_code == 201, submitted.text
    body = submitted.json()
    assert body["statuses"]["payment"] == "awaiting_manual_verification" and body["statuses"]["overall"] == "awaiting_manual_payment_approval"
    assert body["completion"]["completed"] is False  # submitting is not completing
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token, reference="UTR999999999"))).status_code == 409  # one at a time

    # the same UTR cannot be used by anyone else in the organization
    other = await ready_to_pay(client, auth_headers, internship, s1)
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(other, reference="utr-1234-56789"))).status_code == 409

    queue = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/payments", params={"status_filter": "awaiting_verification"}, headers=auth_headers)).json()
    assert len(queue) == 1 and queue[0]["transaction_reference"] == "UTR123456789" and queue[0]["has_proof"]
    tx = queue[0]["id"]
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage", "our_internships.onboarding.review"))
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx}/verify", json={"approve": True}, headers=manager)).status_code == 403
    assert (await client.get(f"{BASE}/{internship.id}/onboarding-flow/payments", headers=manager)).status_code == 403
    finance = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.finance.view", "our_internships.finance.manage"))
    proof = await client.get(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx}/proof", headers=finance)
    assert proof.status_code == 200 and "exp=180" in proof.json()["url"]  # a three-minute link, finance only
    assert (await client.get(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx}/proof", headers=manager)).status_code == 403
    ok = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx}/verify", json={"approve": True}, headers=finance)
    assert ok.status_code == 200 and ok.json()["status"] == "confirmed"
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx}/verify", json={"approve": True}, headers=finance)).status_code == 409

    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.payment_status.value == "paid" and selection.payment_amount == Decimal("5000.00")  # the LMS gate
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["statuses"]["payment"] == "paid" and view["statuses"]["overall"] == "awaiting_verification"  # documents still unchecked
    assert view["payment"]["bank"] is None  # payment closed again


async def test_a_rejected_claim_needs_a_reason_and_the_student_can_try_again(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    await client.post(f"{PUBLIC}/payments/manual", **claim(token))
    tx = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()
    url = f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/verify"
    assert (await client.post(url, json={"approve": False}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.post(url, json={"approve": False, "note": "No credit found for this UTR"}, headers=auth_headers)).json()["status"] == "rejected"
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["statuses"]["payment"] == "failed" and view["payment"]["open"]
    again = await client.post(f"{PUBLIC}/payments/manual", **claim(token))  # same UTR: the rejected claim is not live
    assert again.status_code == 201


async def test_a_different_amount_received_must_be_explained_and_leaves_a_balance(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    await client.post(f"{PUBLIC}/payments/manual", **claim(token))
    tx = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()
    url = f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/verify"
    assert (await client.post(url, json={"approve": True, "amount_received": "4000"}, headers=auth_headers)).status_code in (400, 422)
    await client.post(url, json={"approve": True, "amount_received": "4000", "note": "Bank shows 4000 only"}, headers=auth_headers)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["statuses"]["payment"] == "partially_paid" and view["payment"]["balance"] == "1000.00"
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.payment_status.value == "pending"  # never "paid" on part of the fee


async def test_payment_order_modes_and_acceptance_first(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, modes={"payment_order": "after_document_approval"})
    token = await link(client, auth_headers, internship, s0)
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code == 409  # not accepted yet
    token = await ready_to_pay(client, auth_headers, internship, s0)
    refused = await client.post(f"{PUBLIC}/payments/manual", **claim(token))
    assert refused.status_code == 409 and "verified" in refused.text
    from modules.internship_onboarding.models import OnboardingDocument

    for d in (await db_session.execute(select(OnboardingDocument))).scalars().all():
        await client.post(f"{BASE}/{internship.id}/onboarding-flow/documents/{d.id}/review", json={"approve": True}, headers=auth_headers)
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code == 201


async def test_a_zero_fee_internship_completes_without_any_payment(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, modes={"require_payment": False}, fees={"base_amount": "0", "methods": [], "late_fee": {"mode": "none", "value": "0"}})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    from modules.internship_onboarding.models import OnboardingDocument

    for d in (await db_session.execute(select(OnboardingDocument))).scalars().all():
        await client.post(f"{BASE}/{internship.id}/onboarding-flow/documents/{d.id}/review", json={"approve": True}, headers=auth_headers)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["statuses"] == {"offer": "accepted", "documents": "verified", "payment": "not_required", "overall": "completed"}
    assert view["completion"]["completed"] is True
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token))).status_code in (400, 422)


async def test_staff_can_record_a_checked_payment_in_the_ledger(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    await ready_to_pay(client, auth_headers, internship, s0)
    body = {"method": "cash", "reference": "RCPT-0001", "paid_on": date.today().isoformat(), "amount": "5000", "note": "Paid at the office"}
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/payments", json=body, headers=manager)).status_code == 403
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/payments", json=body, headers=auth_headers)).status_code == 201
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.payment_status.value == "paid"
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/payments", json=body, headers=auth_headers)).status_code == 409


# ------------------------------------------------------------------ Cashfree (mocked HTTP)


class Gateway:
    """A stand-in for Cashfree's HTTP API: records requests and answers like the documented contract."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.payments: dict[str, list[dict]] = {}
        self.amount_override: float | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST" and request.url.path == "/pg/orders":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "cf_order_id": 99, "order_id": body["order_id"], "order_status": "ACTIVE", "payment_session_id": "session_" + body["order_id"],
                "order_amount": self.amount_override if self.amount_override is not None else body["order_amount"],
                "order_currency": body["order_currency"],
            })  # fmt: skip
        if request.method == "GET" and request.url.path.endswith("/payments"):
            order_id = request.url.path.split("/")[-2]
            return httpx.Response(200, json=self.payments.get(order_id, []))
        return httpx.Response(404, json={"code": "not_found"})


@pytest.fixture
def gateway(monkeypatch):
    gw = Gateway()
    monkeypatch.setattr(app_settings, "CASHFREE_ENABLED", True)
    monkeypatch.setattr(app_settings, "CASHFREE_APP_ID", "TEST_APP")
    monkeypatch.setattr(app_settings, "CASHFREE_SECRET_KEY", SECRET)
    provider = CashfreeProvider("TEST_APP", SECRET, "sandbox", "2023-08-01", transport=httpx.MockTransport(gw.handler))
    monkeypatch.setattr(payments_module, "get_provider", lambda name: provider)
    return gw


def signed(body: dict, secret: str = SECRET, ts: int | None = None) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    stamp = str(ts if ts is not None else int(time.time() * 1000))
    sig = base64.b64encode(hmac.new(secret.encode(), stamp.encode() + raw, hashlib.sha256).digest()).decode()
    return raw, {"x-webhook-signature": sig, "x-webhook-timestamp": stamp, "content-type": "application/json"}


def payment_event(order_id: str, status: str = "SUCCESS", amount: float = 5000.0, payment_id: int = 777) -> dict:
    return {
        "type": "PAYMENT_SUCCESS_WEBHOOK" if status == "SUCCESS" else "PAYMENT_FAILED_WEBHOOK",
        "data": {
            "order": {"order_id": order_id, "order_amount": 5000.0, "order_currency": "INR"},
            "payment": {"cf_payment_id": payment_id, "payment_status": status, "payment_amount": amount, "payment_currency": "INR",
                        "payment_time": "2026-11-02T10:00:00+05:30"},
        },
    }  # fmt: skip


async def online(client, headers, internship, student):
    await configure(client, headers, internship, fees={"methods": ["cashfree"]}, payment_accounts={"bank": None})
    return await ready_to_pay(client, headers, internship, student)


async def test_checkout_creates_one_order_for_the_amount_owed_and_never_sends_the_secret_anywhere_else(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    r = await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["environment"] == "sandbox" and out["payment_session_id"].startswith("session_")
    sent = gateway.requests[0]
    assert sent.headers["x-client-id"] == "TEST_APP" and sent.headers["x-api-version"] == "2023-08-01"
    body = json.loads(sent.content)
    assert body["order_amount"] == 5000.0 and body["order_currency"] == "INR" and body["customer_details"]["customer_phone"] == "9876543210"
    assert SECRET not in r.text
    again = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert again["order_id"] == out["order_id"] and len(gateway.requests) == 1  # reused, not a second order


async def test_a_signed_success_notification_confirms_once_and_a_forged_one_does_nothing(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    hook = "/api/v1/public/payments/cashfree/webhook"

    raw, headers = signed(payment_event(order_id), secret="attacker-guess")
    assert (await client.post(hook, content=raw, headers=headers)).status_code == 401
    raw, headers = signed(payment_event(order_id), ts=int(time.time() * 1000) - 4 * 24 * 3600 * 1000)
    assert (await client.post(hook, content=raw, headers=headers)).status_code == 401  # too old to be a retry
    # the student coming back from the checkout page proves nothing
    assert (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()["statuses"]["payment"] == "pending"

    raw, headers = signed(payment_event(order_id))
    first = await client.post(hook, content=raw, headers=headers)
    assert first.status_code == 200 and first.json()["outcome"] == "confirmed"
    assert (await client.post(hook, content=raw, headers=headers)).json()["outcome"] == "duplicate"
    raw2, headers2 = signed({**payment_event(order_id), "event_time": "later"})  # same payment, different envelope
    assert (await client.post(hook, content=raw2, headers=headers2)).json()["outcome"] == "already recorded"
    late_failure, h3 = signed(payment_event(order_id, status="FAILED"))
    assert (await client.post(hook, content=late_failure, headers=h3)).json()["outcome"] == "already recorded"

    payments = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalars().all()
    assert [(p.status, p.amount) for p in payments] == [("confirmed", Decimal("5000.00"))]
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.payment_status.value == "paid"


async def test_a_payment_for_the_wrong_amount_is_never_confirmed(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, amount=1.0))
    assert (await client.post("/api/v1/public/payments/cashfree/webhook", content=raw, headers=headers)).json()["outcome"].startswith("amount mismatch")
    assert (await client.get(PUBLIC, headers=tok(token))).json()["statuses"]["payment"] == "pending"


async def test_a_lost_notification_is_recovered_by_asking_the_gateway(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    gateway.payments[order_id] = [
        {"cf_payment_id": 1, "payment_status": "FAILED", "payment_amount": 5000, "payment_currency": "INR"},
        {"cf_payment_id": 2, "payment_status": "SUCCESS", "payment_amount": 5000, "payment_currency": "INR", "payment_time": "2026-11-02T10:00:00+05:30"},
    ]
    out = (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()
    assert out["outcome"] == "confirmed" and out["statuses"]["payment"] == "paid"
    order = (await db_session.execute(select(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id))).scalar_one()
    assert order.status == "paid"


async def test_failed_payments_can_be_retried(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, status="FAILED", payment_id=5))
    assert (await client.post("/api/v1/public/payments/cashfree/webhook", content=raw, headers=headers)).json()["outcome"] == "failed"
    assert (await client.get(PUBLIC, headers=tok(token))).json()["statuses"]["payment"] == "failed"
    retry = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert retry["order_id"] != order_id


def test_the_adapter_refuses_production_unless_explicitly_authorised(monkeypatch):
    monkeypatch.setattr(app_settings, "CASHFREE_ALLOW_PRODUCTION", False)
    with pytest.raises(ProviderError, match="not authorised"):
        CashfreeProvider("APP", "SECRET", "production", "2023-08-01")
    with pytest.raises(ProviderError, match="not configured"):
        CashfreeProvider("", "", "sandbox", "2023-08-01")
    assert "SECRET" not in repr(CashfreeProvider("APP", "SECRET", "sandbox", "2023-08-01"))


async def test_the_adapter_refuses_an_order_echoed_back_with_another_amount(gateway):
    from datetime import datetime, timedelta, timezone

    gateway.amount_override = 1.0
    provider = CashfreeProvider("APP", SECRET, "sandbox", "2023-08-01", transport=httpx.MockTransport(gateway.handler))
    with pytest.raises(ProviderError, match="different amount"):
        await provider.create_order(
            merchant_order_id="ERPXI1", amount=Decimal("5000.00"), currency="INR", customer_id="c", customer_name="n",
            customer_email="e@example.com", customer_phone="+91 98765 43210", return_url="https://x", note="n",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )  # fmt: skip


# ------------------------------------------------------------------ completion, automatic LMS access, reminders


async def test_completion_is_recorded_once_and_automatic_lms_access_follows(client, auth_headers, db_session, organization, storage, rbac_seeded):
    from modules.courses.models import Course
    from modules.internship_onboarding.completion import follow_up, sweep
    from modules.internship_onboarding.models import OnboardingApplication, OnboardingDocument, OnboardingEvent

    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, modes={"require_payment": False, "lms_access": "automatic"},
                    fees={"base_amount": "0", "methods": [], "late_fee": {"mode": "none", "value": "0"}})  # fmt: skip
    await ready_to_pay(client, auth_headers, internship, s0)
    application = (await db_session.execute(select(OnboardingApplication))).scalar_one()
    assert application.completed_at is None
    for d in (await db_session.execute(select(OnboardingDocument))).scalars().all():
        await client.post(f"{BASE}/{internship.id}/onboarding-flow/documents/{d.id}/review", json={"approve": True}, headers=auth_headers)
    await db_session.refresh(application)
    assert application.completed_at is not None
    events = [e.event for e in (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.application_id == application.id))).scalars()]
    assert events.count("onboarding_completed") == 1

    # no course chosen yet: access waits, nothing half-created
    assert await follow_up(db_session, application.id) == "blocked"
    course = Course(organization_id=organization.id, title="Cloud Basics", slug=f"cloud-{application.id.hex[:6]}")
    db_session.add(course)
    await db_session.flush()
    internship.lms_course_id = course.id
    await db_session.flush()
    assert await follow_up(db_session, application.id) == "granted"
    assert await follow_up(db_session, application.id) == "already granted"  # idempotent
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.lms_status.value == "granted"
    assert (await sweep(db_session))["completed"] == 0  # nothing recorded twice


async def test_reminders_go_once_per_configured_day_and_never_to_finished_or_declined_students(client, auth_headers, db_session, organization, storage, monkeypatch):
    from modules.internship_onboarding import emails
    from modules.internship_onboarding.completion import sweep

    queued: list = []
    monkeypatch.setattr(emails, "enqueue_invitations", lambda ids: queued.extend(ids))
    internship, (s0, s1) = await world(db_session, organization)
    # closes in 2 days 12 hours: the 3-day reminder is due now, the 1-day one is not yet
    from tests.api.test_internship_onboarding import iso

    await configure(client, auth_headers, internship, deadlines={"opens_at": iso(-1), "closes_at": iso(2.5)})
    await link(client, auth_headers, internship, s0)
    declined = await link(client, auth_headers, internship, s1)
    await client.post(f"{PUBLIC}/decline", json={}, headers=tok(declined))
    first = await sweep(db_session)
    assert first["reminders"] == 1 and len(queued) == 1
    second = await sweep(db_session)
    assert second["reminders"] == 0 and len(queued) == 1  # never twice
