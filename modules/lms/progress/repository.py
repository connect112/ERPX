import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.chapters.models import Chapter
from modules.courses.lessons.models import Lesson
from modules.lms.progress.models import LessonProgress


class ProgressRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, student_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonProgress | None:
        result = await self.db.execute(
            select(LessonProgress).where(
                LessonProgress.student_id == student_id, LessonProgress.lesson_id == lesson_id
            )
        )
        return result.scalar_one_or_none()

    async def mark_complete(self, student_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonProgress:
        existing = await self.get(student_id, lesson_id)
        if existing:
            return existing
        record = LessonProgress(student_id=student_id, lesson_id=lesson_id)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def unmark_complete(self, student_id: uuid.UUID, lesson_id: uuid.UUID) -> None:
        existing = await self.get(student_id, lesson_id)
        if existing:
            await self.db.delete(existing)
            await self.db.flush()

    async def list_for_student_course(self, student_id: uuid.UUID, course_id: uuid.UUID) -> list[LessonProgress]:
        result = await self.db.execute(
            select(LessonProgress)
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .where(LessonProgress.student_id == student_id, Chapter.course_id == course_id)
        )
        return list(result.scalars().all())

    async def count_total_lessons_for_course(self, course_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Lesson)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .where(Chapter.course_id == course_id)
        )
        return result.scalar_one()

    async def count_completed_for_student_course(self, student_id: uuid.UUID, course_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(LessonProgress)
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .where(LessonProgress.student_id == student_id, Chapter.course_id == course_id)
        )
        return result.scalar_one()
