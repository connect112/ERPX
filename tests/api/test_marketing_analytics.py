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
from modules.marketing.landing_pages.repository import (
    LandingPageRepository,
    LandingPageViewRepository,
)
from modules.marketing.analytics.service import MarketingAnalyticsService

pytestmark = pytest.mark.api


class _TableQueryCounter:
    """Counts statements touching a given table (guards against N+1)."""

    def __init__(self, table: str):
        from app.db.session import engine

        self._engine = engine.sync_engine
        self._table = table
        self.count = 0

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._on)

    def _on(self, conn, cursor, statement, params, context, executemany):
        if self._table in statement.lower():
            self.count += 1


def _RedemptionQueryCounter():
    return _TableQueryCounter("marketing_coupon_redemptions")


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


async def test_totals_for_organization_matches_totals_for_coupons(db_session, organization):
    # The org-scoped join aggregate (used by marketing_overview to avoid
    # materialising the coupon list) must return values identical to the
    # id-list aggregate over every one of the org's coupons.
    await _seed_coupons_with_redemptions(db_session, organization, n_coupons=5, redemptions_each=2)

    coupons, _ = await CouponRepository(db_session).list_for_organization(
        organization.id, skip=0, limit=10_000
    )
    redemption_repo = CouponRedemptionRepository(db_session)
    by_ids = await redemption_repo.totals_for_coupons([c.id for c in coupons])
    by_org = await redemption_repo.totals_for_organization(organization.id)

    assert by_org == by_ids
    assert by_org[0] == 10  # 5 coupons x 2 redemptions


async def test_marketing_overview_no_coupons_returns_zero_totals(db_session, organization):
    with _RedemptionQueryCounter() as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_coupon_redemptions"] == 0
    assert overview["total_coupon_discount_given"] == 0.0
    # The overview's org-scoped redemption aggregate (totals_for_organization)
    # runs once and returns zero — no coupon list is materialised.
    assert counter.count == 1


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


async def _seed_pages_with_views(db_session, organization, *, campaign_id=None, n_pages=4, views_each=3):
    page_repo = LandingPageRepository(db_session)
    view_repo = LandingPageViewRepository(db_session)
    expected_views = 0
    for i in range(n_pages):
        page = await page_repo.create(
            organization_id=organization.id, campaign_id=campaign_id,
            slug=f"page-{uuid.uuid4().hex[:8]}", title=f"Landing {i}", content="body",
        )
        for _ in range(views_each):
            await view_repo.create(
                landing_page_id=page.id, viewed_at=datetime.now(timezone.utc)
            )
            expected_views += 1
    await db_session.flush()
    return expected_views


async def test_marketing_overview_page_views_are_sql_aggregated(db_session, organization):
    expected_views = await _seed_pages_with_views(db_session, organization, n_pages=4, views_each=3)

    with _TableQueryCounter("marketing_landing_page_views") as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_landing_page_views"] == expected_views
    # One grouped COUNT over all pages, not one per page.
    assert counter.count == 1


async def test_marketing_overview_no_pages_zero_views(db_session, organization):
    with _TableQueryCounter("marketing_landing_page_views") as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_landing_page_views"] == 0
    # The overview's org-scoped view aggregate (count_for_organization) runs
    # once and returns zero — no landing-page list is materialised.
    assert counter.count == 1


async def test_view_count_for_organization_matches_count_for_pages(db_session, organization):
    # The org-scoped join aggregate (used by marketing_overview to avoid
    # materialising the page list) must equal the id-list aggregate over every
    # one of the org's pages.
    await _seed_pages_with_views(db_session, organization, n_pages=5, views_each=3)

    pages, _ = await LandingPageRepository(db_session).list_for_organization(
        organization.id, skip=0, limit=10_000
    )
    view_repo = LandingPageViewRepository(db_session)
    by_ids = await view_repo.count_for_pages([p.id for p in pages])
    by_org = await view_repo.count_for_organization(organization.id)

    assert by_org == by_ids == 15  # 5 pages x 3 views


