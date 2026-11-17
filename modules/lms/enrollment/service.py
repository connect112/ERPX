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
        await self._assert_not_internship_managed(enrollment, status)
        updated = await self.repo.set_status(enrollment, status)
        logger.info("enrollment_status_changed", enrollment_id=str(enrollment_id), status=status.value)
        return updated

    async def _assert_not_internship_managed(self, enrollment: Enrollment, new_status: EnrollmentStatus) -> None:
        """A course screen must not bypass the internship's own access rules. While a student holds internship-granted access to the course
        the enrolment cannot be dropped here (revoke the internship access instead), and an enrolment an internship withdrew cannot be
        brought back here (grant the internship access again). Independent enrolments, and finishing a course, stay course-managed."""
        from sqlalchemy import select

        from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship

        rows = (
            await self.db.execute(
                select(InternshipSelection.lms_status, InternshipSelection.lms_enrolment_preexisting, OurInternship.title)
                .join(OurInternship, OurInternship.id == InternshipSelection.internship_id)
                .where(
                    InternshipSelection.lms_student_id == enrollment.student_id,
                    InternshipSelection.lms_course_id == enrollment.course_id,
                    InternshipSelection.lms_status.in_([LmsStatus.GRANTED, LmsStatus.REVOKED]),
                )
            )
        ).all()
        if not rows:
            return
        granted = [title for st, _, title in rows if st == LmsStatus.GRANTED]
        withdrawn_by_internship = [title for st, pre, title in rows if st == LmsStatus.REVOKED and not pre]
        if new_status == EnrollmentStatus.DROPPED and granted:
            raise ConflictError(
                f"This student has LMS access through {', '.join(granted)}. Withdraw it there (Revoke access); that keeps any enrolment "
                "they hold independently.",
                details={"code": "managed_by_internship", "internships": granted},
            )
        if enrollment.status == EnrollmentStatus.DROPPED and new_status != EnrollmentStatus.DROPPED and withdrawn_by_internship and not granted:
            raise ConflictError(
                f"LMS access through {', '.join(withdrawn_by_internship)} was withdrawn. Grant it again there to restore this enrolment.",
                details={"code": "managed_by_internship", "internships": withdrawn_by_internship},
            )
