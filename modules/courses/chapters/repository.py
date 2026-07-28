import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.chapters.models import Chapter


class ChapterRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Chapter:
        chapter = Chapter(**fields)
        self.db.add(chapter)
        await self.db.flush()
        await self.db.refresh(chapter)
        return chapter

    async def get_by_id(self, chapter_id: uuid.UUID) -> Chapter | None:
        result = await self.db.execute(select(Chapter).where(Chapter.id == chapter_id))
        return result.scalar_one_or_none()

    async def list_for_course(self, course_id: uuid.UUID) -> list[Chapter]:
        result = await self.db.execute(
            select(Chapter).where(Chapter.course_id == course_id).order_by(Chapter.order_index)
        )
        return list(result.scalars().all())

    async def update(self, chapter: Chapter, **fields) -> Chapter:
        for key, value in fields.items():
            if value is not None:
                setattr(chapter, key, value)
        await self.db.flush()
        await self.db.refresh(chapter)
        return chapter

    async def delete(self, chapter: Chapter) -> None:
        await self.db.delete(chapter)
        await self.db.flush()
