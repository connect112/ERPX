import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.repository import CourseRepository
from modules.courses.resources.models import Resource
from modules.courses.resources.repository import ResourceRepository

logger = get_logger(__name__)


class ResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ResourceRepository(db)
        self.lesson_repo = LessonRepository(db)
        self.chapter_repo = ChapterRepository(db)
        self.course_repo = CourseRepository(db)

    async def _get_owned_lesson(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ):
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter or chapter.course_id != course_id:
            raise NotFoundError("Chapter", chapter_id)
        lesson = await self.lesson_repo.get_by_id(lesson_id)
        if not lesson or lesson.chapter_id != chapter_id:
            raise NotFoundError("Lesson", lesson_id)
        return lesson

    async def create_resource(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields,
    ) -> Resource:
        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        resource = await self.repo.create(lesson_id=lesson_id, **fields)
        logger.info("resource_created", resource_id=str(resource.id), lesson_id=str(lesson_id))
        return resource

    async def list_resources(
        self,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[Resource]:
        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        return await self.repo.list_for_lesson(lesson_id)

    async def get_resource(
        self,
        resource_id: uuid.UUID,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Resource:
        await self._get_owned_lesson(lesson_id, chapter_id, course_id, organization_id)
        resource = await self.repo.get_by_id(resource_id)
        if not resource or resource.lesson_id != lesson_id:
            raise NotFoundError("Resource", resource_id)
        return resource

    async def update_resource(
        self,
        resource_id: uuid.UUID,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields,
    ) -> Resource:
        resource = await self.get_resource(
            resource_id, lesson_id, chapter_id, course_id, organization_id
        )
        updated = await self.repo.update(resource, **fields)
        logger.info("resource_updated", resource_id=str(resource_id))
        return updated

    async def delete_resource(
        self,
        resource_id: uuid.UUID,
        lesson_id: uuid.UUID,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        resource = await self.get_resource(
            resource_id, lesson_id, chapter_id, course_id, organization_id
        )
        await self.repo.delete(resource)
        logger.info("resource_deleted", resource_id=str(resource_id))
