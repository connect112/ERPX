import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.courses.learning_paths.models import LearningPath, LearningPathCourse
from modules.courses.learning_paths.repository import LearningPathRepository
from modules.courses.repository import CourseRepository

logger = get_logger(__name__)


class LearningPathService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LearningPathRepository(db)
        self.course_repo = CourseRepository(db)

    async def create_path(self, organization_id: uuid.UUID, slug: str, **fields) -> LearningPath:
        existing = await self.repo.get_by_slug(organization_id, slug)
        if existing:
            raise ConflictError(f"A learning path with slug '{slug}' already exists.")
        path = await self.repo.create(organization_id=organization_id, slug=slug, **fields)
        logger.info("learning_path_created", path_id=str(path.id))
        return path

    async def get_path(self, path_id: uuid.UUID, organization_id: uuid.UUID) -> LearningPath:
        path = await self.repo.get_by_id(path_id, organization_id)
        if not path:
            raise NotFoundError("Learning path", path_id)
        return path

    async def list_paths(self, organization_id: uuid.UUID) -> list[LearningPath]:
        return await self.repo.list_for_organization(organization_id)

    async def update_path(
        self, path_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> LearningPath:
        path = await self.get_path(path_id, organization_id)
        updated = await self.repo.update(path, **fields)
        logger.info("learning_path_updated", path_id=str(path_id))
        return updated

    async def delete_path(self, path_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        path = await self.get_path(path_id, organization_id)
        await self.repo.delete(path)
        logger.info("learning_path_deleted", path_id=str(path_id))

    async def add_course_to_path(
        self, path_id: uuid.UUID, organization_id: uuid.UUID, course_id: uuid.UUID, order_index: int
    ) -> LearningPathCourse:
        await self.get_path(path_id, organization_id)
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        entry = await self.repo.add_course(path_id, course_id, order_index)
        logger.info("course_added_to_path", path_id=str(path_id), course_id=str(course_id))
        return entry

    async def remove_course_from_path(
        self, path_id: uuid.UUID, organization_id: uuid.UUID, course_id: uuid.UUID
    ) -> None:
        await self.get_path(path_id, organization_id)
        await self.repo.remove_course(path_id, course_id)
        logger.info("course_removed_from_path", path_id=str(path_id), course_id=str(course_id))

    async def list_path_courses(
        self, path_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[LearningPathCourse]:
        await self.get_path(path_id, organization_id)
        return await self.repo.list_courses(path_id)