async def test_campaign_performance_page_views_are_sql_aggregated(db_session, organization):
    campaign = await CampaignRepository(db_session).create(
        organization_id=organization.id, campaign_code=f"CMP-{uuid.uuid4().hex[:6]}",
        name="Launch", channel=CampaignChannel.EMAIL, start_date=date(2026, 1, 1),
    )
    expected_views = await _seed_pages_with_views(
        db_session, organization, campaign_id=campaign.id, n_pages=3, views_each=2
    )

    with _TableQueryCounter("marketing_landing_page_views") as counter:
        perf = await MarketingAnalyticsService(db_session).campaign_performance(
            campaign.id, organization.id
        )

    assert perf["landing_page_views"] == expected_views
    assert counter.count == 1


async def _seed_campaigns_with_leads(db_session, organization, *, n_campaigns=4, leads_each=3):
    from modules.crm.leads.models import LeadSource
    from modules.crm.leads.repository import LeadRepository

    campaign_repo = CampaignRepository(db_session)
    lead_repo = LeadRepository(db_session)
    expected = 0
    for i in range(n_campaigns):
        campaign = await campaign_repo.create(
            organization_id=organization.id, campaign_code=f"CMP-{uuid.uuid4().hex[:6]}",
            name=f"Campaign {i}", channel=CampaignChannel.EMAIL, start_date=date(2026, 1, 1),
        )
        for _ in range(leads_each):
            await lead_repo.create(
                organization_id=organization.id, campaign_id=campaign.id,
                full_name="Lead", source=LeadSource.WEBSITE,
            )
            expected += 1
    await db_session.flush()
    return expected


async def test_marketing_overview_campaign_lead_count_is_sql_aggregated(db_session, organization):
    expected_leads = await _seed_campaigns_with_leads(db_session, organization, n_campaigns=4, leads_each=3)

    with _TableQueryCounter("crm_leads") as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_leads_from_campaigns"] == expected_leads
    # One grouped COUNT over all campaigns, not two queries per campaign.
    assert counter.count == 1


async def test_marketing_overview_no_campaigns_zero_leads(db_session, organization):
    with _TableQueryCounter("crm_leads") as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_leads_from_campaigns"] == 0
    # No campaigns -> the aggregate short-circuits without hitting the table.
    assert counter.count == 0


async def _seed_referrals(db_session, organization, counts_by_status):
    from modules.marketing.referrals.models import ReferralStatus
    from modules.marketing.referrals.repository import ReferralProgramRepository, ReferralRepository

    program = await ReferralProgramRepository(db_session).create(
        organization_id=organization.id, name="Prog", code=f"RP-{uuid.uuid4().hex[:6]}",
        referrer_reward_amount=50, valid_from=date(2026, 1, 1),
    )
    repo = ReferralRepository(db_session)
    for status, n in counts_by_status.items():
        for _ in range(n):
            await repo.create(
                organization_id=organization.id, referral_program_id=program.id,
                referee_name="Referee", status=status,
            )
    await db_session.flush()


async def test_marketing_overview_referrals_are_sql_aggregated(db_session, organization):
    from modules.marketing.referrals.models import ReferralStatus

    await _seed_referrals(db_session, organization, {
        ReferralStatus.PENDING: 4,
        ReferralStatus.CONVERTED: 3,
        ReferralStatus.REWARDED: 2,
        ReferralStatus.EXPIRED: 1,
    })

    with _TableQueryCounter("marketing_referrals") as counter:
        overview = await MarketingAnalyticsService(db_session).marketing_overview(organization.id)

    assert overview["total_referrals"] == 10          # 4+3+2+1
    assert overview["referrals_converted"] == 5        # CONVERTED + REWARDED
    assert overview["referrals_rewarded"] == 2
    # One grouped GROUP BY status query, not the list's count + select (2).
    assert counter.count == 1
