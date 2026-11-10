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

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
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
from modules.batches.models import Batch, BatchEnrollment, BatchEnrollmentStatus, BatchStatus
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.chapters.models import Chapter
from modules.courses.models import Course, CourseType
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


def grant_blockers(internship: OurInternship, selection: InternshipSelection, course_problem: str | None = None) -> list[str]:
    """Everything that currently stops LMS access being granted, in words (empty means it can be granted). ``course_problem`` is
    what is wrong with the chosen course itself (not published, no chapters), found once with ``OnboardingService.course_problem``."""
    blockers: list[str] = []
    if selection.lms_status == LmsStatus.GRANTED:
        return ["LMS access has already been granted."]
    if internship.lms_course_id is None:
        blockers.append("Choose the LMS course for this internship first.")
    elif course_problem:
        blockers.append(course_problem)
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
    internship_title: str = ""


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

    async def course_options(self, internship: OurInternship) -> list[dict]:
        """The courses this internship can use: the organization's internship courses, plus the one it already uses (a regular
        course linked before course types existed stays selectable so the screen can show it). Each says whether it is ready to
        enrol students in, and which other internships use it."""
        from modules.our_internships.course_links import linked_internships

        repo = CourseRepository(self.db)
        courses, _ = await repo.list_for_organization(internship.organization_id, limit=200, course_type=CourseType.INTERNSHIP)
        current = internship.lms_course_id
        if current is not None and all(c.id != current for c in courses):
            existing = await repo.get_by_id(current, internship.organization_id)
            if existing is not None:
                courses = [existing, *courses]
        counts = dict(
            (
                await self.db.execute(
                    select(Chapter.course_id, func.count()).where(Chapter.course_id.in_([c.id for c in courses])).group_by(Chapter.course_id)
                )
            ).all()
        ) if courses else {}
        links = await linked_internships(self.db, internship.organization_id, [c.id for c in courses])
        out = []
        for c in courses:
            problem = None
            if not c.is_published:
                problem = "Not published yet."
            elif not counts.get(c.id):
                problem = "Has no chapters yet."
            out.append(
                {
                    "id": c.id, "title": c.title, "is_published": c.is_published, "course_type": c.course_type.value,
                    "level": c.level.value, "duration_hours": c.duration_hours, "is_current": c.id == current,
                    "ready": problem is None, "problem": problem,
                    "also_used_by": [i.title for i in links.get(c.id, []) if i.id != internship.id],
                }
            )
        return out

    async def course_problem(self, internship: OurInternship) -> str | None:
        """What stops students being enrolled in this internship's course, or None when it is ready: it must exist, be published
        and have at least one chapter."""
        if internship.lms_course_id is None:
            return None
        course = await CourseRepository(self.db).get_by_id(internship.lms_course_id, internship.organization_id)
        if course is None:
            return "The LMS course for this internship no longer exists. Choose another."
        if not course.is_published:
            return f"The LMS course \"{course.title}\" is not published yet. Publish it first."
        if not await ChapterRepository(self.db).list_for_course(course.id):
            return f"The LMS course \"{course.title}\" has no chapters yet. Add its content first."
        return None

    async def enrolled_count(self, internship: OurInternship) -> int:
        """Students on this internship whose LMS access is currently granted (each holds a live enrolment in the course)."""
        return (
            await self.db.execute(
                select(func.count()).select_from(InternshipSelection).where(
                    InternshipSelection.internship_id == internship.id, InternshipSelection.lms_status == LmsStatus.GRANTED
                )
            )
        ).scalar_one()

    async def set_course(self, internship: OurInternship, course_id: uuid.UUID | None, *, confirm_replace: bool = False) -> None:
        """Choose (or clear) the course. Linking a first course is always allowed. Replacing or clearing one needs the caller's
        confirmation, and is refused outright while students hold access through it: they would be left in the old course with
        nothing in ERPX pointing at it. Nobody is ever moved between courses silently."""
        # one change at a time, and never while a grant is part-way: grants hold this row shared, this holds it exclusively
        await self.db.refresh(internship, with_for_update=True)
        if course_id == internship.lms_course_id:
            return
        course = None
        if course_id is not None:
            course = await CourseRepository(self.db).get_by_id(course_id, internship.organization_id)
            if course is None:
                raise NotFoundError("Course", course_id)
            if course.course_type != CourseType.INTERNSHIP:
                raise ValidationError(
                    f'"{course.title}" is a regular course. Only an Internship Course can be linked to an internship: '
                    "change its type on the course's edit screen, or create an internship course."
                )
        if internship.lms_course_id is not None:
            current = await CourseRepository(self.db).get_by_id(internship.lms_course_id, internship.organization_id)
            name = f'"{current.title}"' if current else "the current course"
            held = await self.enrolled_count(internship)
            if held:
                raise ConflictError(
                    f"{held} student{'s' if held != 1 else ''} already {'have' if held != 1 else 'has'} LMS access through {name}. "
                    "The course cannot be changed while students are enrolled: revoke their access first, or keep this course.",
                    details={"code": "course_in_use", "enrolled": held},
                )
            if not confirm_replace:
                raise ConflictError(
                    f"This internship already uses {name}. Confirm to replace it.", details={"code": "confirm_replace", "current_course_id": str(internship.lms_course_id)}
                )
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
        # a manual grant and the automatic one can arrive together: take this student's row first, then look again, so two of
        # them never both create the enrolment
        await self.db.refresh(selection, with_for_update=True)
        await self.db.refresh(internship, with_for_update={"read": True})  # the course cannot be changed while this grant is in flight
        blockers = grant_blockers(internship, selection, await self.course_problem(internship))
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

        if await self._ensure_enrolment(erpx_student.id, course.id):
            await self._join_batch(organization_id, course.id, erpx_student.id)

        if created:
            token = await auth_repo.create_password_reset_token(user.id, ttl_hours=SET_PASSWORD_TOKEN_TTL_HOURS)
            reset_token = token.token

        selection.lms_status = LmsStatus.GRANTED
        selection.lms_course_id = course.id  # remembered, so revoking later drops THIS course even if the internship is relinked
        selection.lms_user_id = user.id
        selection.lms_student_id = erpx_student.id
        selection.lms_granted_at = datetime.now(timezone.utc)
        selection.lms_granted_by_user_id = user_id
        await self.db.flush()
        return GrantOutcome(created_account=created, email=email, full_name=student.name, reset_token=reset_token, course_title=course.title, internship_title=internship.title)

    async def _ensure_enrolment(self, student_id: uuid.UUID, course_id: uuid.UUID) -> bool:
        """Make sure the student has a live enrolment in the course, without ever making a second one. True when this call created it or
        brought a dropped one back (a live or finished one is left as it is). Two grants for the same person (two internships, or a manual
        and an automatic one) can arrive together: the database allows one enrolment per student and course, so the loser of the race
        finds the winner's row instead of failing."""
        enrollments = EnrollmentRepository(self.db)
        enrollment = await enrollments.get_by_student_and_course(student_id, course_id)
        if enrollment is None:
            try:
                async with self.db.begin_nested():
                    await enrollments.create(student_id=student_id, course_id=course_id, enrolled_on=date.today())
                return True
            except IntegrityError:
                enrollment = await enrollments.get_by_student_and_course(student_id, course_id)
                if enrollment is None:
                    raise
        if enrollment.status == EnrollmentStatus.DROPPED:
            await enrollments.set_status(enrollment, EnrollmentStatus.ACTIVE)  # access given again; a finished course stays finished
            return True
        return False

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

    async def _join_batch(self, organization_id: uuid.UUID, course_id: uuid.UUID, student_id: uuid.UUID) -> None:
        """Put a newly enrolled student in the batch they should start with, if the course has one, so the timetable and live
        classes have something to show straight away: the soonest batch that has not started yet, else the one that started most
        recently and has not ended. Finished and cancelled batches are never chosen. No batch is fine: the enrolment alone unlocks
        the course."""
        today = date.today()
        open_batches = (
            await self.db.execute(
                select(Batch).where(
                    Batch.organization_id == organization_id,
                    Batch.course_id == course_id,
                    Batch.status.in_([BatchStatus.UPCOMING, BatchStatus.ONGOING]),
                    or_(Batch.end_date.is_(None), Batch.end_date >= today),
                ).order_by(Batch.start_date.asc())
            )
        ).scalars().all()
        upcoming = [b for b in open_batches if b.status == BatchStatus.UPCOMING]
        ongoing = [b for b in open_batches if b.status == BatchStatus.ONGOING]
        batch = upcoming[0] if upcoming else (ongoing[-1] if ongoing else None)
        if batch is None:
            return
        already = (
            await self.db.execute(select(BatchEnrollment).where(BatchEnrollment.batch_id == batch.id, BatchEnrollment.student_id == student_id))
        ).scalars().first()
        if already is None:
            await BatchEnrollmentRepository(self.db).create(
                organization_id=organization_id, batch_id=batch.id, student_id=student_id, enrolled_at=date.today()
            )
        elif already.status != BatchEnrollmentStatus.ACTIVE:
            already.status = BatchEnrollmentStatus.ACTIVE  # access given again after a revoke

    async def revoke(self, internship: OurInternship, selection: InternshipSelection) -> None:
        """Withdraw LMS access: the enrolment in the course THIS student was given is dropped (the account itself is left alone, it
        may be used for other things), however the internship has been linked since. If the same student also holds access to
        that course through another internship, their enrolment stays. Access can be granted again afterwards."""
        await self.db.refresh(selection, with_for_update=True)
        if selection.lms_status != LmsStatus.GRANTED:
            raise ValidationError("This student does not have LMS access.")
        course_id = selection.lms_course_id or internship.lms_course_id  # (the fallback is for access granted before the column existed)
        if selection.lms_student_id and course_id:
            also_through_another = (
                await self.db.execute(
                    select(func.count()).select_from(InternshipSelection).where(
                        InternshipSelection.id != selection.id,
                        InternshipSelection.lms_student_id == selection.lms_student_id,
                        InternshipSelection.lms_course_id == course_id,
                        InternshipSelection.lms_status == LmsStatus.GRANTED,
                    )
                )
            ).scalar_one()
            enrollments = EnrollmentRepository(self.db)
            enrollment = await enrollments.get_by_student_and_course(selection.lms_student_id, course_id)
            if enrollment is not None and not also_through_another and enrollment.status != EnrollmentStatus.DROPPED:
                await enrollments.set_status(enrollment, EnrollmentStatus.DROPPED)
            if not also_through_another:
                # the timetable and live classes follow batch membership, so the batches OF THIS COURSE go with the enrolment
                # (their batches for other courses are left alone)
                await self.db.execute(
                    update(BatchEnrollment)
                    .where(
                        BatchEnrollment.student_id == selection.lms_student_id,
                        BatchEnrollment.status == BatchEnrollmentStatus.ACTIVE,
                        BatchEnrollment.batch_id.in_(select(Batch.id).where(Batch.course_id == course_id)),
                    )
                    .values(status=BatchEnrollmentStatus.REMOVED)
                    .execution_options(synchronize_session=False)
                )
        selection.lms_status = LmsStatus.REVOKED
        await self.db.flush()


