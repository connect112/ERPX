"""
Internship onboarding with Cashfree (mocked HTTP, real signatures): the order is for the fee the internship configures and
the student accepted (never a fixed amount), and nothing is recorded as paid, receipted or completed until a signed
notification or a server-side status check confirms the exact amount. Synthetic data only.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from modules.internship_onboarding.models import FinancialDocument, OnboardingApplication, PaymentOrder
from modules.our_internships.models import InternshipSelection
from tests.api.test_internship_onboarding import PUBLIC, configure, settings, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import gateway, payment_event, ready_to_pay, signed  # noqa: F401

pytestmark = pytest.mark.api

HOOK = "/api/v1/public/payments/cashfree/webhook"
ONLINE_FEE = {"base_amount": "3500", "tax_mode": "exclusive", "tax_rate_percent": "18", "methods": ["cashfree"]}


async def order_amount(db, merchant_order_id: str) -> Decimal:
    return (await db.execute(select(PaymentOrder.amount).where(PaymentOrder.merchant_order_id == merchant_order_id))).scalar_one()


async def test_the_order_is_for_the_configured_fee_the_student_accepted(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship, fees=ONLINE_FEE, payment_accounts={"bank": None})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    # staff change the fee after this student accepted: their order keeps the accepted amount
    await configure(client, auth_headers, internship, fees={**ONLINE_FEE, "base_amount": "9999"}, payment_accounts={"bank": None})
    first = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()
    assert await order_amount(db_session, first["order_id"]) == Decimal("4130.00")  # 3500 + 18% tax, as accepted
    sent = [r for r in gateway.requests if r.method == "POST" and r.url.path == "/pg/orders"][-1]
    assert b'"order_amount": 4130.0' in sent.content and b'"order_currency": "INR"' in sent.content

    # a student who accepts after the change pays the new configured fee
    other = await ready_to_pay(client, auth_headers, internship, s1)
    second = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(other))).json()
    assert await order_amount(db_session, second["order_id"]) == Decimal("11798.82")  # 9999 + 18%


async def test_nothing_is_paid_receipted_or_completed_before_the_gateway_confirms(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, fees={"methods": ["cashfree"]}, payment_accounts={"bank": None})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]

    async def nothing_yet():
        selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
        await db_session.refresh(selection)
        application = (await db_session.execute(select(OnboardingApplication))).scalar_one()
        await db_session.refresh(application)
        receipts = (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar()
        return selection.payment_status.value != "paid" and receipts == 0 and application.completed_at is None

    # the student returns from the checkout page while the gateway still reports the payment as pending
    gateway.payments[order_id] = [{"cf_payment_id": "5", "payment_status": "PENDING", "payment_amount": 5000, "payment_currency": "INR"}]
    assert (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()["outcome"] == "pending"
    assert await nothing_yet()
    # dropped, failed and forged notifications change nothing that matters
    dropped = payment_event(order_id, status="USER_DROPPED", payment_id=6)
    dropped["type"] = "PAYMENT_USER_DROPPED_WEBHOOK"
    for body, secret in ((dropped, None), (payment_event(order_id, status="FAILED", payment_id=7), None), (payment_event(order_id, payment_id=8), "forged")):
        raw, headers = signed(body, **({"secret": secret} if secret else {}))
        await client.post(HOOK, content=raw, headers=headers)
    assert await nothing_yet()

    # a signed success for the exact amount: paid once, one receipt
    raw, headers = signed(payment_event(order_id, payment_id=9))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"
    assert not await nothing_yet()
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar() == 1


async def test_a_refund_cashfree_makes_by_itself_is_reported_to_staff_and_never_changes_the_ledger(client, auth_headers, db_session, organization, storage, gateway):
    from modules.internship_onboarding.models import OnboardingEvent, PaymentTransaction

    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, fees={"methods": ["cashfree"]}, payment_accounts={"bank": None})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, payment_id=9))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"

    # AUTO_REFUND_STATUS_WEBHOOK has no order block: it used to be refused as unreadable (and retried by Cashfree forever)
    auto = {"type": "AUTO_REFUND_STATUS_WEBHOOK", "data": {"refund": {"cf_payment_id": "9", "refund_amount": 5000, "refund_status": "SUCCESS"}}}
    raw, headers = signed(auto)
    r = await client.post(HOOK, content=raw, headers=headers)
    assert r.status_code == 200 and r.json()["outcome"] == "auto refund: reported to staff"
    noted = (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.event == "gateway_auto_refund"))).scalar_one()
    assert noted.detail["amount"] == "5000" and noted.actor == "system"
    kinds = (await db_session.execute(select(PaymentTransaction.kind))).scalars().all()
    assert "refund" not in kinds  # finance confirms and records it; nothing is assumed

    raw, headers = signed({"type": "AUTO_REFUND_STATUS_WEBHOOK", "data": {"refund": {"cf_payment_id": "unknown"}}})
    r = await client.post(HOOK, content=raw, headers=headers)
    assert r.status_code == 200 and r.json()["outcome"] == "auto refund: no matching payment"
    forged, h2 = signed(auto, secret="attacker-guess")
    assert (await client.post(HOOK, content=forged, headers=h2)).status_code == 401


# ------------------------------------------------------------------ sandbox acceptance: replays and the ₹1 refund


@pytest.fixture
def queued_emails(monkeypatch):
    """Every receipt / credit-note email the code asks Celery to send."""
    from modules.internship_onboarding import financial

    sent: list[str] = []
    monkeypatch.setattr(financial, "enqueue_email", lambda document_id: sent.append(str(document_id)))
    return sent


async def journal_entries(db) -> int:
    from sqlalchemy import text

    return (await db.execute(text("SELECT count(*) FROM accounting_journal_entries"))).scalar_one()


async def paid_online(client, headers, db, internship, student, gateway, payment_id="901"):
    await configure(client, headers, internship, fees={"base_amount": "2000", "methods": ["cashfree"]}, payment_accounts={"bank": None})
    token = await ready_to_pay(client, headers, internship, student)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    success = payment_event(order_id, amount=2000.0, payment_id=payment_id)
    success["data"]["order"]["order_amount"] = 2000.0
    raw, sig = signed(success)
    assert (await client.post(HOOK, content=raw, headers=sig)).json()["outcome"] == "confirmed"
    return token, order_id, success, raw, sig


async def test_a_replayed_success_adds_no_payment_receipt_email_or_accounting_entry(client, auth_headers, db_session, organization, storage, gateway, queued_emails):
    from modules.internship_onboarding.models import PaymentTransaction, PaymentWebhookEvent

    internship, (s0, _) = await world(db_session, organization)
    entries_before = await journal_entries(db_session)
    token, order_id, success, raw, sig = await paid_online(client, auth_headers, db_session, internship, s0, gateway)
    # Cashfree delivers the same notification again, and a re-wrapped copy of it; the status check also sees it
    assert (await client.post(HOOK, content=raw, headers=sig)).json()["outcome"] == "duplicate"
    raw2, sig2 = signed({**success, "event_time": "2026-11-02T10:05:00+05:30"})
    assert (await client.post(HOOK, content=raw2, headers=sig2)).json()["outcome"] == "already recorded"
    gateway.payments[order_id] = [{"cf_payment_id": "901", "payment_status": "SUCCESS", "payment_amount": 2000, "payment_currency": "INR"}]
    await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))

    payments = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalars().all()
    assert [(p.status, p.amount) for p in payments] == [("confirmed", Decimal("2000.00"))]
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar() == 1
    assert len(queued_emails) == 1  # one receipt email, however often the payment is reported
    assert (await db_session.execute(select(func.count(PaymentWebhookEvent.id)))).scalar() == 2  # the exact repeat is not stored again
    assert await journal_entries(db_session) == entries_before  # onboarding never posts to the accounting ledger


async def test_a_one_rupee_refund_is_counted_once_and_its_replays_change_nothing(client, auth_headers, db_session, organization, storage, gateway, queued_emails, monkeypatch):
    import httpx

    from modules.internship_onboarding import payments as payments_module
    from modules.internship_onboarding.models import PaymentTransaction
    from modules.internship_onboarding.providers.cashfree import CashfreeProvider
    from tests.api.test_internship_onboarding import BASE
    from tests.api.test_internship_onboarding_payments import SECRET

    internship, (s0, _) = await world(db_session, organization)
    token, order_id, *_ = await paid_online(client, auth_headers, db_session, internship, s0, gateway)
    payment = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()
    refund_calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/refunds"):
            body = __import__("json").loads(request.content)
            refund_calls.append(body)
            return httpx.Response(200, json={"refund_id": body["refund_id"], "cf_refund_id": "cf-r1", "refund_status": "PENDING", "refund_amount": body["refund_amount"]})
        return gateway.handler(request)

    provider = CashfreeProvider("TEST_APP", SECRET, "sandbox", "2025-01-01", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(payments_module, "get_provider", lambda name: provider)
    url = f"{BASE}/{internship.id}/onboarding-flow/payments/{payment.id}/refund"
    r = await client.post(url, json={"amount": "1", "reason": "Sandbox refund check"}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert (await client.post(url, json={"amount": "1", "reason": "again"}, headers=auth_headers)).status_code == 409  # one open refund
    refund = await db_session.get(PaymentTransaction, r.json()["id"])
    assert [c["refund_id"] for c in refund_calls] == [f"RF{refund.id.hex[:30]}"]  # one call, id derived from the refund row

    note = {"type": "REFUND_STATUS_WEBHOOK", "data": {"refund": {"order_id": order_id, "refund_id": f"RF{refund.id.hex[:30]}",
                                                                 "cf_refund_id": "cf-r1", "refund_status": "SUCCESS", "refund_amount": 1.0}}}  # fmt: skip
    raw, sig = signed(note)
    assert (await client.post(HOOK, content=raw, headers=sig)).json()["outcome"] == "refund confirmed"
    assert (await client.post(HOOK, content=raw, headers=sig)).json()["outcome"] == "duplicate"
    raw2, sig2 = signed({**note, "event_time": "later"})
    assert (await client.post(HOOK, content=raw2, headers=sig2)).json()["outcome"] == "unknown refund"  # already confirmed: ignored

    rows = (await db_session.execute(select(PaymentTransaction.kind, PaymentTransaction.status, PaymentTransaction.amount, PaymentTransaction.note)
                                     .order_by(PaymentTransaction.created_at))).all()  # fmt: skip
    assert sorted((k, s, a) for k, s, a, _ in rows) == [
        ("payment", "confirmed", Decimal("2000.00")), ("refund", "confirmed", Decimal("1.00")), ("waiver", "confirmed", Decimal("1.00")),
    ]
    assert [n for k, _, _, n in rows if k == "waiver"] == ["refund_adjustment"]
    # counted once: the student owes 1,999 and has paid 1,999 net (2,000 - 1); nothing outstanding, nothing refunded twice
    pay = (await client.get(PUBLIC, headers=tok(token))).json()["payment"]
    assert (pay["payable"], pay["paid"], pay["balance"]) == ("1999.00", "1999.00", "0.00")
    board = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/dashboard", headers=auth_headers)).json()
    assert board["money"]["received"] == "1999.00" and board["money"]["outstanding"] == "0.00"
    docs = {d.kind: d for d in (await db_session.execute(select(FinancialDocument))).scalars().all()}
    assert set(docs) == {"receipt", "credit_note"} and docs["credit_note"].amount == Decimal("1.00")
    assert docs["credit_note"].details["against"] == f"Receipt {docs['receipt'].number}"
    assert len(queued_emails) == 2  # the receipt and the credit note, once each


async def test_reconciliation_recovers_a_lost_success_and_settles_failed_or_dropped_payments(client, auth_headers, db_session, organization, storage, gateway, queued_emails):
    """What the 15-minute reconciliation task does for each order still open (PaymentService.stale_orders -> refresh_order)."""
    from datetime import timedelta

    from modules.internship_onboarding.models import PaymentTransaction
    from modules.internship_onboarding.payments import PaymentService

    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship, fees={"base_amount": "2000", "methods": ["cashfree"]}, payment_accounts={"bank": None})
    lost, dropped = await ready_to_pay(client, auth_headers, internship, s0), await ready_to_pay(client, auth_headers, internship, s1)
    lost_order = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(lost))).json()["order_id"]
    dropped_order = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(dropped))).json()["order_id"]
    gateway.payments[lost_order] = [{"cf_payment_id": "701", "payment_status": "SUCCESS", "payment_amount": 2000, "payment_currency": "INR"}]
    gateway.payments[dropped_order] = [
        {"cf_payment_id": "702", "payment_status": "FAILED", "payment_amount": 2000, "payment_currency": "INR"},
        {"cf_payment_id": "703", "payment_status": "USER_DROPPED", "payment_amount": 2000, "payment_currency": "INR"},
    ]

    service = PaymentService(db_session)
    stale = await service.stale_orders(older_than=timedelta(0))
    assert {o.merchant_order_id for o in stale} == {lost_order, dropped_order}
    outcomes = {o.merchant_order_id: await service.refresh_order(o) for o in stale}
    assert outcomes[lost_order] == "confirmed"  # no webhook ever arrived: the status check found the money
    assert outcomes[dropped_order] != "confirmed"

    rows = {(t.provider_payment_id, t.status) for t in (await db_session.execute(select(PaymentTransaction))).scalars().all()}
    assert rows == {("701", "confirmed"), ("702", "failed"), ("703", "failed")}
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar() == 1 and len(queued_emails) == 1
    assert (await client.get(PUBLIC, headers=tok(lost))).json()["statuses"]["payment"] == "paid"
    view = (await client.get(PUBLIC, headers=tok(dropped))).json()
    assert view["statuses"]["payment"] != "paid" and view["payment"]["open"] is True
    # the student whose payment failed / was dropped can try again with a new order
    retry = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(dropped))).json()["order_id"]
    assert retry != dropped_order
    # running reconciliation again changes nothing
    for order in stale:
        await service.refresh_order(order)
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar() == 1 and len(queued_emails) == 1


# ------------------------------------------------------------------ sandbox acceptance: the status-check button on its own


async def test_a_lost_webhook_is_recovered_only_by_the_students_explicit_status_check(client, auth_headers, db_session, organization, storage, gateway, queued_emails):
    """The server side of the "I have paid: check status" test (./staging.sh gate on blocks the webhook and the return page):
    the money was paid at the gateway, no notification arrived. Opening the student's page never asks the gateway and never
    confirms anything; the explicit status check confirms exactly once; asking again, and the late notifications, change nothing."""
    from modules.internship_onboarding.models import OnboardingEvent, PaymentTransaction, PaymentWebhookEvent

    internship, (s0, _) = await world(db_session, organization)
    entries_before = await journal_entries(db_session)
    await configure(client, auth_headers, internship, fees={"base_amount": "2000", "methods": ["cashfree"]}, payment_accounts={"bank": None})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    gateway.payments[order_id] = [{"cf_payment_id": "777", "payment_status": "SUCCESS", "payment_amount": 2000, "payment_currency": "INR"}]

    def status_checks():
        return [r for r in gateway.requests if r.url.path.endswith(f"/orders/{order_id}/payments")]

    async def counts():
        payments = (await db_session.execute(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.kind == "payment"))).scalar()
        documents = (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar()
        webhooks = (await db_session.execute(select(func.count(PaymentWebhookEvent.id)))).scalar()
        return payments, documents, webhooks, len(queued_emails)

    # 1. the student opens the page without ?order=: nothing is asked of the gateway and nothing is recorded
    view = await client.get(PUBLIC, headers=tok(token))
    assert view.status_code == 200 and view.json()["statuses"]["payment"] != "paid"
    assert status_checks() == [] and await counts() == (0, 0, 0, 0)

    # 2. the explicit status check confirms the payment, once
    out = (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()
    assert out["outcome"] == "confirmed" and out["statuses"]["payment"] == "paid"
    assert len(status_checks()) == 1
    assert await counts() == (1, 1, 0, 1)  # one payment, one receipt, no webhook involved, one receipt email
    confirmed = (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.event == "payment_confirmed"))).scalars().all()
    assert [e.detail.get("source") for e in confirmed] == ["status check"]

    # 3. pressing it again: the order is paid, so there is nothing to check and nothing changes
    again = (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()
    assert again["outcome"] == "nothing to check" and len(status_checks()) == 1
    assert await counts() == (1, 1, 0, 1)

    # 4. the notifications that were refused earlier arrive now: acknowledged, nothing is added
    success = payment_event(order_id, amount=2000.0, payment_id="777")
    success["data"]["order"]["order_amount"] = 2000.0
    raw, sig = signed(success)
    first = await client.post(HOOK, content=raw, headers=sig)
    assert first.status_code == 200 and first.json()["outcome"] == "already recorded"
    second = await client.post(HOOK, content=raw, headers=sig)
    assert second.status_code == 200 and second.json()["outcome"] == "duplicate"
    assert await counts() == (1, 1, 1, 1)  # only the (processed) notification is stored; no second payment, receipt or email
    assert await journal_entries(db_session) == entries_before
