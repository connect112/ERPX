import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.announcements.models import Announcement
from modules.lms.announcements.repository import AnnouncementRepository

logger = get_logger(__name__)


class AnnouncementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AnnouncementRepository(db)
        self.course_repo = CourseRepository(db)

    async def create_announcement(
        self, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, course_id: uuid.UUID | None, **fields
    ) -> Announcement:
        if course_id is not None:
            course = await self.course_repo.get_by_id(course_id, organization_id)
            if not course:
                raise NotFoundError("Course", course_id)

        announcement = await self.repo.create(
            organization_id=organization_id,
            course_id=course_id,
            created_by_user_id=created_by_user_id,
            **fields,
        )
        logger.info("announcement_created", announcement_id=str(announcement.id))
        return announcement

    async def get_announcement(self, announcement_id: uuid.UUID, organization_id: uuid.UUID) -> Announcement:
        announcement = await self.repo.get_by_id(announcement_id, organization_id)
        if not announcement:
            raise NotFoundError("Announcement", announcement_id)
        return announcement

    async def list_announcements(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None
    ) -> list[Announcement]:
        return await self.repo.list_for_organization(organization_id, course_id)

    async def update_announcement(
        self, announcement_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Announcement:
        announcement = await self.get_announcement(announcement_id, organization_id)
        updated = await self.repo.update(announcement, **fields)
        logger.info("announcement_updated", announcement_id=str(announcement_id))
        return updated

    async def delete_announcement(self, announcement_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        announcement = await self.get_announcement(announcement_id, organization_id)
        await self.repo.delete(announcement)
        logger.info("announcement_deleted", announcement_id=str(announcement_id))
