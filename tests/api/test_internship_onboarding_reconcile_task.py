"""
The scheduled reconciliation of Cashfree payments (the acceptance test behind `./staging.sh recon`): when neither the webhook
nor the student's status check reaches ERPX, the Celery Beat task `internship_onboarding.reconcile_payments` asks Cashfree
about orders that are still open and confirms a paid one exactly once.

These tests run the real task body (`_reconcile`), the real Beat schedule entry and the real report SQL
(ops/staging-cashfree/recon.sql) against a real PostgreSQL, with Cashfree's HTTP mocked and real signatures. Synthetic data only.
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update

from modules.internship_onboarding.service import now  # the clock the task and the service use
from modules.internship_onboarding import tasks
from modules.internship_onboarding.models import FinancialDocument, OnboardingEvent, PaymentOrder, PaymentTransaction, PaymentWebhookEvent
from tests.api.test_internship_onboarding import PUBLIC, configure, settings, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_cashfree import HOOK, journal_entries, queued_emails  # noqa: F401
from tests.api.test_internship_onboarding_payments import gateway, payment_event, ready_to_pay, signed  # noqa: F401

pytestmark = pytest.mark.api

RECON_SQL = Path(__file__).resolve().parents[2] / "ops" / "staging-cashfree" / "recon.sql"


def test_the_beat_schedule_and_the_worker_registration_of_the_reconciliation_task():
    from app.core.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["internship-onboarding-reconcile-payments"]
    assert entry["task"] == "internship_onboarding.reconcile_payments"
    assert entry["schedule"].minute == set(range(0, 60, 15))  # :00, :15, :30, :45 (UTC, the app's timezone)
    assert celery_app.conf.timezone == "UTC"
    celery_app.loader.import_default_modules()  # what a worker does at start
    assert "internship_onboarding.reconcile_payments" in celery_app.tasks
    # nothing routes the task to a queue the staging worker does not consume
    assert not (celery_app.conf.task_routes or {}).get("internship_onboarding.reconcile_payments")


@pytest.fixture
def task_session(db_session, monkeypatch):
    """The task opens its own sessions; give it the test's transaction instead (same code, same database)."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def context():
        yield db_session
        await db_session.flush()

    monkeypatch.setattr(tasks, "get_db_context", context)
    return db_session


async def counts(db, queued):
    payments = (await db.execute(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.kind == "payment"))).scalar()
    documents = (await db.execute(select(func.count(FinancialDocument.id)))).scalar()
    webhooks = (await db.execute(select(func.count(PaymentWebhookEvent.id)))).scalar()
    return payments, documents, webhooks, len(queued)


async def lost_webhook_order(client, auth_headers, db, organization, gateway):
    """A student starts checkout and pays at Cashfree; no notification and no status check ever reaches ERPX."""
    internship, (s0, _) = await world(db, organization)
    await configure(client, auth_headers, internship, fees={"base_amount": "2000", "methods": ["cashfree"]}, payment_accounts={"bank": None})
    token = await ready_to_pay(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    gateway.payments[order_id] = [{"cf_payment_id": "888", "payment_status": "SUCCESS", "payment_amount": 2000, "payment_currency": "INR"}]
    return token, order_id


def payment_checks(gateway, order_id):
    return [r for r in gateway.requests if r.url.path.endswith(f"/orders/{order_id}/payments")]


async def test_the_scheduled_task_confirms_a_lost_webhook_payment_once_and_only_when_the_order_is_old_enough(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session
):
    entries_before = await journal_entries(db_session)
    _, order_id = await lost_webhook_order(client, auth_headers, db_session, organization, gateway)

    # a minute after checkout the task does not touch the order: it only looks at orders open for more than 10 minutes
    assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert payment_checks(gateway, order_id) == []
    assert await counts(db_session, queued_emails) == (0, 0, 0, 0)

    # 11 minutes later the scheduled run asks Cashfree, sees the successful payment and confirms it
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(created_at=now() - timedelta(minutes=11)))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 1}
    assert len(payment_checks(gateway, order_id)) == 1  # verified through Cashfree's API, not assumed
    order = (await db_session.execute(select(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id))).scalar_one()
    assert order.status == "paid" and order.paid_at is not None and order.last_checked_at is not None
    assert await counts(db_session, queued_emails) == (1, 1, 0, 1)  # one payment, one receipt, no notification, one email
    event = (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.event == "payment_confirmed"))).scalar_one()
    assert event.detail["source"] == "status check" and event.actor == "system"
    assert await journal_entries(db_session) == entries_before

    # the next scheduled run finds nothing open: nothing is asked, nothing changes
    assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert len(payment_checks(gateway, order_id)) == 1
    assert await counts(db_session, queued_emails) == (1, 1, 0, 1)

    # the notification that was refused earlier arrives now: acknowledged, nothing is added
    success = payment_event(order_id, amount=2000.0, payment_id=888)
    success["data"]["order"]["order_amount"] = 2000.0
    raw, sig = signed(success)
    assert (await client.post(HOOK, content=raw, headers=sig)).json()["outcome"] == "already recorded"
    assert await counts(db_session, queued_emails) == (1, 1, 1, 1)


