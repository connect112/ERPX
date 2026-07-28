import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class EnrollmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EnrollmentRepository(db)
        self.student_repo = StudentRepository(db)
        self.course_repo = CourseRepository(db)

    async def create_enrollment(
        self,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
        enrolled_on: date | None,
    ) -> Enrollment:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)

        existing = await self.repo.get_by_student_and_course(student_id, course_id)
        if existing:
            raise ConflictError("This student is already enrolled in this course.")

        enrollment = await self.repo.create(
            student_id=student_id,
            course_id=course_id,
            enrolled_on=enrolled_on or date.today(),
        )
        logger.info(
            "student_enrolled", enrollment_id=str(enrollment.id), student_id=str(student_id),
            course_id=str(course_id),
        )
        return enrollment

    async def get_enrollment(self, enrollment_id: uuid.UUID, organization_id: uuid.UUID) -> Enrollment:
        enrollment = await self.repo.get_by_id(enrollment_id)
        if not enrollment:
            raise NotFoundError("Enrollment", enrollment_id)
        # Ownership check via the student record (enrollment itself has no org column).
        student = await self.student_repo.get_by_id(enrollment.student_id, organization_id)
        if not student:
            raise NotFoundError("Enrollment", enrollment_id)
        return enrollment

    async def list_for_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> list[Enrollment]:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.repo.list_for_student(student_id)

    async def list_for_course(self, course_id: uuid.UUID, organization_id: uuid.UUID) -> list[Enrollment]:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        return await self.repo.list_for_course(course_id)

    async def change_status(
        self, enrollment_id: uuid.UUID, organization_id: uuid.UUID, status: EnrollmentStatus
    ) -> Enrollment:
        enrollment = await self.get_enrollment(enrollment_id, organization_id)
        updated = await self.repo.set_status(enrollment, status)
        logger.info("enrollment_status_changed", enrollment_id=str(enrollment_id), status=status.value)
        return updated
