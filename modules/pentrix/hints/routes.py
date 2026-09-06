import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.hints.schemas import (
    HintCreateRequest,
    HintLocked,
    HintPublic,
    HintUnlockResponse,
    UnlockHintRequest,
)
from modules.pentrix.common.dependencies import assert_can_access_student, enforce_own_student_or_staff
from modules.pentrix.hints.service import HintService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/challenges/{challenge_id}/hints", response_model=HintPublic, status_code=status.HTTP_201_CREATED)
async def create_hint(
    challenge_id: uuid.UUID,
    payload: HintCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = HintService(db)
    hint = await service.create_hint(challenge_id, organization_id, **payload.model_dump())
    return HintPublic.model_validate(hint)


@router.get("/challenges/{challenge_id}/hints", response_model=list[HintLocked])
async def list_hints(
    challenge_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.flags.submit")),
    _ownership: None = Depends(enforce_own_student_or_staff),
    db: AsyncSession = Depends(get_db),
):
    service = HintService(db)
    return await service.list_hints_for_student(challenge_id, organization_id, student_id)


@router.post("/hints/{hint_id}/unlock", response_model=HintUnlockResponse)
async def unlock_hint(
    hint_id: uuid.UUID,
    payload: UnlockHintRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.flags.submit")),
    db: AsyncSession = Depends(get_db),
):
    # `student_id` here is body-supplied — check ownership explicitly.
    await assert_can_access_student(payload.student_id, user, db)
    service = HintService(db)
    return await service.unlock_hint(hint_id, organization_id, payload.student_id)
