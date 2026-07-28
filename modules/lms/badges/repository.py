import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.lms.badges.models import Badge, StudentBadge


class BadgeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Badge:
        badge = Badge(**fields)
        self.db.add(badge)
        await self.db.flush()
        await self.db.refresh(badge)
        return badge

    async def get_by_id(self, badge_id: uuid.UUID, organization_id: uuid.UUID) -> Badge | None:
        result = await self.db.execute(
            select(Badge).where(Badge.id == badge_id, Badge.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Badge]:
        result = await self.db.execute(select(Badge).where(Badge.organization_id == organization_id))
        return list(result.scalars().all())

    async def award(self, student_id: uuid.UUID, badge_id: uuid.UUID) -> StudentBadge:
        record = StudentBadge(student_id=student_id, badge_id=badge_id)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_award(self, student_id: uuid.UUID, badge_id: uuid.UUID) -> StudentBadge | None:
        result = await self.db.execute(
            select(StudentBadge).where(
                StudentBadge.student_id == student_id, StudentBadge.badge_id == badge_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[StudentBadge]:
        result = await self.db.execute(
            select(StudentBadge).where(StudentBadge.student_id == student_id)
        )
        return list(result.scalars().all())
