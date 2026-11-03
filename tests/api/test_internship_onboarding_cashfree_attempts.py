"""
Several payment attempts on one Cashfree order, and what reconciliation does about them.

A Cashfree order takes new payment attempts until it expires, so a student can fail or drop one attempt and succeed on the next, on
the same order. ERPX marks the local order "failed" after a failed or dropped attempt (that is what lets the student start a fresh
one), but the Cashfree order may still be payable, so the scheduled reconciliation must keep asking about "failed" orders, and about
"expired" ones for a short grace period (an attempt started before expiry can still be PENDING). Money is recorded only from a
verified SUCCESS for the order's exact amount and currency, once: one payment, one receipt, one confirmation event, one email.

These tests run the real task body (`_reconcile`) and the real webhook handler against a real PostgreSQL, with Cashfree's HTTP
mocked and real signatures. Synthetic data only.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from modules.internship_onboarding import tasks
from modules.internship_onboarding.models import FinancialDocument, OnboardingEvent, PaymentOrder, PaymentTransaction
from modules.internship_onboarding.payments import RECONCILE_GRACE
from modules.internship_onboarding.service import now
from tests.api.test_internship_onboarding import PUBLIC, configure, settings, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_cashfree import HOOK, journal_entries, queued_emails  # noqa: F401
from tests.api.test_internship_onboarding_payments import gateway, payment_event, ready_to_pay, signed  # noqa: F401
from tests.api.test_internship_onboarding_reconcile_task import task_session  # noqa: F401

pytestmark = pytest.mark.api

ORDER_LIFETIME = timedelta(minutes=30)  # CASHFREE_ORDER_MINUTES


async def new_order(client, auth_headers, db, organization):
    internship, (s0, _) = await world(db, organization)
    await configure(client, auth_headers, internship, fees={"base_amount": "2000", "methods": ["cashfree"]}, payment_accounts={"bank": None})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    return token, order_id


def event(order_id: str, pid: int, status: str, amount: float = 2000.0) -> dict:
    body = payment_event(order_id, status=status, amount=amount, payment_id=pid)
    body["data"]["order"]["order_amount"] = 2000.0
    if status == "USER_DROPPED":
        body["type"] = "PAYMENT_USER_DROPPED_WEBHOOK"
    return body


async def notify(client, body) -> tuple[int, str]:
    raw, headers = signed(body)
    response = await client.post(HOOK, content=raw, headers=headers)
    return response.status_code, response.json()["outcome"]


def attempt(pid: str, status: str, amount: int = 2000, currency: str = "INR") -> dict:
    return {"cf_payment_id": pid, "payment_status": status, "payment_amount": amount, "payment_currency": currency}


async def order_of(db, order_id) -> PaymentOrder:
    row = (await db.execute(select(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id))).scalar_one()
    await db.refresh(row)
    return row


async def state_of(db, queued) -> dict:
    payments = (await db.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalars().all()
    events = (await db.execute(select(OnboardingEvent))).scalars().all()
    return {
        "payments": sorted((p.provider_payment_id, p.status) for p in payments),
        "receipts": (await db.execute(select(func.count(FinancialDocument.id)))).scalar(),
        "confirmed_events": sum(e.event == "payment_confirmed" for e in events),
        "failed_events": sum(e.event == "payment_failed" for e in events),
        "emails": len(queued),
    }


async def age(db, order_id, *, created: timedelta = timedelta(minutes=15), expired_for: timedelta | None = None, unchecked: bool = True):
    """Move an order back in time: created that long ago; expired that long ago if asked, otherwise living its normal lifetime."""
    created_at = now() - created
    values = {"created_at": created_at, "expires_at": (now() - expired_for) if expired_for is not None else created_at + ORDER_LIFETIME}
    if unchecked:
        values["last_checked_at"] = None
    await db.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(**values))


def requests_for(gateway, order_id) -> int:
    return len([r for r in gateway.requests if r.url.path.endswith(f"/orders/{order_id}/payments")])


async def student_payment_status(client, token) -> str:
    return (await client.get(PUBLIC, headers=tok(token))).json()["statuses"]["payment"]


# ------------------------------------------------------------------------------------------------ the notifications


async def test_a_user_dropped_notification_alone_fails_the_attempt_and_nothing_else(client, auth_headers, db_session, organization, storage, gateway, queued_emails):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    entries = await journal_entries(db_session)

    assert await notify(client, event(order_id, 6, "USER_DROPPED")) == (200, "failed")  # acknowledged: Cashfree will not retry it
    order = await order_of(db_session, order_id)
    assert order.status == "failed" and order.paid_at is None
    assert await state_of(db_session, queued_emails) == {"payments": [("6", "failed")], "receipts": 0, "confirmed_events": 0, "failed_events": 1, "emails": 0}
    assert await student_payment_status(client, token) == "failed"  # unpaid, and free to try again
    assert await journal_entries(db_session) == entries

    # the same notification again, and a re-wrapped copy of it: nothing is added
    assert await notify(client, event(order_id, 6, "USER_DROPPED")) == (200, "duplicate")
    assert (await notify(client, {**event(order_id, 6, "USER_DROPPED"), "event_time": "2026-11-03T12:00:00+05:30"}))[1] == "already recorded"
    assert (await state_of(db_session, queued_emails))["payments"] == [("6", "failed")]

    # the student starts a fresh order
    assert (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"] != order_id


async def test_user_dropped_then_success_on_the_same_order_is_paid_once(client, auth_headers, db_session, organization, storage, gateway, queued_emails):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    await notify(client, event(order_id, 6, "USER_DROPPED"))
    assert await notify(client, event(order_id, 9, "SUCCESS")) == (200, "confirmed")
    assert (await order_of(db_session, order_id)).status == "paid"
    assert await state_of(db_session, queued_emails) == {
        "payments": [("6", "failed"), ("9", "confirmed")], "receipts": 1, "confirmed_events": 1, "failed_events": 1, "emails": 1,
    }
    assert await student_payment_status(client, token) == "paid"
    assert await notify(client, event(order_id, 9, "SUCCESS")) == (200, "duplicate")
    assert (await state_of(db_session, queued_emails))["receipts"] == 1


@pytest.mark.parametrize("late_status", ["USER_DROPPED", "FAILED"])
async def test_success_then_a_late_failed_or_dropped_notification_never_reverses_the_payment(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, late_status
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    assert await notify(client, event(order_id, 9, "SUCCESS")) == (200, "confirmed")
    before = await state_of(db_session, queued_emails)

    # a late notification about ANOTHER attempt on the same order: recorded as a failed attempt, the payment stays
    assert await notify(client, event(order_id, 6, late_status)) == (200, "failed")
    after = await state_of(db_session, queued_emails)
    assert (await order_of(db_session, order_id)).status == "paid"
    assert await student_payment_status(client, token) == "paid"
    assert after["receipts"] == before["receipts"] == 1 and after["emails"] == 1 and after["confirmed_events"] == 1
    assert ("9", "confirmed") in after["payments"]

    # a late notification claiming the SAME payment failed cannot flip it either
    assert await notify(client, event(order_id, 9, late_status)) == (200, "already recorded")
    assert ("9", "confirmed") in (await state_of(db_session, queued_emails))["payments"]


# ------------------------------------------------------------------------------------------------ the scheduled task


@pytest.mark.parametrize("first_attempt", ["USER_DROPPED", "FAILED"])
async def test_a_lost_success_after_a_failed_or_dropped_attempt_is_recovered_by_the_scheduled_task(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session, first_attempt
):
    """The defect this fixes: the failed attempt turned the local order into "failed", which scheduled reconciliation ignored."""
    entries = await journal_entries(db_session)
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    await notify(client, event(order_id, 6, first_attempt))  # arrives; the later success notification is lost
    assert (await order_of(db_session, order_id)).status == "failed"
    gateway.payments[order_id] = [attempt("6", first_attempt), attempt("9", "SUCCESS")]
    await age(db_session, order_id, created=timedelta(minutes=15))

    assert await tasks._reconcile() == {"checked": 1, "confirmed": 1}  # nobody pressed anything
    assert requests_for(gateway, order_id) == 1
    assert (await order_of(db_session, order_id)).status == "paid"
    assert await state_of(db_session, queued_emails) == {
        "payments": [("6", "failed"), ("9", "confirmed")], "receipts": 1, "confirmed_events": 1, "failed_events": 1, "emails": 1,
    }
    assert await student_payment_status(client, token) == "paid"
    assert await journal_entries(db_session) == entries

    # later scheduled runs, and the notification that was lost arriving at last, add nothing and ask nothing
    for _ in range(3):
        await age(db_session, order_id, created=timedelta(minutes=40))
        assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert requests_for(gateway, order_id) == 1  # a paid order is final: Cashfree is not asked again
    assert await notify(client, event(order_id, 9, "SUCCESS")) == (200, "already recorded")
    assert (await state_of(db_session, queued_emails))["receipts"] == 1


async def test_a_checkout_closed_before_a_method_is_chosen_records_nothing_and_ends_expired(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    gateway.payments[order_id] = []  # Cashfree has no payment attempt for the order: nothing to report, no notification
    empty = {"payments": [], "receipts": 0, "confirmed_events": 0, "failed_events": 0, "emails": 0}

    await age(db_session, order_id, created=timedelta(minutes=12))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}
    assert (await order_of(db_session, order_id)).status == "active"  # still within its validity: the student may come back
    assert await state_of(db_session, queued_emails) == empty

    await age(db_session, order_id, created=timedelta(minutes=45), expired_for=timedelta(minutes=5))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}
    assert (await order_of(db_session, order_id)).status == "expired"
    assert await state_of(db_session, queued_emails) == empty
    assert await student_payment_status(client, token) != "paid"
    assert (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"] != order_id


async def test_reconciliation_is_bounded_it_waits_between_checks_and_stops_after_the_grace_period(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    await notify(client, event(order_id, 6, "USER_DROPPED"))  # local order "failed"
    gateway.payments[order_id] = [attempt("6", "USER_DROPPED")]

    await age(db_session, order_id, created=timedelta(minutes=15))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}
    assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}  # just checked: not asked again straight away
    assert requests_for(gateway, order_id) == 1
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(last_checked_at=now() - timedelta(minutes=11)))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}  # a check is due again
    assert requests_for(gateway, order_id) == 2
    assert (await state_of(db_session, queued_emails))["payments"] == [("6", "failed")]  # the same dropped attempt is not recorded twice

    # past its expiry and the grace period the order is final: the scheduled task no longer asks Cashfree
    await age(db_session, order_id, created=timedelta(hours=3), expired_for=RECONCILE_GRACE + timedelta(minutes=1))
    assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert requests_for(gateway, order_id) == 2
    assert (await order_of(db_session, order_id)).status == "failed"  # not reopened

    # orders that are paid, only created, or cancelled are never asked about
    for status in ("paid", "created", "cancelled"):
        await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(status=status))
        await age(db_session, order_id, created=timedelta(minutes=15))
        assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert requests_for(gateway, order_id) == 2


async def test_a_pending_attempt_that_succeeds_after_the_order_expired_is_recovered_inside_the_grace_period_only(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    gateway.payments[order_id] = [attempt("9", "PENDING")]  # an attempt started before the order expired, not settled yet

    await age(db_session, order_id, created=timedelta(minutes=35), expired_for=timedelta(minutes=5))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}
    assert (await order_of(db_session, order_id)).status == "expired"
    assert (await state_of(db_session, queued_emails))["payments"] == []  # pending is not paid, and not a failed attempt either

    # the bank settles it a little later, inside the grace period: the scheduled task finds it
    gateway.payments[order_id] = [attempt("9", "SUCCESS")]
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(last_checked_at=now() - timedelta(minutes=11)))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 1}
    assert (await order_of(db_session, order_id)).status == "paid"
    assert (await state_of(db_session, queued_emails))["receipts"] == 1

    # an order whose grace period has passed is not polled any more; a signed notification can still record a late payment
    token2, late_order = await new_order(client, auth_headers, db_session, organization)
    gateway.payments[late_order] = [attempt("11", "SUCCESS")]
    await age(db_session, late_order, created=timedelta(hours=4), expired_for=RECONCILE_GRACE + timedelta(minutes=1))
    # (in real life the first check after its expiry made it "expired"; an "active" order is always checked once, so it can be finalised)
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == late_order).values(status="expired"))
    assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert requests_for(gateway, late_order) == 0
    assert await notify(client, event(late_order, 11, "SUCCESS")) == (200, "confirmed")


@pytest.mark.parametrize("status", ["USER_DROPPED", "FAILED", "CANCELLED", "VOID", "PENDING", "NOT_ATTEMPTED"])
async def test_only_a_verified_success_confirms_a_failed_order_never_these_statuses(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session, status
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    await notify(client, event(order_id, 6, "USER_DROPPED"))
    gateway.payments[order_id] = [attempt("9", status)]
    await age(db_session, order_id, created=timedelta(minutes=15))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}
    assert (await order_of(db_session, order_id)).status == "failed"
    state = await state_of(db_session, queued_emails)
    assert state["receipts"] == 0 and state["emails"] == 0 and state["confirmed_events"] == 0
    assert ("9", "confirmed") not in state["payments"] and await student_payment_status(client, token) != "paid"


@pytest.mark.parametrize("wrong", [attempt("9", "SUCCESS", amount=1999), attempt("9", "SUCCESS", currency="USD")])
async def test_a_success_for_the_wrong_amount_or_currency_does_not_confirm_a_failed_order(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session, wrong
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    await notify(client, event(order_id, 6, "FAILED"))
    gateway.payments[order_id] = [wrong]
    await age(db_session, order_id, created=timedelta(minutes=15))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 0}
    state = await state_of(db_session, queued_emails)
    assert (await order_of(db_session, order_id)).status == "failed" and state["receipts"] == 0 and ("9", "confirmed") not in state["payments"]
    mismatches = (await db_session.execute(select(func.count(OnboardingEvent.id)).where(OnboardingEvent.event == "payment_mismatch"))).scalar()
    assert mismatches == 1  # left for staff, visibly


async def test_the_students_own_status_check_also_covers_failed_and_recently_expired_orders(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails
):
    token, order_id = await new_order(client, auth_headers, db_session, organization)
    await notify(client, event(order_id, 6, "USER_DROPPED"))
    gateway.payments[order_id] = [attempt("6", "USER_DROPPED"), attempt("9", "SUCCESS")]
    out = (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()
    assert out["outcome"] == "confirmed" and out["statuses"]["payment"] == "paid"  # a "failed" order: as before

    token2, expired_order = await new_order(client, auth_headers, db_session, organization)
    gateway.payments[expired_order] = [attempt("12", "SUCCESS")]
    await age(db_session, expired_order, created=timedelta(minutes=40), expired_for=timedelta(minutes=10))
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == expired_order).values(status="expired"))
    out = (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token2))).json()
    assert out["outcome"] == "confirmed"  # an "expired" order inside the grace period: new
    assert (await state_of(db_session, queued_emails))["receipts"] == 2
