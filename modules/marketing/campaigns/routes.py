import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.marketing.campaigns.models import CampaignChannel, CampaignStatus
from modules.marketing.campaigns.schemas import (
    CampaignCreateRequest,
    CampaignPublic,
    CampaignStatusChangeRequest,
    CampaignUpdateRequest,
    MessageResponse,
)
from modules.marketing.campaigns.service import CampaignService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=CampaignPublic, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.campaigns.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.create_campaign(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return CampaignPublic.model_validate(campaign)


@router.get("", response_model=dict)
async def list_campaigns(
    channel: CampaignChannel | None = None,
    status_filter: CampaignStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaigns, total = await service.list_campaigns(
        organization_id, channel=channel, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [CampaignPublic.model_validate(c) for c in campaigns],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{campaign_id}", response_model=CampaignPublic)
async def get_campaign(
    campaign_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.campaigns.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.get_campaign(campaign_id, organization_id)
    return CampaignPublic.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignPublic)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.campaigns.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.update_campaign(campaign_id, organization_id, **payload.model_dump(exclude_unset=True))
    return CampaignPublic.model_validate(campaign)


@router.post("/{campaign_id}/status", response_model=CampaignPublic)
async def change_campaign_status(
    campaign_id: uuid.UUID,
    payload: CampaignStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.campaigns.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.change_status(campaign_id, organization_id, payload.status)
    return CampaignPublic.model_validate(campaign)
