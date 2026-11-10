import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.categories.repository import CategoryRepository
from modules.courses.models import Course, CourseType
from modules.courses.repository import CourseRepository

logger = get_logger(__name__)


class CourseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CourseRepository(db)
        self.category_repo = CategoryRepository(db)

    async def create_course(self, organization_id: uuid.UUID, slug: str, **fields) -> Course:
        existing = await self.repo.get_by_slug(organization_id, slug)
        if existing:
            raise ConflictError(f"A course with slug '{slug}' already exists.")

        category_id = fields.get("category_id")
        if category_id:
            category = await self.category_repo.get_by_id(category_id, organization_id)
            if not category:
                raise NotFoundError("Category", category_id)

        course = await self.repo.create(organization_id=organization_id, slug=slug, **fields)
        logger.info("course_created", course_id=str(course.id))
        return course

    async def get_course(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> Course:
        course = await self.repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return course

    async def list_courses(self, organization_id: uuid.UUID, **filters) -> tuple[list[Course], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def _linked_to(self, course: Course) -> list:
        from modules.our_internships.course_links import linked_internships

        return (await linked_internships(self.db, course.organization_id, [course.id])).get(course.id, [])

    async def update_course(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Course:
        course = await self.get_course(course_id, organization_id)
        new_type = fields.get("course_type") or course.course_type
        price = fields["price"] if "price" in fields and fields["price"] is not None else float(course.price or 0)
        if new_type == CourseType.INTERNSHIP:
            if price:
                raise ValidationError(
                    "An internship course has no price of its own: its fee comes from the internship's onboarding settings. "
                    "Set the price to 0 to make this an internship course."
                )
        else:
            if fields.get("show_internship_fee"):
                raise ValidationError("Fee visibility applies to internship courses only.")
            if course.course_type == CourseType.INTERNSHIP:
                linked = await self._linked_to(course)
                if linked:
                    names = ", ".join(f'"{i.title}"' for i in linked[:3])
                    raise ConflictError(f"This course is linked to {names}. Unlink it from the internship before making it a regular course.")
                fields["show_internship_fee"] = False  # (an explicit False; the repository skips None only)
        updated = await self.repo.update(course, **fields)
        logger.info("course_updated", course_id=str(course_id))
        return updated

    async def publish_course(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> Course:
        from modules.courses.chapters.repository import ChapterRepository

        course = await self.get_course(course_id, organization_id)
        chapters = await ChapterRepository(self.db).list_for_course(course_id)
        if not chapters:
            raise ValidationError("Cannot publish a course with no chapters.")

        updated = await self.repo.update(course, is_published=True)
        logger.info("course_published", course_id=str(course_id))
        return updated

    async def unpublish_course(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> Course:
        course = await self.get_course(course_id, organization_id)
        updated = await self.repo.update(course, is_published=False)
        logger.info("course_unpublished", course_id=str(course_id))
        return updated

    async def delete_course(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        course = await self.get_course(course_id, organization_id)
        linked = await self._linked_to(course)
        if linked:
            names = ", ".join(f'"{i.title}"' for i in linked[:3])
            raise ConflictError(f"This course is linked to {names}. Unlink it from the internship before deleting it.")
        await self.repo.soft_delete(course)
        logger.info("course_deleted", course_id=str(course_id))
