import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.examinations.viva.models import VivaExam, VivaResult


class VivaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> VivaExam:
        viva = VivaExam(**fields)
        self.db.add(viva)
        await self.db.flush()
        await self.db.refresh(viva)
        return viva

    async def get_by_id(self, viva_id: uuid.UUID) -> VivaExam | None:
        result = await self.db.execute(select(VivaExam).where(VivaExam.id == viva_id))
        return result.scalar_one_or_none()

    async def list_for_course(self, course_id: uuid.UUID) -> list[VivaExam]:
        result = await self.db.execute(select(VivaExam).where(VivaExam.course_id == course_id))
        return list(result.scalars().all())

    async def update(self, viva: VivaExam, **fields) -> VivaExam:
        for key, value in fields.items():
            if value is not None:
                setattr(viva, key, value)
        await self.db.flush()
        await self.db.refresh(viva)
        return viva

    async def delete(self, viva: VivaExam) -> None:
        await self.db.delete(viva)
        await self.db.flush()

    async def record_result(self, **fields) -> VivaResult:
        result_row = VivaResult(**fields)
        self.db.add(result_row)
        await self.db.flush()
        await self.db.refresh(result_row)
        return result_row

    async def get_result(self, viva_id: uuid.UUID, student_id: uuid.UUID) -> VivaResult | None:
        result = await self.db.execute(
            select(VivaResult).where(
                VivaResult.viva_id == viva_id, VivaResult.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_results(self, viva_id: uuid.UUID) -> list[VivaResult]:
        result = await self.db.execute(select(VivaResult).where(VivaResult.viva_id == viva_id))
        return list(result.scalars().all())
