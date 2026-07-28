import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.announcements.models import Announcement


class AnnouncementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Announcement:
        announcement = Announcement(**fields)
        self.db.add(announcement)
        await self.db.flush()
        await self.db.refresh(announcement)
        return announcement

    async def get_by_id(self, announcement_id: uuid.UUID, organization_id: uuid.UUID) -> Announcement | None:
        result = await self.db.execute(
            select(Announcement).where(
                Announcement.id == announcement_id, Announcement.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, course_id: uuid.UUID | None = None
    ) -> list[Announcement]:
        conditions = [Announcement.organization_id == organization_id]
        if course_id is not None:
            conditions.append(Announcement.course_id == course_id)
        result = await self.db.execute(
            select(Announcement).where(*conditions).order_by(Announcement.published_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, announcement: Announcement, **fields) -> Announcement:
        for key, value in fields.items():
            if value is not None:
                setattr(announcement, key, value)
        await self.db.flush()
        await self.db.refresh(announcement)
        return announcement

    async def delete(self, announcement: Announcement) -> None:
        await self.db.delete(announcement)
        await self.db.flush()
