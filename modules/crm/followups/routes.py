import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.crm.followups.schemas import (
    FollowUpCompleteRequest,
    FollowUpCreateRequest,
    FollowUpPublic,
    FollowUpUpdateRequest,
    MessageResponse,
)
from modules.crm.followups.service import FollowUpService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post(
    "/leads/{lead_id}/followups", response_model=FollowUpPublic, status_code=status.HTTP_201_CREATED
)
async def create_followup(
    lead_id: uuid.UUID,
    payload: FollowUpCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.followups.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpService(db)
    followup = await service.create_followup(
        lead_id, organization_id, created_by_user_id=user.id, **payload.model_dump()
    )
    return FollowUpPublic.model_validate(followup)


@router.get("/leads/{lead_id}/followups", response_model=list[FollowUpPublic])
async def list_followups(
    lead_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.followups.view")),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpService(db)
    followups = await service.list_followups(lead_id, organization_id)
    return [FollowUpPublic.model_validate(f) for f in followups]


@router.get("/leads/{lead_id}/followups/{followup_id}", response_model=FollowUpPublic)
async def get_followup(
    lead_id: uuid.UUID,
    followup_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.followups.view")),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpService(db)
    followup = await service.get_followup(followup_id, lead_id, organization_id)
    return FollowUpPublic.model_validate(followup)


@router.patch("/leads/{lead_id}/followups/{followup_id}", response_model=FollowUpPublic)
async def update_followup(
    lead_id: uuid.UUID,
    followup_id: uuid.UUID,
    payload: FollowUpUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.followups.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpService(db)
    followup = await service.update_followup(
        followup_id, lead_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return FollowUpPublic.model_validate(followup)


@router.post("/leads/{lead_id}/followups/{followup_id}/complete", response_model=FollowUpPublic)
async def complete_followup(
    lead_id: uuid.UUID,
    followup_id: uuid.UUID,
    payload: FollowUpCompleteRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.followups.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpService(db)
    followup = await service.complete_followup(
        followup_id, lead_id, organization_id, payload.outcome, payload.notes
    )
    return FollowUpPublic.model_validate(followup)


@router.delete("/leads/{lead_id}/followups/{followup_id}", response_model=MessageResponse)
async def delete_followup(
    lead_id: uuid.UUID,
    followup_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.followups.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpService(db)
    await service.delete_followup(followup_id, lead_id, organization_id)
    return MessageResponse(message="Follow-up deleted successfully.")
