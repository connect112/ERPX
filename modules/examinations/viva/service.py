import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.examinations.viva.models import VivaExam, VivaResult
from modules.examinations.viva.repository import VivaRepository
from modules.learning.scope import selection_access, student_internship_ids
from modules.lms.enrollment.access import require_live_enrollment
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class VivaService:
    """Vivas of a course. A course-wide one has no ``internship_id``; one that belongs to a single internship carries it and is
    reached only through that internship. A result is recorded only for a student who is in the course (course-wide) or holds granted LMS
    access on that internship (internship-scoped); a recorded result can be corrected by authorized staff, and a revoked student's results
    stay visible to them, marked."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = VivaRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)

    async def create_viva(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> VivaExam:
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
            raise NotFoundError("Viva", viva_id)
        return viva

    async def list_vivas(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, *, internship_id: uuid.UUID | None = None, include_course: bool = False
    ) -> list[VivaExam]:
        """Course-wide viva (no internship given), or one internship's own (plus the course-wide ones when asked)."""
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        clause = VivaExam.internship_id.is_(None)
        if internship_id is not None:
            clause = VivaExam.internship_id == internship_id
            if include_course:
                clause = or_(clause, VivaExam.internship_id.is_(None))
        rows = await self.db.execute(select(VivaExam).where(VivaExam.course_id == course_id, clause).order_by(VivaExam.exam_date))
        return list(rows.scalars().all())

    async def my_vivas(self, course_id: uuid.UUID, student) -> list[dict]:
        """What a student sees: the course-wide viva and those of internships they hold granted access on, each with their own result."""
        ids = await student_internship_ids(self.db, student, course_id)
        clause = VivaExam.internship_id.is_(None)
        if ids:
            clause = or_(clause, VivaExam.internship_id.in_(list(ids)))
        rows = (await self.db.execute(select(VivaExam).where(VivaExam.course_id == course_id, clause).order_by(VivaExam.exam_date))).scalars().all()
        out = []
        for p in rows:
            result = await self.repo.get_result(p.id, student.id)
            out.append(
                {
                    "id": p.id, "title": p.title, "exam_date": p.exam_date, "panel_members": p.panel_members, "total_marks": p.total_marks,
                    "passing_marks": p.passing_marks, "internship_id": p.internship_id,
                    "score": result.score if result else None, "remarks": result.remarks if result else None,
                    "passed": (result.score >= p.passing_marks) if result else None,
                }
            )
        return out

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
        recorded = await self.repo.list_results(viva_id)
        if recorded:
            raise ConflictError("Results have already been recorded for this evaluation, so it cannot be deleted.")
        await self.repo.delete(viva)
        logger.info("viva_deleted", viva_id=str(viva_id))

    async def _eligible(self, viva: VivaExam, student) -> None:
        """Only a student who is in the course (or, for an internship's own viva, holds granted access on that internship)."""
        if viva.internship_id is not None:
            if viva.internship_id not in await student_internship_ids(self.db, student, viva.course_id):
                raise ValidationError("This student does not have LMS access on the internship this evaluation belongs to.")
        else:
            await require_live_enrollment(self.db, student, viva.course_id)

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
        await self._eligible(viva, student)

        existing = await self.repo.get_result(viva_id, student_id)
        if existing:
            raise ConflictError("A result has already been recorded for this student. Edit it instead.")

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

    async def update_result(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, student_id: uuid.UUID,
        score: int, remarks: str | None, evaluated_by_user_id: uuid.UUID,
    ) -> VivaResult:
        """Correct a recorded result. It stays allowed for a student whose access was withdrawn: it is their history."""
        from datetime import datetime, timezone

        viva = await self._get_owned_viva(viva_id, course_id, organization_id)
        if await self.student_repo.get_by_id(student_id, organization_id) is None:
            raise NotFoundError("Student", student_id)
        existing = await self.repo.get_result(viva_id, student_id)
        if existing is None:
            raise NotFoundError("Result", student_id)
        if score > viva.total_marks:
            raise ValidationError(f"Score cannot exceed the total marks of {viva.total_marks}.")
        existing.score = score
        existing.remarks = remarks
        existing.evaluated_by_user_id = evaluated_by_user_id
        existing.evaluated_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info("viva_result_updated", viva_id=str(viva_id), student_id=str(student_id))
        return existing

    async def list_results(
        self, viva_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, *, internship_id: uuid.UUID | None = None
    ) -> list[dict]:
        """Results with the student's name. For an internship (its own viva, or one asked for by internship) only that internship's
        students, revoked ones kept and marked."""
        viva = await self._get_owned_viva(viva_id, course_id, organization_id)
        rows = await self.repo.list_results(viva_id)
        scope = viva.internship_id or internship_id
        access = await selection_access(self.db, scope) if scope is not None else {}
        out = []
        for r in rows:
            if scope is not None and r.student_id not in access:
                continue
            student = await self.student_repo.get_by_id(r.student_id, organization_id)
            out.append(
                {
                    "id": r.id, "viva_id": r.viva_id, "student_id": r.student_id, "score": r.score, "remarks": r.remarks,
                    "evaluated_by_user_id": r.evaluated_by_user_id, "evaluated_at": r.evaluated_at,
                    "access_status": access[r.student_id][0] if r.student_id in access else None,
                    "student_name": student.full_name if student else None,
                }
            )
        return out
