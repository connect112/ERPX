import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.announcements.schemas import (
    AnnouncementCreateRequest,
    AnnouncementPublic,
    AnnouncementUpdateRequest,
    MessageResponse,
)
from modules.lms.announcements.service import AnnouncementService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=AnnouncementPublic, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    payload: AnnouncementCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.announcements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = await service.create_announcement(
        organization_id, user.id, payload.course_id, title=payload.title, body=payload.body
    )
    return AnnouncementPublic.model_validate(announcement)


@router.get("", response_model=list[AnnouncementPublic])
async def list_announcements(
    course_id: uuid.UUID | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.announcements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AnnouncementService(db)
    announcements = await service.list_announcements(organization_id, course_id)
    return [AnnouncementPublic.model_validate(a) for a in announcements]


@router.get("/{announcement_id}", response_model=AnnouncementPublic)
async def get_announcement(
    announcement_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.announcements.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = await service.get_announcement(announcement_id, organization_id)
    return AnnouncementPublic.model_validate(announcement)


@router.patch("/{announcement_id}", response_model=AnnouncementPublic)
async def update_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.announcements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AnnouncementService(db)
    announcement = await service.update_announcement(
        announcement_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AnnouncementPublic.model_validate(announcement)


@router.delete("/{announcement_id}", response_model=MessageResponse)
async def delete_announcement(
    announcement_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.announcements.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AnnouncementService(db)
    await service.delete_announcement(announcement_id, organization_id)
    return MessageResponse(message="Announcement deleted successfully.")
