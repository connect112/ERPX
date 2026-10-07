import secrets
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import hash_password
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authentication.tasks import send_password_reset_email_task
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.crm.admissions.models import AdmissionStatus
from modules.crm.admissions.repository import AdmissionRepository
from modules.crm.leads.repository import LeadRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.models import Student, StudentStatus
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

# Mirrors modules/provisioning/service.py's own constant: a student's first
# login shouldn't expire before they've opened the email, longer than the
# 1-hour default an ordinary "I forgot my password" reset uses.
SET_PASSWORD_TOKEN_TTL_HOURS = 72


class StudentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = StudentRepository(db)
        self.admission_repo = AdmissionRepository(db)
        self.lead_repo = LeadRepository(db)
        self.auth_repo = AuthRepository(db)
        self.profile_repo = UserProfileRepository(db)
        self.authz_repo = AuthorizationRepository(db)
        self.course_repo = CourseRepository(db)
        self.enrollment_repo = EnrollmentRepository(db)
        self.batch_repo = BatchRepository(db)
        self.batch_enrollment_repo = BatchEnrollmentRepository(db)

    async def create_student(self, organization_id: uuid.UUID, **fields) -> Student:
        student = await self.repo.create(organization_id, **fields)
        logger.info("student_created", student_id=str(student.id), org_id=str(organization_id))
        return student

    async def create_from_admission(
        self,
        admission_id: uuid.UUID,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        enrollment_date: date | None,
    ) -> Student:
        admission = await self.admission_repo.get_by_id(admission_id, organization_id)
        if not admission:
            raise NotFoundError("Admission", admission_id)

        if admission.status != AdmissionStatus.CONFIRMED:
            raise ValidationError(
                "Only a CONFIRMED admission can be converted into a student. "
                f"This admission is currently '{admission.status.value}'."
            )

        existing = await self.repo.get_by_admission_id(admission_id)
        if existing:
            raise ConflictError("A student record already exists for this admission.")

        # Copy the lead's contact details across so the operator doesn't
        # have to re-type name/email/phone that's already on file.
        lead = await self.lead_repo.get_by_id(admission.lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", admission.lead_id)

        student = await self.repo.create(
            organization_id=organization_id,
            admission_id=admission_id,
            branch_id=branch_id or admission.branch_id,
            full_name=lead.full_name,
            email=lead.email,
            phone=lead.phone,
            course_name=admission.course_name,
            batch_name=admission.batch_name,
            enrollment_date=enrollment_date or date.today(),
        )
        logger.info(
            "student_created_from_admission", student_id=str(student.id), admission_id=str(admission_id)
        )
        return student

    async def get_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> Student:
        student = await self.repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return student

    async def list_students(self, organization_id: uuid.UUID, **filters) -> tuple[list[Student], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Student:
        student = await self.get_student(student_id, organization_id)
        updated = await self.repo.update(student, **fields)
        logger.info("student_updated", student_id=str(student_id))
        return updated

    async def change_status(
        self,
        student_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: StudentStatus,
        notes: str | None = None,
    ) -> Student:
        student = await self.get_student(student_id, organization_id)
        updated = await self.repo.set_status(student, status, notes)
        logger.info("student_status_changed", student_id=str(student_id), status=status.value)
        return updated

    async def delete_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        student = await self.get_student(student_id, organization_id)
        await self.repo.soft_delete(student)
        logger.info("student_deleted", student_id=str(student_id))

    async def create_login_account(
        self,
        student_id: uuid.UUID,
        organization_id: uuid.UUID,
        course_id: uuid.UUID,
        batch_id: uuid.UUID | None,
        created_by_user_id: uuid.UUID,
    ) -> tuple[uuid.UUID, str]:
        """Gives an existing Student record (created directly or via CRM
        admission) portal login access -- the general-purpose counterpart
        to modules/provisioning's Pentrix-only, payment-webhook-triggered
        flow, which this mirrors step for step but applies to a student
        who already exists rather than creating one. Returns
        (user_id, login_url); never returns a password over the wire."""
        student = await self.get_student(student_id, organization_id)
        if student.user_id is not None:
            raise ConflictError("This student already has a login account.")
        if not student.email:
            raise ValidationError("This student needs an email on file before a login can be created.")

        existing_user = await self.auth_repo.get_user_by_email(student.email)
        if existing_user:
            raise ConflictError(f"An ERPX account already exists for {student.email}.")

        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)

        student_role = await self.authz_repo.get_role_by_slug("student")
        if not student_role:
            raise ValidationError(
                "The 'student' system role is not seeded on this ERPX instance. "
                "Run apps/api/scripts/seed.py (seed_default_rbac) first."
            )

        user = await self.auth_repo.create_user(
            email=student.email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name=student.full_name,
            phone_number=student.phone,
        )
        # Skip self-registration email verification: an admin creating this
        # account on the student's behalf has already confirmed the email
        # is real, and the account only becomes usable once the student
        # follows the "set your password" link sent below.
        user.is_email_verified = True
        user.status = UserStatus.ACTIVE
        await self.db.flush()

        await self.profile_repo.create(user_id=user.id, organization_id=organization_id)
        await AuthorizationService(self.db).assign_role(
            user.id, student_role.id, organization_id, assigned_by_user_id=created_by_user_id
        )
        await self.repo.update(student, user_id=user.id)

        existing_enrollment = await self.enrollment_repo.get_by_student_and_course(student.id, course.id)
        if not existing_enrollment:
            await self.enrollment_repo.create(
                student_id=student.id, course_id=course.id, enrolled_on=date.today()
            )

        if batch_id is not None:
            batch = await self.batch_repo.get_by_id(batch_id, organization_id)
            if not batch or batch.course_id != course.id:
                raise ValidationError("The selected batch does not belong to the selected course.")
            existing_batch_enrollment = await self.batch_enrollment_repo.get_by_batch_and_student(
                batch.id, student.id
            )
            if not existing_batch_enrollment:
                await self.batch_enrollment_repo.create(
                    organization_id=organization_id,
                    batch_id=batch.id,
                    student_id=student.id,
                    enrolled_at=date.today(),
                )
        else:
            # Best-effort, matching modules/provisioning/service.py: if a
            # batch already exists for this course, put the student in it
            # so timetable/live-class self-service has something to show
            # immediately. No batch existing yet is not an error.
            batches, _total = await self.batch_repo.list_for_organization(
                organization_id, course_id=course.id, limit=1
            )
            if batches:
                await self.batch_enrollment_repo.create(
                    organization_id=organization_id,
                    batch_id=batches[0].id,
                    student_id=student.id,
                    enrolled_at=date.today(),
                )

        login_url = await self._send_set_password_email(user)
        logger.info(
            "student_login_account_created",
            student_id=str(student.id),
            user_id=str(user.id),
            course_id=str(course.id),
            created_by_user_id=str(created_by_user_id),
        )
        return user.id, login_url

    async def resend_login_email(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> str:
        student = await self.get_student(student_id, organization_id)
        if student.user_id is None:
            raise ValidationError("This student does not have a login account yet.")
        user = await self.auth_repo.get_user_by_id(student.user_id)
        if not user:
            raise NotFoundError("User", student.user_id)
        login_url = await self._send_set_password_email(user)
        logger.info("student_login_email_resent", student_id=str(student.id), user_id=str(user.id))
        return login_url

    async def _send_set_password_email(self, user) -> str:
        reset_token = await self.auth_repo.create_password_reset_token(
            user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS
        )
        set_password_url = f"{settings.STUDENT_PORTAL_URL}/reset-password?token={reset_token.token}"
        send_password_reset_email_task.delay(user.email, user.full_name, set_password_url, "account_invite")
        return f"{settings.STUDENT_PORTAL_URL}/login"
