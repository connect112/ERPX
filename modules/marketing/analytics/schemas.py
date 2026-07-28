import uuid

from pydantic import BaseModel


class CampaignPerformanceResponse(BaseModel):
    campaign_id: uuid.UUID
    leads_generated: int
    leads_converted: int
    conversion_rate_percent: float
    landing_pages_count: int
    landing_page_views: int
    coupons_count: int
    coupon_redemptions: int
    coupon_discount_given: float
    budget_amount: float | None
    actual_spend: float
    cost_per_lead: float | None


class MarketingOverviewResponse(BaseModel):
    total_campaigns: int
    active_campaigns: int
    total_leads_from_campaigns: int
    total_landing_page_views: int
    total_coupon_redemptions: int
    total_coupon_discount_given: float
    total_referrals: int
    referrals_converted: int
    referrals_rewarded: int


class MessageResponse(BaseModel):
    message: str
