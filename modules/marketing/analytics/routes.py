import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.marketing.analytics.schemas import CampaignPerformanceResponse, MarketingOverviewResponse
from modules.marketing.analytics.service import MarketingAnalyticsService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/overview", response_model=MarketingOverviewResponse)
async def get_marketing_overview(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    service = MarketingAnalyticsService(db)
    overview = await service.marketing_overview(organization_id)
    return MarketingOverviewResponse(**overview)


@router.get("/campaigns/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    campaign_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    service = MarketingAnalyticsService(db)
    performance = await service.campaign_performance(campaign_id, organization_id)
    return CampaignPerformanceResponse(**performance)
