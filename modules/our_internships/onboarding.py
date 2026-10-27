"""
After the offers: tracking each selected student through the onboarding steps, and giving LMS access once it is earned.

The steps are verification of the student's documents, a manually confirmed payment (money is checked by hand, so staff say
when it has arrived), and then LMS access: an account on the student portal (lms.pentrix.in) and enrolment in the
internship's course. LMS access is only possible once both verification and payment are confirmed, so access follows the
checks rather than being handed out ahead of them.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
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
from modules.batches.models import BatchEnrollment
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.models import Course
from modules.courses.repository import CourseRepository
from modules.institutions.models import InstitutionStudent
from modules.lms.enrollment.models import EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.our_internships.models import (
    InternshipSelection,
    LmsStatus,
    OfferResponse,
    OfferStatus,
    OurInternship,
    PaymentStatus,
    VerificationStatus,
)
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository
from packages.email.service import email_service

logger = get_logger(__name__)

SET_PASSWORD_TOKEN_TTL_HOURS = 72
MAX_BULK_GRANT = 25


# ------------------------------------------------------------------ where the student is

STAGE_LABELS: dict[str, str] = {
    "selected": "Selected",
    "offer_sent": "Offer sent",
    "accepted": "Offer accepted",
    "verified": "Verified",
    "paid": "Payment confirmed",
    "ready_for_lms": "Ready for LMS access",
    "lms_access": "LMS access granted",
    "declined": "Declined the offer",
    "rejected": "Verification failed",
}


def stage_of(selection: InternshipSelection) -> str:
    """One word for where this student is, the furthest step they have reached. LMS access comes first, then the two
    ways out (declined, failed verification), then the steps in order."""
    if selection.lms_status == LmsStatus.GRANTED:
        return "lms_access"
    if selection.offer_response == OfferResponse.DECLINED:
        return "declined"
    if selection.verification_status == VerificationStatus.REJECTED:
        return "rejected"
    verified = selection.verification_status == VerificationStatus.VERIFIED
    paid = selection.payment_status == PaymentStatus.PAID
    if verified and paid:
        return "ready_for_lms"
    if paid:
        return "paid"
    if verified:
        return "verified"
    if selection.offer_response == OfferResponse.ACCEPTED:
        return "accepted"
    if selection.offer_status == OfferStatus.SENT:
        return "offer_sent"
    return "selected"


def grant_blockers(internship: OurInternship, selection: InternshipSelection) -> list[str]:
    """Everything that currently stops LMS access being granted, in words (empty means it can be granted)."""
    blockers: list[str] = []
    if selection.lms_status == LmsStatus.GRANTED:
        return ["LMS access has already been granted."]
    if internship.lms_course_id is None:
        blockers.append("Choose the LMS course for this internship first.")
    if selection.offer_response == OfferResponse.DECLINED:
        blockers.append("The student declined the offer.")
    if selection.verification_status != VerificationStatus.VERIFIED:
        blockers.append("Verification is not complete.")
    if selection.payment_status != PaymentStatus.PAID:
        blockers.append("Payment has not been confirmed.")
    return blockers


@dataclass
class GrantOutcome:
    created_account: bool
    email: str
    full_name: str
    reset_token: str | None
    course_title: str


class OnboardingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ loading

    async def selection(self, internship: OurInternship, student_id: uuid.UUID) -> tuple[InternshipSelection, InstitutionStudent]:
        row = (
            await self.db.execute(
                select(InternshipSelection, InstitutionStudent)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .where(InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Selected student", student_id)
        return row[0], row[1]

    async def selections(self, internship: OurInternship, student_ids: list[uuid.UUID]) -> list[tuple[InternshipSelection, InstitutionStudent]]:
        wanted = list(dict.fromkeys(student_ids))
        rows = (
            await self.db.execute(
                select(InternshipSelection, InstitutionStudent)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .where(InternshipSelection.internship_id == internship.id, InternshipSelection.student_id.in_(wanted))
                .order_by(InstitutionStudent.name)
            )
        ).all()
        if len(rows) != len(wanted):
            raise ValidationError("Only students on the selected list can be updated.")
        return [(r[0], r[1]) for r in rows]

    # ------------------------------------------------------------------ the LMS course

    async def courses(self, organization_id: uuid.UUID) -> list[Course]:
        courses, _ = await CourseRepository(self.db).list_for_organization(organization_id, limit=200)
        return courses

    async def set_course(self, internship: OurInternship, course_id: uuid.UUID | None) -> None:
        if course_id is not None:
            course = await CourseRepository(self.db).get_by_id(course_id, internship.organization_id)
            if course is None:
                raise NotFoundError("Course", course_id)
        internship.lms_course_id = course_id
        await self.db.flush()

    # ------------------------------------------------------------------ the steps

    def apply(self, selection: InternshipSelection, user_id: uuid.UUID, fields: dict) -> None:
        """Record what staff report about one student. Only the fields given change."""
        now = datetime.now(timezone.utc)
        verification = fields.get("verification_status", selection.verification_status)
        payment = fields.get("payment_status", selection.payment_status)
        if selection.lms_status == LmsStatus.GRANTED and (
            verification != VerificationStatus.VERIFIED or payment != PaymentStatus.PAID
        ):
            raise ConflictError("This student already has LMS access. Revoke it before changing verification or payment.")

        if "offer_response" in fields and fields["offer_response"] != selection.offer_response:
            selection.offer_response = fields["offer_response"]
            selection.offer_response_at = None if fields["offer_response"] == OfferResponse.AWAITING else now

        if "verification_status" in fields and fields["verification_status"] != selection.verification_status:
            selection.verification_status = fields["verification_status"]
            if fields["verification_status"] == VerificationStatus.PENDING:
                selection.verified_at, selection.verified_by_user_id = None, None
            else:
                selection.verified_at, selection.verified_by_user_id = now, user_id
        if "verification_note" in fields:
            selection.verification_note = fields["verification_note"]

        for key in ("payment_amount", "payment_reference", "payment_received_on"):
            if key in fields:
                setattr(selection, key, fields[key])
        if "payment_status" in fields and fields["payment_status"] != selection.payment_status:
            selection.payment_status = fields["payment_status"]
            if fields["payment_status"] == PaymentStatus.PAID:
                selection.payment_confirmed_at, selection.payment_confirmed_by_user_id = now, user_id
                if selection.payment_received_on is None:
                    selection.payment_received_on = date.today()
            else:
                selection.payment_confirmed_at, selection.payment_confirmed_by_user_id = None, None

    async def update_one(self, internship: OurInternship, student_id: uuid.UUID, user_id: uuid.UUID, fields: dict) -> InternshipSelection:
        selection, _ = await self.selection(internship, student_id)
        self.apply(selection, user_id, fields)
        await self.db.flush()
        return selection

    async def update_many(
        self, internship: OurInternship, student_ids: list[uuid.UUID], user_id: uuid.UUID, fields: dict
    ) -> tuple[int, list[str]]:
        """Apply the same status to several students. Returns (changed, problems); a student who cannot take the change
        (already has LMS access) is reported by name and the others still change."""
        changed, problems = 0, []
        for selection, student in await self.selections(internship, student_ids):
            try:
                async with self.db.begin_nested():
                    self.apply(selection, user_id, fields)
                changed += 1
            except ConflictError as exc:
                problems.append(f"{student.name}: {exc}")
        await self.db.flush()
        return changed, problems

    # ------------------------------------------------------------------ LMS access

    async def grant(
        self, internship: OurInternship, selection: InternshipSelection, student: InstitutionStudent, user_id: uuid.UUID
    ) -> GrantOutcome:
        blockers = grant_blockers(internship, selection)
        if blockers:
            raise ValidationError(" ".join(blockers))
        organization_id = internship.organization_id
        course = await CourseRepository(self.db).get_by_id(internship.lms_course_id, organization_id)
        if course is None:
            raise ValidationError("The LMS course for this internship no longer exists. Choose another.")
        student_role = await AuthorizationRepository(self.db).get_role_by_slug("student")
        if student_role is None:
            raise ValidationError("The 'student' role is not set up on this ERPX instance, so LMS accounts cannot be created.")

        auth_repo = AuthRepository(self.db)
        student_repo = StudentRepository(self.db)
        email = student.email.strip().lower()
        created = False
        reset_token: str | None = None

        user = await auth_repo.get_user_by_email(email)
        if user is not None:
            erpx_student = await student_repo.get_by_user_id(user.id)
            if erpx_student is None or erpx_student.organization_id != organization_id:
                # silently reusing someone else's account (a staff member's, another organization's) would hand out access
                # to the wrong person; say so and let an admin sort it out
                raise ConflictError(f"An ERPX account already exists for {email} and it is not a student account here.")
        else:
            user = await auth_repo.create_user(
                email=email,
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                full_name=student.name,
                phone_number=(student.phone or None) and student.phone[:32],
            )
            # staff vouch for this address; the account only becomes usable through the set-password link
            user.is_email_verified = True
            user.status = UserStatus.ACTIVE
            await self.db.flush()
            await UserProfileRepository(self.db).create(user_id=user.id, organization_id=organization_id)
            erpx_student = await self._existing_unlinked_student(organization_id, email)
            if erpx_student is None:
                erpx_student = await student_repo.create(
                    organization_id,
                    full_name=student.name,
                    email=email,
                    phone=(student.phone or None) and student.phone[:32],
                    course_name=course.title,
                    enrollment_date=date.today(),
                )
            erpx_student.user_id = user.id
            await self.db.flush()
            created = True

        # the student role may be missing even on an existing account (a hackathon participant has only the restricted one)
        await AuthorizationService(self.db).assign_role(user.id, student_role.id, organization_id, user_id)

        enrollments = EnrollmentRepository(self.db)
        enrollment = await enrollments.get_by_student_and_course(erpx_student.id, course.id)
        new_enrollment = enrollment is None
        if enrollment is None:
            await enrollments.create(student_id=erpx_student.id, course_id=course.id, enrolled_on=date.today())
        elif enrollment.status != EnrollmentStatus.ACTIVE:
            await enrollments.set_status(enrollment, EnrollmentStatus.ACTIVE)
        if new_enrollment:
            await self._join_first_batch(organization_id, course.id, erpx_student.id)

        if created:
            token = await auth_repo.create_password_reset_token(user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS)
            reset_token = token.token

        selection.lms_status = LmsStatus.GRANTED
        selection.lms_user_id = user.id
        selection.lms_student_id = erpx_student.id
        selection.lms_granted_at = datetime.now(timezone.utc)
        selection.lms_granted_by_user_id = user_id
        await self.db.flush()
        return GrantOutcome(created_account=created, email=email, full_name=student.name, reset_token=reset_token, course_title=course.title)

    async def _existing_unlinked_student(self, organization_id: uuid.UUID, email: str) -> Student | None:
        from sqlalchemy import func

        return (
            await self.db.execute(
                select(Student).where(
                    Student.organization_id == organization_id,
                    func.lower(Student.email) == email,
                    Student.deleted_at.is_(None),
                    Student.user_id.is_(None),
                )
            )
        ).scalars().first()

    async def _join_first_batch(self, organization_id: uuid.UUID, course_id: uuid.UUID, student_id: uuid.UUID) -> None:
        """Put a newly enrolled student in the course's first batch, if it has one, so the timetable and live classes have
        something to show straight away. No batch yet is fine: the enrolment alone unlocks the course."""
        batches, _ = await BatchRepository(self.db).list_for_organization(organization_id, course_id=course_id, limit=1)
        if not batches:
            return
        already = (
            await self.db.execute(
                select(BatchEnrollment.id).where(BatchEnrollment.batch_id == batches[0].id, BatchEnrollment.student_id == student_id)
            )
        ).first()
        if already is None:
            await BatchEnrollmentRepository(self.db).create(
                organization_id=organization_id, batch_id=batches[0].id, student_id=student_id, enrolled_at=date.today()
            )

    async def revoke(self, internship: OurInternship, selection: InternshipSelection) -> None:
        """Withdraw LMS access: the course enrolment is dropped (the account itself is left alone, it may be used for other
        things). Access can be granted again afterwards."""
        if selection.lms_status != LmsStatus.GRANTED:
            raise ValidationError("This student does not have LMS access.")
        if selection.lms_student_id and internship.lms_course_id:
            enrollments = EnrollmentRepository(self.db)
            enrollment = await enrollments.get_by_student_and_course(selection.lms_student_id, internship.lms_course_id)
            if enrollment is not None:
                await enrollments.set_status(enrollment, EnrollmentStatus.DROPPED)
        selection.lms_status = LmsStatus.REVOKED
        await self.db.flush()


async def notify_access(outcome: GrantOutcome) -> None:
    """Tell the student. A new account gets the set-password link; someone who already had an account gets a short note.
    Best effort: the access itself is already saved, so a mail problem must not undo it."""
    login_url = f"{settings.STUDENT_PORTAL_URL.rstrip('/')}/login"
    try:
        if outcome.created_account and outcome.reset_token:
            link = f"{settings.STUDENT_PORTAL_URL.rstrip('/')}/reset-password?token={outcome.reset_token}"
            send_password_reset_email_task.delay(outcome.email, outcome.full_name, link, "account_invite")
            return
        text = (
            f"Dear {outcome.full_name},\n\nYour access to the Pentrix LMS is ready. You are now enrolled in {outcome.course_title}.\n\n"
            f"Sign in with your existing account here: {login_url}\n\nRegards,\nPentrix"
        )
        await email_service.send(outcome.email, "Your Pentrix LMS access is ready", text, None)
    except Exception:  # noqa: BLE001
        logger.warning("internship_lms_notice_failed", email=outcome.email, exc_info=True)