async def test_the_task_does_nothing_unless_cashfree_is_enabled(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session, monkeypatch
):
    from app.core.config import settings as app_settings

    _, order_id = await lost_webhook_order(client, auth_headers, db_session, organization, gateway)
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(created_at=now() - timedelta(minutes=11)))
    monkeypatch.setattr(app_settings, "CASHFREE_ENABLED", False)
    assert await tasks._reconcile() == {"checked": 0, "confirmed": 0}
    assert payment_checks(gateway, order_id) == [] and await counts(db_session, queued_emails) == (0, 0, 0, 0)


def recon_rows(sql: str):
    """recon.sql is written for psql (`:'name'` variables, backslash commands); the same SELECT runs here with bind parameters."""
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("\\"))
    return text(re.sub(r":'(\w+)'", r":\1", body))


async def run_recon_sql(db, **variables) -> dict[str, str]:
    rows = (await db.execute(recon_rows(RECON_SQL.read_text()), variables)).all()
    return {key: value for key, value in rows}


async def test_the_report_sql_proves_the_scheduled_run_did_it_and_catches_contamination(
    client, auth_headers, db_session, organization, storage, gateway, queued_emails, task_session
):
    entries_before = await journal_entries(db_session)
    token, order_id = await lost_webhook_order(client, auth_headers, db_session, organization, gateway)
    started = now() - timedelta(hours=2)
    await db_session.execute(update(PaymentOrder).where(PaymentOrder.merchant_order_id == order_id).values(created_at=now() - timedelta(minutes=11)))
    assert await tasks._reconcile() == {"checked": 1, "confirmed": 1}
    confirmed_at = (await db_session.execute(select(OnboardingEvent.created_at).where(OnboardingEvent.event == "payment_confirmed"))).scalar_one()
    reference = (await db_session.execute(text("SELECT reference FROM internship_onboarding_applications LIMIT 1"))).scalar_one()
    since, task_ok = started.isoformat(), confirmed_at.isoformat()

    facts = await run_recon_sql(db_session, app=reference, since=since, task_ok=task_ok)
    assert facts["fact.order"] == order_id and facts["fact.order_status"] == "paid"
    assert facts["fact.confirmed_payments"] == "1" and facts["fact.receipts"] == "1" and facts["fact.confirmed_events"] == "1"
    assert facts["fact.cashfree_payment_id"] == "888" and facts["fact.confirmed_event_source"] == "status check"
    assert facts["fact.notifications_that_reached_erpx"] == "0"
    assert [k for k, v in facts.items() if k.startswith("check.") and v != "true"] == []
    integrity = {k: v for k, v in facts.items() if k.startswith("integrity.")}
    assert len(integrity) == 5 and all(v == "0" for k, v in integrity.items() if k != "integrity.accounting_journal_entries")
    assert integrity["integrity.accounting_journal_entries"] == str(entries_before)

    # without an application reference the latest Cashfree order since the mode went on is used
    assert (await run_recon_sql(db_session, app="", since=since, task_ok=task_ok))["fact.order"] == order_id
    assert (await run_recon_sql(db_session, app="", since=now().isoformat(), task_ok=task_ok))["fact.order"] == "NONE"

    # each way the evidence can be missing is reported as not true, never assumed
    assert (await run_recon_sql(db_session, app=reference, since=since, task_ok=""))["check.confirmation_inside_scheduled_task_run"] == "false"
    far = (confirmed_at - timedelta(minutes=10)).isoformat()
    assert (await run_recon_sql(db_session, app=reference, since=since, task_ok=far))["check.confirmation_inside_scheduled_task_run"] == "false"
    late = now().isoformat()  # the test mode went on after checkout started: not isolated
    assert (await run_recon_sql(db_session, app=reference, since=late, task_ok=task_ok))["check.test_mode_was_on_before_checkout"] == "false"

    # a notification that reached ERPX (the gateway should have refused it) invalidates the isolation
    success = payment_event(order_id, amount=2000.0, payment_id=888)
    success["data"]["order"]["order_amount"] = 2000.0
    raw, sig = signed(success)
    await client.post(HOOK, content=raw, headers=sig)
    contaminated = await run_recon_sql(db_session, app=reference, since=since, task_ok=task_ok)
    assert contaminated["fact.notifications_that_reached_erpx"] == "1" and contaminated["check.no_notification_reached_erpx"] == "false"
