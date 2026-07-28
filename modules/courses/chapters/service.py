import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.courses.chapters.models import Chapter
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.repository import CourseRepository

logger = get_logger(__name__)


class ChapterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ChapterRepository(db)
        self.course_repo = CourseRepository(db)

    async def _get_owned_course(self, course_id: uuid.UUID, organization_id: uuid.UUID):
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return course

    async def create_chapter(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Chapter:
        await self._get_owned_course(course_id, organization_id)
        chapter = await self.repo.create(course_id=course_id, **fields)
        logger.info("chapter_created", chapter_id=str(chapter.id), course_id=str(course_id))
        return chapter

    async def list_chapters(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[Chapter]:
        await self._get_owned_course(course_id, organization_id)
        return await self.repo.list_for_course(course_id)

    async def get_chapter(
        self, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Chapter:
        await self._get_owned_course(course_id, organization_id)
        chapter = await self.repo.get_by_id(chapter_id)
        if not chapter or chapter.course_id != course_id:
            raise NotFoundError("Chapter", chapter_id)
        return chapter

    async def update_chapter(
        self, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Chapter:
        chapter = await self.get_chapter(chapter_id, course_id, organization_id)
        updated = await self.repo.update(chapter, **fields)
        logger.info("chapter_updated", chapter_id=str(chapter_id))
        return updated

    async def delete_chapter(
        self, chapter_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        chapter = await self.get_chapter(chapter_id, course_id, organization_id)
        await self.repo.delete(chapter)
        logger.info("chapter_deleted", chapter_id=str(chapter_id))