async def notify_access(outcome: GrantOutcome) -> None:
    """Tell the student. A new account gets the set-password link; someone who already had an account gets a short note.
    Best effort: the access itself is already saved, so a mail problem must not undo it."""
    login_url = f"{settings.STUDENT_PORTAL_URL.rstrip('/')}/login"
    try:
        if outcome.created_account and outcome.reset_token:
            link = f"{settings.STUDENT_PORTAL_URL.rstrip('/')}/reset-password?token={outcome.reset_token}"
            # one email, not two: the secure set-password link, inside a welcome that names the internship and the course
            send_password_reset_email_task.delay(
                outcome.email, outcome.full_name, link, "internship_access",
                {"internship_title": outcome.internship_title, "course_title": outcome.course_title, "login_url": login_url, "link_valid_hours": SET_PASSWORD_TOKEN_TTL_HOURS},
            )
            return
        from app.db.session import get_db_context
        from modules.email_templates.render import render_email

        async with get_db_context() as db:
            subject, text, html = await render_email(
                db,
                "internship_welcome",
                {"full_name": outcome.full_name, "internship_title": outcome.internship_title, "course_title": outcome.course_title, "login_url": login_url},
                recipient_email=outcome.email,
            )
        await email_service.send(outcome.email, subject, text, html)
    except Exception:  # noqa: BLE001
        logger.warning("internship_lms_notice_failed", email=outcome.email, exc_info=True)
