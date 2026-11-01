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
