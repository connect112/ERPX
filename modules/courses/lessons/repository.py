import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.lessons.models import Lesson


class LessonRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Lesson:
        lesson = Lesson(**fields)
        self.db.add(lesson)
        await self.db.flush()
        await self.db.refresh(lesson)
        return lesson

    async def get_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        result = await self.db.execute(select(Lesson).where(Lesson.id == lesson_id))
        return result.scalar_one_or_none()

    async def list_for_chapter(self, chapter_id: uuid.UUID) -> list[Lesson]:
        result = await self.db.execute(
            select(Lesson).where(Lesson.chapter_id == chapter_id).order_by(Lesson.order_index)
        )
        return list(result.scalars().all())

    async def update(self, lesson: Lesson, **fields) -> Lesson:
        for key, value in fields.items():
            if value is not None:
                setattr(lesson, key, value)
        await self.db.flush()
        await self.db.refresh(lesson)
        return lesson

    async def delete(self, lesson: Lesson) -> None:
        await self.db.delete(lesson)
        await self.db.flush()
