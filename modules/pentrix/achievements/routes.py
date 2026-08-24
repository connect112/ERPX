import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.achievements.schemas import (
    AchievementCreateRequest,
    AchievementPublic,
    StudentAchievementPublic,
)
from modules.pentrix.achievements.service import AchievementService
from modules.pentrix.common.dependencies import enforce_own_student_or_staff
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=AchievementPublic, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    payload: AchievementCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.achievements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AchievementService(db)
    achievement = await service.create_achievement(organization_id, **payload.model_dump())
    return AchievementPublic.model_validate(achievement)


@router.get("", response_model=list[AchievementPublic])
async def list_achievements(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.achievements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AchievementService(db)
    achievements = await service.list_achievements(organization_id)
    return [AchievementPublic.model_validate(a) for a in achievements]


@router.get("/students/{student_id}", response_model=list[StudentAchievementPublic])
async def list_student_achievements(
    student_id: uuid.UUID,
    user: User = Depends(require_permissions("pentrix.achievements.view")),
    _ownership: None = Depends(enforce_own_student_or_staff),
    db: AsyncSession = Depends(get_db),
):
    service = AchievementService(db)
    achievements = await service.list_for_student(student_id)
    return [StudentAchievementPublic.model_validate(a) for a in achievements]
