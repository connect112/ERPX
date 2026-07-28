"""
Marketing module — top-level router aggregator.

Mounted at /marketing.
"""

from fastapi import APIRouter

from modules.marketing.analytics.routes import router as analytics_router
from modules.marketing.campaigns.routes import router as campaigns_router
from modules.marketing.coupons.routes import router as coupons_router
from modules.marketing.landing_pages.routes import router as landing_pages_router
from modules.marketing.referrals.routes import router as referrals_router

router = APIRouter()

router.include_router(campaigns_router, prefix="/campaigns", tags=["Marketing - Campaigns"])
router.include_router(landing_pages_router, prefix="/landing-pages", tags=["Marketing - Landing Pages"])
router.include_router(coupons_router, prefix="/coupons", tags=["Marketing - Coupons"])
router.include_router(referrals_router, prefix="/referrals", tags=["Marketing - Referrals"])
router.include_router(analytics_router, prefix="/analytics", tags=["Marketing - Analytics"])
