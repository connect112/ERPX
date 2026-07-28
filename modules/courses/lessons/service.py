import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.models import Lesson
from modules.courses.lessons.repository import LessonRepository
from modules.courses.repository import CourseRepository

logger = get_logger(__name__)


class LessonService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LessonRepository(db)
        self.chapter_repo = ChapterRepository(db)
        self.course_repo = CourseRepository(db)

    async def _get_owned_chapter(self, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID):
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.course_id != course_id:
            raise NotFoundError("Chapter", chapter_id)
        return chapter

    async def create_lesson(
        self, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Lesson:
        await self._get_owned_chapter(chapter_id, course_id, organization_id)
        lesson = await self.repo.create(chapter_id=chapter_id, **fields)
        logger.info("lesson_created", lesson_id=str(lesson.id), chapter_id=str(chapter_id))
        return lesson

    async def list_lessons(
        self, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[Lesson]:
        await self._get_owned_chapter(chapter_id, course_id, organization_id)
        return await self.repo.list_for_chapter(chapter_id)

    async def get_lesson(
        self, lesson_id: uuid.UUID, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Lesson:
        await self._get_owned_chapter(chapter_id, course_id, organization_id)
        lesson = await self.repo.get_by_id(lesson_id)
        if not lesson or lesson.chapter_id != chapter_id:
            raise NotFoundError("Lesson", lesson_id)
        return lesson

    async def update_lesson(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields,
    ) -> Lesson:
        lesson = await self.get_lesson(lesson_id, chapter_id, course_id, organization_id)
        updated = await self.repo.update(lesson, **fields)
        logger.info("lesson_updated", lesson_id=str(lesson_id))
        return updated

    async def delete_lesson(
        self, lesson_id: uuid.UUID, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        lesson = await self.get_lesson(lesson_id, chapter_id, course_id, organization_id)
        await self.repo.delete(lesson)
        logger.info("lesson_deleted", lesson_id=str(lesson_id))
