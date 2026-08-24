import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.achievements.service import AchievementService
from modules.pentrix.flags.schemas import (
    FlagPublic,
    SetFlagRequest,
    SolvePublic,
    SubmissionResultResponse,
    SubmitFlagRequest,
)
from modules.pentrix.common.dependencies import assert_can_access_student, enforce_own_student_or_staff
from modules.pentrix.flags.service import FlagService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.put("/challenges/{challenge_id}/flag", response_model=FlagPublic)
async def set_flag(
    challenge_id: uuid.UUID,
    payload: SetFlagRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = FlagService(db)
    flag = await service.set_flag(challenge_id, organization_id, payload.flag_value)
    return FlagPublic.model_validate(flag)


@router.post("/challenges/{challenge_id}/submit", response_model=SubmissionResultResponse)
async def submit_flag(
    challenge_id: uuid.UUID,
    payload: SubmitFlagRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.flags.submit")),
    db: AsyncSession = Depends(get_db),
):
    # `student_id` here is body-supplied — check ownership explicitly before
    # crediting a solve to it (see `assert_can_access_student` docstring).
    await assert_can_access_student(payload.student_id, user, db)
    flag_service = FlagService(db)
    result = await flag_service.submit(
        challenge_id, organization_id, payload.student_id, payload.flag_value
    )

    # A correct, first-time solve may unlock one or more achievements —
    # checked here in the route layer rather than inside FlagService, to
    # avoid a circular dependency between the flags and achievements
    # services (achievements already reads submission data from flags).
    if result.correct and not result.already_solved:
        await AchievementService(db).check_and_award(payload.student_id, organization_id)

    return result


@router.get("/students/{student_id}/solves", response_model=list[SolvePublic])
async def list_solves(
    student_id: uuid.UUID,
    user: User = Depends(require_permissions("pentrix.flags.submit")),
    _ownership: None = Depends(enforce_own_student_or_staff),
    db: AsyncSession = Depends(get_db),
):
    service = FlagService(db)
    solves = await service.list_solves_for_student(student_id)
    return [SolvePublic.model_validate(s) for s in solves]
