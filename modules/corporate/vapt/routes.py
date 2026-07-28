import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.vapt.models import FindingStatus
from modules.corporate.vapt.schemas import (
    MessageResponse,
    VAPTEngagementCreateRequest,
    VAPTEngagementPublic,
    VAPTEngagementUpdateRequest,
    VAPTFindingCreateRequest,
    VAPTFindingPublic,
    VAPTFindingsSummaryResponse,
    VAPTFindingUpdateRequest,
)
from modules.corporate.vapt.service import VAPTEngagementService, VAPTFindingService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/engagements", response_model=VAPTEngagementPublic, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    payload: VAPTEngagementCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTEngagementService(db)
    engagement = await service.create_engagement(organization_id, **payload.model_dump())
    return VAPTEngagementPublic.model_validate(engagement)


@router.get("/engagements/projects/{project_id}", response_model=list[VAPTEngagementPublic])
async def list_engagements_for_project(
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTEngagementService(db)
    engagements = await service.list_for_project(project_id, organization_id)
    return [VAPTEngagementPublic.model_validate(e) for e in engagements]


@router.get("/engagements/{engagement_id}", response_model=VAPTEngagementPublic)
async def get_engagement(
    engagement_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTEngagementService(db)
    engagement = await service.get_engagement(engagement_id, organization_id)
    return VAPTEngagementPublic.model_validate(engagement)


@router.patch("/engagements/{engagement_id}", response_model=VAPTEngagementPublic)
async def update_engagement(
    engagement_id: uuid.UUID,
    payload: VAPTEngagementUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTEngagementService(db)
    engagement = await service.update_engagement(
        engagement_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return VAPTEngagementPublic.model_validate(engagement)


@router.get("/engagements/{engagement_id}/summary", response_model=VAPTFindingsSummaryResponse)
async def get_findings_summary(
    engagement_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTFindingService(db)
    summary = await service.get_summary(engagement_id, organization_id)
    return VAPTFindingsSummaryResponse(**summary)


@router.post(
    "/engagements/{engagement_id}/findings", response_model=VAPTFindingPublic, status_code=status.HTTP_201_CREATED
)
async def create_finding(
    engagement_id: uuid.UUID,
    payload: VAPTFindingCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTFindingService(db)
    finding = await service.create_finding(engagement_id, organization_id, **payload.model_dump())
    return VAPTFindingPublic.model_validate(finding)


@router.get("/engagements/{engagement_id}/findings", response_model=list[VAPTFindingPublic])
async def list_findings(
    engagement_id: uuid.UUID,
    status_filter: FindingStatus | None = Query(default=None, alias="status"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.vapt.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTFindingService(db)
    findings = await service.list_findings(engagement_id, organization_id, status_filter)
    return [VAPTFindingPublic.model_validate(f) for f in findings]


@router.patch("/findings/{finding_id}", response_model=VAPTFindingPublic)
async def update_finding(
    finding_id: uuid.UUID,
    payload: VAPTFindingUpdateRequest,
    user: User = Depends(require_permissions("corporate.vapt.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VAPTFindingService(db)
    finding = await service.update_finding(finding_id, **payload.model_dump(exclude_unset=True))
    return VAPTFindingPublic.model_validate(finding)
