"""
Provisioning module — service layer.

Orchestrates the one-way Pentrix-share -> ERPX student account handoff:
resolve the fixed Pentrix org/course, create a User + UserProfile + Student
+ student Role + course Enrollment, and email a "set your password" link.
Never returns a password over the wire.

Atomicity: every write below uses `flush()`, never `commit()` — the whole
sequence runs on the single request-scoped session FastAPI's `get_db()`
dependency hands the route (see app/db/session.py), which commits exactly
once after the route returns and rolls back the entire session on any
exception. So as long as this method lets exceptions propagate (it does —
nothing here catches and swallows one), a failure at any step leaves zero
trace: no orphaned User, no UserProfile with no role, nothing. See
tests/api/test_provisioning_atomicity.py for a live check of that
invariant, not just this comment's word for it.
"""

import secrets
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import hash_password
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authentication.tasks import send_password_reset_email_task
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.organizations.repository import OrganizationRepository
from modules.provisioning.schemas import ProvisionStudentRequest, ProvisionStudentResponse
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

# Fixed seed org/course this endpoint provisions into — created idempotently
# by apps/api/scripts/seed.py's seed_pentrix_program(), never by this
# endpoint itself (a request-time "create if missing" would let a typo in
# `program_code` silently spin up a bogus course rather than failing
# clearly, which is exactly the failure mode the brief calls out).
PENTRIX_ORG_SLUG = "gir-pentrix-program"

# A student's very first login shouldn't expire before they've opened the
# email — longer than the 1-hour default `create_password_reset_token` uses
# for an ordinary "I forgot my password" flow.
SET_PASSWORD_TOKEN_TTL_HOURS = 72


class ProvisioningService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_repo = AuthRepository(db)
        self.profile_repo = UserProfileRepository(db)
        self.authz_repo = AuthorizationRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)
        self.enrollment_repo = EnrollmentRepository(db)
        self.batch_repo = BatchRepository(db)
        self.batch_enrollment_repo = BatchEnrollmentRepository(db)

    async def provision_student(self, payload: ProvisionStudentRequest) -> ProvisionStudentResponse:
        login_url = f"{settings.STUDENT_PORTAL_URL}/login"

        existing_profile = await self.profile_repo.get_by_external_reference(payload.payment_reference)
        if existing_profile:
            logger.info(
                "provisioning_already_exists",
                payment_reference=payload.payment_reference,
                user_id=str(existing_profile.user_id),
            )
            return ProvisionStudentResponse(
                user_id=existing_profile.user_id, status="already_exists", login_url=login_url
            )

        # Resolve everything this call needs *before* writing anything, so a
        # bad request (unknown program, unseeded org, role not seeded)
        # fails clearly with zero side effects rather than a partial write.
        org = await self.org_repo.get_by_slug(PENTRIX_ORG_SLUG)
        if not org:
            raise ValidationError(
                f"The Pentrix organization ('{PENTRIX_ORG_SLUG}') is not seeded on this ERPX "
                "instance. Run apps/api/scripts/seed.py before provisioning students."
            )

        course = await self.course_repo.get_by_slug(org.id, payload.program_code)
        if not course:
            raise ValidationError(
                f"Unknown program identifier '{payload.program_code}' — no matching course "
                f"exists in the '{PENTRIX_ORG_SLUG}' organization."
            )

        student_role = await self.authz_repo.get_role_by_slug("student")
        if not student_role:
            raise ValidationError(
                "The 'student' system role is not seeded on this ERPX instance. "
                "Run apps/api/scripts/seed.py (seed_default_rbac) before provisioning students."
            )

        existing_user = await self.auth_repo.get_user_by_email(payload.email)
        if existing_user:
            # A genuinely different situation than "retried the same
            # payment": this email already has an ERPX account under some
            # other reference (or none). Silently reusing it would either
            # hijack an existing account or mask a real data problem —
            # fail clearly instead.
            raise ConflictError(f"An ERPX account already exists for {payload.email}.")

        user = await self.auth_repo.create_user(
            email=payload.email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name=payload.full_name,
            phone_number=payload.phone,
        )
        # Skip the ordinary self-registration email-verification flow: the
        # student already proved their email works by receiving Pentrix's
        # own payment confirmation, and this account only becomes usable
        # once they follow the "set your password" link sent below.
        user.is_email_verified = True
        user.status = UserStatus.ACTIVE
        await self.db.flush()

        await self.profile_repo.create(
            user_id=user.id, organization_id=org.id, external_reference=payload.payment_reference
        )

        await AuthorizationService(self.db).assign_role(
            user.id, student_role.id, assigned_by_user_id=None
        )

        student = await self.student_repo.create(
            org.id,
            user_id=user.id,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            course_name=course.title,
            enrollment_date=date.today(),
        )

        await self.enrollment_repo.create(
            student_id=student.id, course_id=course.id, enrolled_on=date.today()
        )

        # Best-effort: if a batch already exists for this course, put the
        # student in it too (so timetable/live-class self-service has
        # something to show immediately). No batch existing yet is not an
        # error — course enrollment alone is enough to unlock the LMS/
        # Pentrix side of the portal; batch assignment can follow later.
        batches, _total = await self.batch_repo.list_for_organization(org.id, course_id=course.id, limit=1)
        if batches:
            await self.batch_enrollment_repo.create(
                organization_id=org.id,
                batch_id=batches[0].id,
                student_id=student.id,
                enrolled_at=date.today(),
            )

        reset_token = await self.auth_repo.create_password_reset_token(
            user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS
        )
        set_password_url = f"{settings.STUDENT_PORTAL_URL}/reset-password?token={reset_token.token}"
        # Reuses the ordinary password-reset email/token machinery verbatim
        # (PasswordResetToken + reset_password() are already generic — see
        # modules/authentication/service.py) rather than inventing a
        # parallel "welcome" token type. The copy says "reset" rather than
        # "set", which reads slightly oddly for a brand-new account; a
        # dedicated template is a reasonable future polish, not a
        # functional gap — the token/link mechanics are identical either way.
        send_password_reset_email_task.delay(user.email, user.full_name, set_password_url)

        logger.info(
            "student_provisioned",
            user_id=str(user.id),
            student_id=str(student.id),
            payment_reference=payload.payment_reference,
            program_code=payload.program_code,
            # amount_paise/paid_at aren't persisted to any ERPX column (the
            # payment record of truth stays in Pentrix-share) — logged here
            # purely so a support investigation has a trace of what the
            # caller claimed was paid, without a schema change to store it.
            amount_paise=payload.amount_paise,
            paid_at=payload.paid_at.isoformat(),
        )
        return ProvisionStudentResponse(user_id=user.id, status="created", login_url=login_url)
