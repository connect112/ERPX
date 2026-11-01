"""
Opt-in checks of the Cashfree adapter against the real Cashfree SANDBOX (test money only). Skipped unless
CASHFREE_SANDBOX_TESTS=1 and sandbox keys are in the environment (CASHFREE_APP_ID, CASHFREE_SECRET_KEY: environment
secrets, never in the repository or a chat). They always use the sandbox host and refuse to run otherwise.

    CASHFREE_SANDBOX_TESTS=1 pytest tests/sandbox -q

After paying one order by hand on the sandbox checkout page with a sandbox test instrument:
    CASHFREE_SANDBOX_PAID_ORDER_ID=<order id>   the status check sees that payment as a success
    CASHFREE_SANDBOX_REFUND=1                   also refunds 1.00 of it and reads the refund back
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from modules.internship_onboarding import fees as fee_maths
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.providers.base import ProviderError
from modules.internship_onboarding.providers.cashfree import BASE_URLS, CashfreeProvider

APP_ID, SECRET = os.environ.get("CASHFREE_APP_ID", ""), os.environ.get("CASHFREE_SECRET_KEY", "")
VERSION = os.environ.get("CASHFREE_API_VERSION", "2025-01-01")
PAID_ORDER = os.environ.get("CASHFREE_SANDBOX_PAID_ORDER_ID", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("CASHFREE_SANDBOX_TESTS") != "1" or not APP_ID or not SECRET,
                       reason="Cashfree sandbox tests are opt-in (CASHFREE_SANDBOX_TESTS=1 and sandbox keys)"),
    pytest.mark.skipif(os.environ.get("CASHFREE_ENV", "sandbox") != "sandbox", reason="never against production"),
]  # fmt: skip


@pytest.fixture
def provider() -> CashfreeProvider:
    assert BASE_URLS["sandbox"].startswith("https://sandbox.cashfree.com/")
    return CashfreeProvider(APP_ID, SECRET, "sandbox", VERSION)


def configured_fee() -> Decimal:
    """What a student owes under the default internship settings (INR 2,000), computed the way the app does."""
    return fee_maths.total_of(fee_maths.snapshot(OnboardingConfig().fees))


async def new_order(provider: CashfreeProvider, order_id: str | None = None):
    order_id = order_id or f"ERPXSBX{secrets.token_hex(8).upper()}"
    created = await provider.create_order(
        merchant_order_id=order_id, amount=configured_fee(), currency="INR", customer_id="ERPX-SANDBOX-TEST",
        customer_name="Sandbox Test", customer_email="sandbox-test@example.com", customer_phone="9999999999",
        return_url=f"https://example.com/internship-onboarding?order={order_id}",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30), note="ERPX sandbox test",
    )  # fmt: skip
    return order_id, created


async def test_an_order_for_the_configured_fee_gets_a_payment_session(provider):
    assert configured_fee() == Decimal("2000.00")
    order_id, created = await new_order(provider)
    assert created.payment_session_id and created.provider_order_id
    assert await provider.order_payments(order_id) == []  # nothing paid yet


async def test_an_order_id_cannot_be_used_twice(provider):
    order_id, _ = await new_order(provider)
    with pytest.raises(ProviderError):
        await new_order(provider, order_id)


async def test_an_unpaid_order_cannot_be_refunded(provider):
    order_id, _ = await new_order(provider)
    with pytest.raises(ProviderError):
        await provider.create_refund(order_id, f"RFSBX{secrets.token_hex(8)}", Decimal("1.00"), "ERPX sandbox test")


async def test_wrong_keys_are_refused_without_the_secret_appearing_anywhere():
    wrong = "wrong-secret-" + secrets.token_hex(4)
    bad = CashfreeProvider(APP_ID, wrong, "sandbox", VERSION)
    with pytest.raises(ProviderError) as caught:
        await new_order(bad)
    assert wrong not in str(caught.value) and wrong not in repr(bad)


@pytest.mark.skipif(not PAID_ORDER, reason="set CASHFREE_SANDBOX_PAID_ORDER_ID to an order paid on the sandbox checkout")
async def test_a_sandbox_payment_is_seen_by_the_status_check(provider):
    payments = await provider.order_payments(PAID_ORDER)
    success = [p for p in payments if p.status == "success"]
    assert success and success[0].currency == "INR" and success[0].amount > 0


@pytest.mark.skipif(not PAID_ORDER or os.environ.get("CASHFREE_SANDBOX_REFUND") != "1", reason="refund round trip is opt-in")
async def test_a_sandbox_refund_round_trip(provider):
    refund_id = f"RFSBX{secrets.token_hex(8)}"
    created = await provider.create_refund(PAID_ORDER, refund_id, Decimal("1.00"), "ERPX sandbox test")
    assert created.refund_id == refund_id and created.status in ("pending", "success")
    again = await provider.refund_status(PAID_ORDER, refund_id)
    assert again.refund_id == refund_id and again.amount == Decimal("1.00")
