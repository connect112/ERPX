import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.learning_paths.models import LearningPath, LearningPathCourse


class LearningPathRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LearningPath:
        path = LearningPath(**fields)
        self.db.add(path)
        await self.db.flush()
        await self.db.refresh(path)
        return path

    async def get_by_id(self, path_id: uuid.UUID, organization_id: uuid.UUID) -> LearningPath | None:
        result = await self.db.execute(
            select(LearningPath).where(
                LearningPath.id == path_id, LearningPath.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, organization_id: uuid.UUID, slug: str) -> LearningPath | None:
        result = await self.db.execute(
            select(LearningPath).where(
                LearningPath.organization_id == organization_id, LearningPath.slug == slug
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[LearningPath]:
        result = await self.db.execute(
            select(LearningPath)
            .where(LearningPath.organization_id == organization_id)
            .order_by(LearningPath.title)
        )
        return list(result.scalars().all())

    async def update(self, path: LearningPath, **fields) -> LearningPath:
        for key, value in fields.items():
            if value is not None:
                setattr(path, key, value)
        await self.db.flush()
        await self.db.refresh(path)
        return path

    async def delete(self, path: LearningPath) -> None:
        await self.db.delete(path)
        await self.db.flush()

    # ---- Path <-> Course ----

    async def add_course(
        self, learning_path_id: uuid.UUID, course_id: uuid.UUID, order_index: int
    ) -> LearningPathCourse:
        entry = LearningPathCourse(
            learning_path_id=learning_path_id, course_id=course_id, order_index=order_index
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def remove_course(self, learning_path_id: uuid.UUID, course_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(LearningPathCourse).where(
                LearningPathCourse.learning_path_id == learning_path_id,
                LearningPathCourse.course_id == course_id,
            )
        )
        await self.db.flush()

    async def list_courses(self, learning_path_id: uuid.UUID) -> list[LearningPathCourse]:
        result = await self.db.execute(
            select(LearningPathCourse)
            .where(LearningPathCourse.learning_path_id == learning_path_id)
            .order_by(LearningPathCourse.order_index)
        )
        return list(result.scalars().all())
