import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.examinations.practicals.models import PracticalExam, PracticalResult
from modules.examinations.practicals.repository import PracticalRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class PracticalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PracticalRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_practical(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> PracticalExam:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        practical = await self.repo.create(course_id=course_id, **fields)
        logger.info("practical_created", practical_id=str(practical.id))
        return practical

    async def _get_owned_practical(
        self, practical_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> PracticalExam:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        practical = await self.repo.get_by_id(practical_id)
        if not practical or practical.course_id != course_id:
            raise NotFoundError("Practical exam", practical_id)
        return practical

    async def list_practicals(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[PracticalExam]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_for_course(course_id)

    async def get_practical(
        self, practical_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> PracticalExam:
        return await self._get_owned_practical(practical_id, course_id, organization_id)

    async def update_practical(
        self, practical_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> PracticalExam:
        practical = await self._get_owned_practical(practical_id, course_id, organization_id)
        updated = await self.repo.update(practical, **fields)
        logger.info("practical_updated", practical_id=str(practical_id))
        return updated

    async def delete_practical(
        self, practical_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        practical = await self._get_owned_practical(practical_id, course_id, organization_id)
        await self.repo.delete(practical)
        logger.info("practical_deleted", practical_id=str(practical_id))

    async def record_result(
        self,
        practical_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        score: int,
        remarks: str | None,
        evaluated_by_user_id: uuid.UUID,
    ) -> PracticalResult:
        practical = await self._get_owned_practical(practical_id, course_id, organization_id)
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.repo.get_result(practical_id, student_id)
        if existing:
            raise ConflictError("A result has already been recorded for this student.")

        if score > practical.total_marks:
            raise ValidationError(f"Score cannot exceed the total marks of {practical.total_marks}.")

        result_row = await self.repo.record_result(
            practical_id=practical_id,
            student_id=student_id,
            score=score,
            remarks=remarks,
            evaluated_by_user_id=evaluated_by_user_id,
        )
        logger.info("practical_result_recorded", practical_id=str(practical_id), student_id=str(student_id))
        return result_row

    async def list_results(
        self, practical_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[PracticalResult]:
        await self._get_owned_practical(practical_id, course_id, organization_id)
        return await self.repo.list_results(practical_id)
