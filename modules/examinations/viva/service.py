import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.examinations.viva.models import VivaExam, VivaResult
from modules.examinations.viva.repository import VivaRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class VivaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = VivaRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_viva(self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> VivaExam:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        viva = await self.repo.create(course_id=course_id, **fields)
        logger.info("viva_created", viva_id=str(viva.id))
        return viva

    async def _get_owned_viva(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> VivaExam:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        viva = await self.repo.get_by_id(viva_id)
        if not viva or viva.course_id != course_id:
            raise NotFoundError("Viva exam", viva_id)
        return viva

    async def list_vivas(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[VivaExam]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_for_course(course_id)

    async def get_viva(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> VivaExam:
        return await self._get_owned_viva(viva_id, course_id, organization_id)

    async def update_viva(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> VivaExam:
        viva = await self._get_owned_viva(viva_id, course_id, organization_id)
        updated = await self.repo.update(viva, **fields)
        logger.info("viva_updated", viva_id=str(viva_id))
        return updated

    async def delete_viva(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        viva = await self._get_owned_viva(viva_id, course_id, organization_id)
        await self.repo.delete(viva)
        logger.info("viva_deleted", viva_id=str(viva_id))

    async def record_result(
        self,
        viva_id: uuid.UUID,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        score: int,
        remarks: str | None,
        evaluated_by_user_id: uuid.UUID,
    ) -> VivaResult:
        viva = await self._get_owned_viva(viva_id, course_id, organization_id)
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.repo.get_result(viva_id, student_id)
        if existing:
            raise ConflictError("A result has already been recorded for this student.")

        if score > viva.total_marks:
            raise ValidationError(f"Score cannot exceed the total marks of {viva.total_marks}.")

        result_row = await self.repo.record_result(
            viva_id=viva_id,
            student_id=student_id,
            score=score,
            remarks=remarks,
            evaluated_by_user_id=evaluated_by_user_id,
        )
        logger.info("viva_result_recorded", viva_id=str(viva_id), student_id=str(student_id))
        return result_row

    async def list_results(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[VivaResult]:
        await self._get_owned_viva(viva_id, course_id, organization_id)
        return await self.repo.list_results(viva_id)
