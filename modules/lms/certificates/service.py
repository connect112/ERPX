import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.certificates.models import Certificate
from modules.lms.certificates.repository import CertificateRepository
from modules.lms.certificates.schemas import CertificateVerificationResponse
from modules.lms.progress.service import ProgressService
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


def _generate_certificate_number() -> str:
    return f"ERPX-CERT-{secrets.token_hex(6).upper()}"


class CertificateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CertificateRepository(db)
        self.student_repo = StudentRepository(db)
        self.course_repo = CourseRepository(db)
        self.progress_service = ProgressService(db)

    async def issue_certificate(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, course_id: uuid.UUID, force: bool
    ) -> Certificate:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)

        existing = await self.repo.get_by_student_and_course(student_id, course_id)
        if existing:
            raise ConflictError("A certificate has already been issued for this student and course.")

        if not force:
            progress = await self.progress_service.get_course_progress(
                organization_id, student_id, course_id
            )
            if progress.percent_complete < 100:
                raise ValidationError(
                    f"Student has only completed {progress.percent_complete}% of this course. "
                    "A certificate can only be issued at 100% completion (or pass force=true)."
                )

        certificate = await self.repo.create(
            student_id=student_id,
            course_id=course_id,
            certificate_number=_generate_certificate_number(),
        )
        logger.info(
            "certificate_issued",
            certificate_id=str(certificate.id),
            certificate_number=certificate.certificate_number,
        )
        return certificate

    async def list_for_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> list[Certificate]:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.repo.list_for_student(student_id)

    async def verify(self, certificate_number: str) -> CertificateVerificationResponse:
        """
        Public verification — no organization scoping, since certificate
        verification links are meant to be shared and checked by anyone
        (employers, other institutions) without an ERPX account.
        """
        certificate = await self.repo.get_by_number(certificate_number)
        if not certificate:
            return CertificateVerificationResponse(valid=False, certificate_number=certificate_number)

        # Certificate verification is intentionally organization-unscoped:
        # fetch the student/course directly by ID rather than through the
        # org-scoped repositories used elsewhere in this service.
        from sqlalchemy import select

        from modules.courses.models import Course
        from modules.students.models import Student

        student_result = await self.db.execute(select(Student).where(Student.id == certificate.student_id))
        student = student_result.scalar_one_or_none()

        course_result = await self.db.execute(select(Course).where(Course.id == certificate.course_id))
        course = course_result.scalar_one_or_none()

        return CertificateVerificationResponse(
            valid=True,
            certificate_number=certificate.certificate_number,
            student_name=student.full_name if student else None,
            course_title=course.title if course else None,
            issued_at=certificate.issued_at,
        )
