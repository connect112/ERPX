import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.models import Course


class CourseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Course:
        course = Course(**fields)
        self.db.add(course)
        await self.db.flush()
        await self.db.refresh(course)
        return course

    async def get_by_id(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> Course | None:
        result = await self.db.execute(
            select(Course).where(
                Course.id == course_id,
                Course.organization_id == organization_id,
                Course.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_ids(
        self, course_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[Course]:
        """Batch-load org-scoped, non-deleted courses by id in a single query.

        Same filtering as ``get_by_id`` (organization scope + ``deleted_at IS
        NULL``); callers that need per-id access build an ``{id: course}`` map.
        """
        if not course_ids:
            return []
        result = await self.db.execute(
            select(Course).where(
                Course.id.in_(course_ids),
                Course.organization_id == organization_id,
                Course.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def get_by_slug(self, organization_id: uuid.UUID, slug: str) -> Course | None:
        result = await self.db.execute(
            select(Course).where(
                Course.organization_id == organization_id,
                Course.slug == slug,
                Course.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
        is_published: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Course], int]:
        from sqlalchemy import func

        conditions = [Course.organization_id == organization_id, Course.deleted_at.is_(None)]
        if category_id is not None:
            conditions.append(Course.category_id == category_id)
        if is_published is not None:
            conditions.append(Course.is_published == is_published)

        count_result = await self.db.execute(
            select(func.count()).select_from(Course).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Course).where(*conditions).order_by(Course.title).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, course: Course, **fields) -> Course:
        for key, value in fields.items():
            if value is not None:
                setattr(course, key, value)
        await self.db.flush()
        await self.db.refresh(course)
        return course

    async def soft_delete(self, course: Course) -> None:
        from datetime import datetime, timezone

        course.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
