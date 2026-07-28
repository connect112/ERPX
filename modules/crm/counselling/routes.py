import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.crm.counselling.schemas import (
    CounsellingCompleteRequest,
    CounsellingCreateRequest,
    CounsellingPublic,
    CounsellingUpdateRequest,
    MessageResponse,
)
from modules.crm.counselling.service import CounsellingService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post(
    "/leads/{lead_id}/counselling",
    response_model=CounsellingPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_counselling_session(
    lead_id: uuid.UUID,
    payload: CounsellingCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.counselling.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CounsellingService(db)
    session = await service.create_session(lead_id, organization_id, **payload.model_dump())
    return CounsellingPublic.model_validate(session)


@router.get("/leads/{lead_id}/counselling", response_model=list[CounsellingPublic])
async def list_counselling_sessions(
    lead_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.counselling.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CounsellingService(db)
    sessions = await service.list_sessions(lead_id, organization_id)
    return [CounsellingPublic.model_validate(s) for s in sessions]


@router.get("/leads/{lead_id}/counselling/{session_id}", response_model=CounsellingPublic)
async def get_counselling_session(
    lead_id: uuid.UUID,
    session_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.counselling.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CounsellingService(db)
    session = await service.get_session(session_id, lead_id, organization_id)
    return CounsellingPublic.model_validate(session)


@router.patch("/leads/{lead_id}/counselling/{session_id}", response_model=CounsellingPublic)
async def update_counselling_session(
    lead_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: CounsellingUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.counselling.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CounsellingService(db)
    session = await service.update_session(
        session_id, lead_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return CounsellingPublic.model_validate(session)


@router.post("/leads/{lead_id}/counselling/{session_id}/complete", response_model=CounsellingPublic)
async def complete_counselling_session(
    lead_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: CounsellingCompleteRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.counselling.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CounsellingService(db)
    session = await service.complete_session(
        session_id, lead_id, organization_id, payload.recommended_course, payload.notes
    )
    return CounsellingPublic.model_validate(session)


@router.delete("/leads/{lead_id}/counselling/{session_id}", response_model=MessageResponse)
async def delete_counselling_session(
    lead_id: uuid.UUID,
    session_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.counselling.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CounsellingService(db)
    await service.delete_session(session_id, lead_id, organization_id)
    return MessageResponse(message="Counselling session deleted successfully.")
