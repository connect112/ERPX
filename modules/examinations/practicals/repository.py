import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.examinations.practicals.models import PracticalExam, PracticalResult


class PracticalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> PracticalExam:
        practical = PracticalExam(**fields)
        self.db.add(practical)
        await self.db.flush()
        await self.db.refresh(practical)
        return practical

    async def get_by_id(self, practical_id: uuid.UUID) -> PracticalExam | None:
        result = await self.db.execute(select(PracticalExam).where(PracticalExam.id == practical_id))
        return result.scalar_one_or_none()

    async def list_for_course(self, course_id: uuid.UUID) -> list[PracticalExam]:
        result = await self.db.execute(select(PracticalExam).where(PracticalExam.course_id == course_id))
        return list(result.scalars().all())

    async def update(self, practical: PracticalExam, **fields) -> PracticalExam:
        for key, value in fields.items():
            if value is not None:
                setattr(practical, key, value)
        await self.db.flush()
        await self.db.refresh(practical)
        return practical

    async def delete(self, practical: PracticalExam) -> None:
        await self.db.delete(practical)
        await self.db.flush()

    async def record_result(self, **fields) -> PracticalResult:
        result_row = PracticalResult(**fields)
        self.db.add(result_row)
        await self.db.flush()
        await self.db.refresh(result_row)
        return result_row

    async def get_result(self, practical_id: uuid.UUID, student_id: uuid.UUID) -> PracticalResult | None:
        result = await self.db.execute(
            select(PracticalResult).where(
                PracticalResult.practical_id == practical_id, PracticalResult.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_results(self, practical_id: uuid.UUID) -> list[PracticalResult]:
        result = await self.db.execute(
            select(PracticalResult).where(PracticalResult.practical_id == practical_id)
        )
        return list(result.scalars().all())
