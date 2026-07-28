import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.achievements.models import Achievement, StudentAchievement


class AchievementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Achievement:
        achievement = Achievement(**fields)
        self.db.add(achievement)
        await self.db.flush()
        await self.db.refresh(achievement)
        return achievement

    async def get_by_id(self, achievement_id: uuid.UUID, organization_id: uuid.UUID) -> Achievement | None:
        result = await self.db.execute(
            select(Achievement).where(
                Achievement.id == achievement_id, Achievement.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Achievement]:
        result = await self.db.execute(
            select(Achievement).where(Achievement.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def has_award(self, student_id: uuid.UUID, achievement_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(StudentAchievement).where(
                StudentAchievement.student_id == student_id,
                StudentAchievement.achievement_id == achievement_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def award(self, student_id: uuid.UUID, achievement_id: uuid.UUID) -> StudentAchievement:
        award = StudentAchievement(student_id=student_id, achievement_id=achievement_id)
        self.db.add(award)
        await self.db.flush()
        await self.db.refresh(award)
        return award

    async def list_for_student(self, student_id: uuid.UUID) -> list[StudentAchievement]:
        result = await self.db.execute(
            select(StudentAchievement).where(StudentAchievement.student_id == student_id)
        )
        return list(result.scalars().all())
