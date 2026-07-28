import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.badges.schemas import (
    AwardBadgeRequest,
    BadgeCreateRequest,
    BadgePublic,
    StudentBadgePublic,
)
from modules.lms.badges.service import BadgeService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=BadgePublic, status_code=status.HTTP_201_CREATED)
async def create_badge(
    payload: BadgeCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.badges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BadgeService(db)
    badge = await service.create_badge(organization_id, **payload.model_dump())
    return BadgePublic.model_validate(badge)


@router.get("", response_model=list[BadgePublic])
async def list_badges(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.badges.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BadgeService(db)
    badges = await service.list_badges(organization_id)
    return [BadgePublic.model_validate(b) for b in badges]


@router.post("/award", response_model=StudentBadgePublic, status_code=status.HTTP_201_CREATED)
async def award_badge(
    payload: AwardBadgeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.badges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BadgeService(db)
    award = await service.award_badge(organization_id, payload.student_id, payload.badge_id)
    return StudentBadgePublic.model_validate(award)


@router.get("/by-student/{student_id}", response_model=list[StudentBadgePublic])
async def list_student_badges(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.badges.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BadgeService(db)
    badges = await service.list_student_badges(organization_id, student_id)
    return [StudentBadgePublic.model_validate(b) for b in badges]
