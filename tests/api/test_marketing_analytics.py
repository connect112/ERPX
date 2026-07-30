"""
API/service tests for Marketing Analytics aggregates.

Focuses on the coupon redemption/discount totals, which are aggregated in
SQL (`CouponRedemptionRepository.totals_for_coupons`) rather than looped
per coupon. Each test both asserts the returned totals equal the manual
sum of the seeded redemptions (behaviour) and pins the redemption-table
query count to a single grouped query (guards against N+1 reintroduction).
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import event

from modules.marketing.campaigns.models import CampaignChannel
from modules.marketing.campaigns.repository import CampaignRepository
from modules.marketing.coupons.models import CouponDiscountType
from modules.marketing.coupons.repository import CouponRedemptionRepository, CouponRepository
from modules.marketing.analytics.service import MarketingAnalyticsService

pytestmark = pytest.mark.api


class _RedemptionQueryCounter:
    """Counts statements touching the coupon-redemptions table."""

    def __init__(self):
        from app.db.session import engine

        self._engine = engine.sync_engine
        self.count = 0

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._on)

    def _on(self, conn, cursor, statement, params, context, executemany):
        if "marketing_coupon_redemptions" in statement.lower():
            self.count += 1


async def _seed_coupons_with_redemptions(
    db_session, organization, *, campaign_id=None, n_coupons=4, redemptions_each=3
):
    coupon_repo = CouponRepository(db_session)
    redemption_repo = CouponRedemptionRepository(db_session)
    expected_redemptions = 0
    expected_discount = 0.0
    for i in range(n_coupons):
        coupon = await coupon_repo.create(
            organization_id=organization.id,
            campaign_id=campaign_id,
            code=f"C{i}-{uuid.uuid4().hex[:6]}",
            discount_type=CouponDiscountType.FIXED_AMOUNT,
            discount_value=10,
            valid_from=date(2026, 1, 1),
            valid_until=date(2026, 12, 31),
        )
        for j in range(redemptions_each):
            await redemption_repo.create(
                coupon_id=coupon.id,
                redeemed_by_reference=f"user{j}@example.com",
                order_amount=100,
                discount_amount_applied=10 + j,
                redeemed_at=datetime.now(timezone.utc),
            )
            expected_redemptions += 1
            expected_discount += 10 + j
    await db_session.flush()
    return expected_redemptions, round(expected_discount, 2)


async def test_marketing_overview_coupon_totals_are_sql_aggregated(db_session, organization):
    expected_redemptions, expected_discount = await _seed_coupons_with_redemptions(
        db_session, organization, n_coupons=4, redemptions_each=3
    )

    with _RedemptionQueryCounter() as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_coupon_redemptions"] == expected_redemptions
    assert overview["total_coupon_discount_given"] == expected_discount
    # One grouped aggregate query, not 2 per coupon.
    assert counter.count == 1


async def test_marketing_overview_no_coupons_returns_zero_totals(db_session, organization):
    with _RedemptionQueryCounter() as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_coupon_redemptions"] == 0
    assert overview["total_coupon_discount_given"] == 0.0
    # No coupons -> the aggregate short-circuits without hitting the table.
    assert counter.count == 0


async def test_campaign_performance_coupon_totals_are_sql_aggregated(db_session, organization):
    campaign = await CampaignRepository(db_session).create(
        organization_id=organization.id,
        campaign_code=f"CMP-{uuid.uuid4().hex[:6]}",
        name="Summer Drive",
        channel=CampaignChannel.EMAIL,
        start_date=date(2026, 1, 1),
    )
    expected_redemptions, expected_discount = await _seed_coupons_with_redemptions(
        db_session, organization, campaign_id=campaign.id, n_coupons=3, redemptions_each=2
    )

    with _RedemptionQueryCounter() as counter:
        perf = await MarketingAnalyticsService(db_session).campaign_performance(
            campaign.id, organization.id
        )

    assert perf["coupon_redemptions"] == expected_redemptions
    assert perf["coupon_discount_given"] == expected_discount
    assert counter.count == 1
