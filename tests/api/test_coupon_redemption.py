"""
Regression tests for the coupon usage-limit TOCTOU (finding #23).

`CouponService.redeem_coupon` did a live "count redemptions, then insert"
with no locking, so two concurrent redemptions of a single-use coupon could
both read count==0 and both insert — redeeming the coupon past its
`usage_limit_total`. The fix takes a `SELECT ... FOR UPDATE` lock on the
coupon row at the start of `redeem_coupon`, serializing redemptions of the
same code.

A true wall-clock race is not deterministically reproducible in a single
event loop, so the mechanism is pinned deterministically instead: the redeem
path must emit a `SELECT ... FOR UPDATE` on the coupon row (removing the lock
makes `test_redeem_takes_for_update_lock_on_coupon` fail), and the underlying
usage-limit enforcement is exercised sequentially.

They manage their own committed data (outside the rolled-back `db_session`
fixture) and clean it up.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import delete, event

from app.core.exceptions import ValidationError
from app.db.session import AsyncSessionLocal, engine
from modules.marketing.coupons.models import Coupon, CouponDiscountType
from modules.marketing.coupons.repository import CouponRedemptionRepository, CouponRepository
from modules.marketing.coupons.service import CouponService
from modules.organizations.models import Organization

pytestmark = pytest.mark.api


async def _make_coupon(org_id: uuid.UUID, code: str, *, usage_limit_total: int | None = 1) -> None:
    async with AsyncSessionLocal() as setup:
        setup.add(Organization(id=org_id, name="Race Org", slug=f"race-{uuid.uuid4().hex[:10]}"))
        await setup.flush()
        setup.add(
            Coupon(
                organization_id=org_id,
                code=code,
                discount_type=CouponDiscountType.FIXED_AMOUNT,
                discount_value=10,
                valid_from=date(2026, 1, 1),
                valid_until=date(2026, 12, 31),
                usage_limit_total=usage_limit_total,
                usage_limit_per_customer=5,
            )
        )
        await setup.commit()


async def _cleanup(org_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as cleanup:
        await cleanup.execute(delete(Coupon).where(Coupon.organization_id == org_id))
        await cleanup.execute(delete(Organization).where(Organization.id == org_id))
        await cleanup.commit()


async def test_redeem_takes_for_update_lock_on_coupon():
    await engine.dispose()
    org_id = uuid.uuid4()
    code = f"LOCK-{uuid.uuid4().hex[:8].upper()}"
    await _make_coupon(org_id, code)

    statements: list[str] = []

    def _capture(conn, cursor, statement, params, context, executemany):
        statements.append(statement.lower())

    try:
        async with AsyncSessionLocal() as session:
            event.listen(engine.sync_engine, "before_cursor_execute", _capture)
            try:
                await CouponService(session).redeem_coupon(
                    org_id, code=code, order_amount=100.0, customer_reference="a@example.com"
                )
                await session.commit()
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", _capture)

        locked = [s for s in statements if "marketing_coupons" in s and "for update" in s]
        assert locked, "redeem_coupon must SELECT ... FOR UPDATE the coupon row"
    finally:
        await _cleanup(org_id)
        await engine.dispose()


async def test_usage_limit_total_is_enforced():
    await engine.dispose()
    org_id = uuid.uuid4()
    code = f"LIMIT-{uuid.uuid4().hex[:8].upper()}"
    await _make_coupon(org_id, code, usage_limit_total=1)

    try:
        async with AsyncSessionLocal() as session:
            service = CouponService(session)
            # First redemption succeeds and is committed.
            await service.redeem_coupon(
                org_id, code=code, order_amount=100.0, customer_reference="a@example.com"
            )
            await session.commit()

            # A second redemption (even a different customer) is rejected on the
            # total limit, and no extra redemption row is written.
            with pytest.raises(ValidationError):
                await service.redeem_coupon(
                    org_id, code=code, order_amount=100.0, customer_reference="b@example.com"
                )
            await session.rollback()

            coupon = await CouponRepository(session).get_by_code(org_id, code)
            assert await CouponRedemptionRepository(session).count_for_coupon(coupon.id) == 1
    finally:
        await _cleanup(org_id)
        await engine.dispose()
