import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.crm.leads.models import LeadStatus
from modules.crm.leads.repository import LeadRepository
from modules.marketing.campaigns.models import CampaignStatus
from modules.marketing.campaigns.repository import CampaignRepository
from modules.marketing.coupons.repository import CouponRedemptionRepository, CouponRepository
from modules.marketing.landing_pages.repository import LandingPageRepository, LandingPageViewRepository
from modules.marketing.referrals.models import ReferralStatus
from modules.marketing.referrals.repository import ReferralRepository


class MarketingAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.campaign_repo = CampaignRepository(db)
        self.lead_repo = LeadRepository(db)
        self.page_repo = LandingPageRepository(db)
        self.view_repo = LandingPageViewRepository(db)
        self.coupon_repo = CouponRepository(db)
        self.redemption_repo = CouponRedemptionRepository(db)
        self.referral_repo = ReferralRepository(db)

    async def campaign_performance(self, campaign_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
        campaign = await self.campaign_repo.get_by_id(campaign_id, organization_id)
        if not campaign:
            raise NotFoundError("Campaign", campaign_id)

        leads, leads_generated = await self.lead_repo.list_for_organization(
            organization_id, campaign_id=campaign_id, skip=0, limit=10_000
        )
        leads_converted = sum(1 for l in leads if l.status == LeadStatus.CONVERTED)
        conversion_rate = round((leads_converted / leads_generated) * 100, 2) if leads_generated > 0 else 0.0

        pages, landing_pages_count = await self.page_repo.list_for_organization(
            organization_id, campaign_id=campaign_id, skip=0, limit=10_000
        )
        landing_page_views = 0
        for page in pages:
            landing_page_views += await self.view_repo.count_for_page(page.id)

        coupons, coupons_count = await self.coupon_repo.list_for_organization(
            organization_id, campaign_id=campaign_id, skip=0, limit=10_000
        )
        coupon_redemptions, coupon_discount_given = await self.redemption_repo.totals_for_coupons(
            [coupon.id for coupon in coupons]
        )

        actual_spend = float(campaign.actual_spend)
        cost_per_lead = round(actual_spend / leads_generated, 2) if leads_generated > 0 else None

        return {
            "campaign_id": campaign_id,
            "leads_generated": leads_generated,
            "leads_converted": leads_converted,
            "conversion_rate_percent": conversion_rate,
            "landing_pages_count": landing_pages_count,
            "landing_page_views": landing_page_views,
            "coupons_count": coupons_count,
            "coupon_redemptions": coupon_redemptions,
            "coupon_discount_given": round(coupon_discount_given, 2),
            "budget_amount": float(campaign.budget_amount) if campaign.budget_amount is not None else None,
            "actual_spend": actual_spend,
            "cost_per_lead": cost_per_lead,
        }

    async def marketing_overview(self, organization_id: uuid.UUID) -> dict:
        campaigns, total_campaigns = await self.campaign_repo.list_for_organization(
            organization_id, skip=0, limit=10_000
        )
        active_campaigns = sum(1 for c in campaigns if c.status == CampaignStatus.ACTIVE)

        total_leads_from_campaigns = 0
        for campaign in campaigns:
            _, count = await self.lead_repo.list_for_organization(
                organization_id, campaign_id=campaign.id, skip=0, limit=1
            )
            total_leads_from_campaigns += count

        pages, _ = await self.page_repo.list_for_organization(organization_id, skip=0, limit=10_000)
        total_landing_page_views = 0
        for page in pages:
            total_landing_page_views += await self.view_repo.count_for_page(page.id)

        coupons, _ = await self.coupon_repo.list_for_organization(organization_id, skip=0, limit=10_000)
        total_coupon_redemptions, total_coupon_discount_given = (
            await self.redemption_repo.totals_for_coupons([coupon.id for coupon in coupons])
        )

        referrals, total_referrals = await self.referral_repo.list_for_organization(
            organization_id, skip=0, limit=10_000
        )
        referrals_converted = sum(
            1 for r in referrals if r.status in (ReferralStatus.CONVERTED, ReferralStatus.REWARDED)
        )
        referrals_rewarded = sum(1 for r in referrals if r.status == ReferralStatus.REWARDED)

        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_leads_from_campaigns": total_leads_from_campaigns,
            "total_landing_page_views": total_landing_page_views,
            "total_coupon_redemptions": total_coupon_redemptions,
            "total_coupon_discount_given": round(total_coupon_discount_given, 2),
            "total_referrals": total_referrals,
            "referrals_converted": referrals_converted,
            "referrals_rewarded": referrals_rewarded,
        }
