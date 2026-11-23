import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.institutions.models import EventRegistration, Institution, InstitutionEvent, InstitutionStudent
from modules.our_internships.models import InternshipScope, InternshipSelection, OurInternship
from modules.courses.models import Course
from modules.our_internships.onboarding import STAGE_LABELS, OnboardingService, grant_blockers, stage_of
from modules.our_internships.performance import PerformanceBuilder
from modules.our_internships.schemas import SelectedStudent


# The columns of a selection that record something that happened to the student (everything else on the row is identity or audit). A selection
# whose columns all still hold their starting value has nothing to lose; any other value is history and blocks removal.
SELECTION_HISTORY_COLUMNS = {
    "note": "a staff note was written about them",
    "offer_reference": "an offer letter was issued to them",
    "offer_status": "an offer letter was sent or attempted",
    "offer_sent_at": "an offer letter was sent",
    "offer_attempts": "an offer letter was attempted",
    "offer_error": "an offer letter delivery failed and is on record",
    "offer_response": "their answer to the offer was recorded",
    "offer_response_at": "their answer to the offer was recorded",
    "verification_status": "their verification was decided",
    "verification_note": "a verification note was written",
    "verified_at": "their verification was decided",
    "verified_by_user_id": "their verification was decided",
    "payment_status": "a payment status was recorded for them",
    "payment_amount": "a payment amount is recorded",
    "payment_reference": "a payment reference is recorded",
    "payment_received_on": "a payment date is recorded",
    "payment_confirmed_at": "a payment was confirmed",
    "payment_confirmed_by_user_id": "a payment was confirmed",
    "lms_status": "LMS access was granted to them (current or withdrawn)",
    "lms_user_id": "an LMS account was created for them",
    "lms_student_id": "an LMS student record is linked to them",
    "lms_course_id": "they were enrolled in an LMS course through this internship",
    "lms_enrolment_preexisting": "their LMS enrolment predates this internship",
    "lms_granted_at": "LMS access was granted to them",
    "lms_granted_by_user_id": "LMS access was granted to them",
}
# every table with a foreign key to a selection, and so every table whose rows a removal would delete or detach; history_of checks each
SELECTION_REFERENCING_TABLES = {
    "internship_assignment_submissions", "internship_project_choices", "internship_project_submissions", "internship_award_grants",
    "internship_certificate_eligibility", "workshop_exam_attendees", "offer_letters", "internship_onboarding_applications",
}
# columns that are identity or audit, not history
SELECTION_IDENTITY_COLUMNS = {"id", "created_at", "updated_at", "organization_id", "internship_id", "student_id", "selected_by_user_id"}


def _undelivered_offer(selection) -> bool:
    status = str(getattr(selection.offer_status, "value", selection.offer_status))
    return status == "queued" and not selection.offer_attempts and selection.offer_sent_at is None and not selection.offer_error


def _recorded(value) -> bool:
    """True when a column holds something other than its starting value (None, false, 0, empty, or the enum's initial member)."""
    if value is None or value is False or value == 0 or value == "" or value == {} or value == []:
        return False
    # "queued" is an offer waiting to be delivered: nothing has been sent, so on its own it is not history (an attempt, a sent time, a
    # reference or a generated letter all are, and are checked separately)
    return str(getattr(value, "value", value)) not in {"not_sent", "queued", "awaiting", "pending", "not_granted", "none"}


class OurInternshipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ the internship

    async def get(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
        internship = (
            await self.db.execute(
                select(OurInternship).where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if internship is None:
            raise NotFoundError("Internship", internship_id)
        return internship

    async def create(self, organization_id: uuid.UUID, user_id: uuid.UUID, **fields) -> OurInternship:
        institution_id, event_id = fields.get("institution_id"), fields.get("event_id")
        if institution_id is not None:
            institution = (
                await self.db.execute(
                    select(Institution.id).where(Institution.id == institution_id, Institution.organization_id == organization_id)
                )
            ).first()
            if institution is None:
                raise NotFoundError("Institution", institution_id)
        if event_id is not None:
            event = (
                await self.db.execute(
                    select(InstitutionEvent).where(
                        InstitutionEvent.id == event_id, InstitutionEvent.organization_id == organization_id
                    )
                )
            ).scalar_one_or_none()
            if event is None:
                raise NotFoundError("Event", event_id)
            if event.institution_id != institution_id:
                raise ValidationError("That event belongs to a different institution.")
        internship = OurInternship(organization_id=organization_id, created_by_user_id=user_id, **fields)
        self.db.add(internship)
        await self.db.flush()
        await self.db.refresh(internship)
        return internship

    async def update(self, internship: OurInternship, fields: dict) -> OurInternship:
        for key in ("title", "status"):
            if key in fields and fields[key] is None:
                raise ValidationError(f"{key.capitalize()} cannot be empty.")
        confirm_replace = bool(fields.pop("confirm_replace", False))
        if "lms_course_id" in fields:
            await OnboardingService(self.db).set_course(internship, fields.pop("lms_course_id"), confirm_replace=confirm_replace)
        for key, value in fields.items():
            setattr(internship, key, value)
        await self.db.flush()
        return internship

    async def delete(self, internship: OurInternship) -> None:
        await self.db.delete(internship)
        await self.db.flush()

    async def list_all(self, organization_id: uuid.UUID) -> list[OurInternship]:
        return list(
            (
                await self.db.execute(
                    select(OurInternship)
                    .where(OurInternship.organization_id == organization_id)
                    .order_by(OurInternship.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def names(self, internships: list[OurInternship]) -> tuple[dict, dict, dict, dict]:
        """institution names, event names, selected counts and LMS course titles for a batch of internships."""
        institution_ids = {i.institution_id for i in internships if i.institution_id}
        event_ids = {i.event_id for i in internships if i.event_id}
        institutions = {}
        if institution_ids:
            institutions = dict((await self.db.execute(select(Institution.id, Institution.name).where(Institution.id.in_(institution_ids)))).all())
        events = {}
        if event_ids:
            events = dict((await self.db.execute(select(InstitutionEvent.id, InstitutionEvent.name).where(InstitutionEvent.id.in_(event_ids)))).all())
        counts = {}
        ids = [i.id for i in internships]
        if ids:
            counts = dict(
                (
                    await self.db.execute(
                        select(InternshipSelection.internship_id, func.count())
                        .where(InternshipSelection.internship_id.in_(ids))
                        .group_by(InternshipSelection.internship_id)
                    )
                ).all()
            )
        course_ids = {i.lms_course_id for i in internships if i.lms_course_id}
        courses = {}
        if course_ids:
            courses = dict((await self.db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids)))).all())
        return institutions, events, counts, courses

    # ------------------------------------------------------------------ what it may select from

    @staticmethod
    def scope_filters(
        internship: OurInternship, institution_id: uuid.UUID | None, event_id: uuid.UUID | None
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        """The pool is the internship's own scope; a viewer may narrow it further but never widen it."""
        if internship.scope == InternshipScope.INSTITUTION:
            institution_id = internship.institution_id
            if internship.event_id is not None:
                event_id = internship.event_id
        return institution_id, event_id

    async def selected_ids(self, internship_id: uuid.UUID) -> set[uuid.UUID]:
        return {
            sid
            for (sid,) in (
                await self.db.execute(select(InternshipSelection.student_id).where(InternshipSelection.internship_id == internship_id))
            ).all()
        }

    async def performance(
        self,
        internship: OurInternship,
        institution_id: uuid.UUID | None,
        event_id: uuid.UUID | None,
        q: str | None,
    ):
        institution_id, event_id = self.scope_filters(internship, institution_id, event_id)
        return await PerformanceBuilder(self.db).build(
            internship.organization_id,
            institution_id=institution_id,
            event_id=event_id,
            q=q,
            selected_ids=await self.selected_ids(internship.id),
        )

    # ------------------------------------------------------------------ the shortlist

    async def select(
        self, internship: OurInternship, student_ids: list[uuid.UUID], user_id: uuid.UUID, note: str | None
    ) -> tuple[int, int]:
        """Add students to the shortlist. Returns (added, already selected). Only students registered for an event in
        the internship's scope can be chosen."""
        wanted = list(dict.fromkeys(student_ids))
        institution_id, event_id = self.scope_filters(internship, None, None)
        eligible_query = (
            select(EventRegistration.student_id)
            .join(InstitutionEvent, InstitutionEvent.id == EventRegistration.event_id)
            .where(EventRegistration.organization_id == internship.organization_id, EventRegistration.student_id.in_(wanted))
        )
        if institution_id is not None:
            eligible_query = eligible_query.where(InstitutionEvent.institution_id == institution_id)
        if event_id is not None:
            eligible_query = eligible_query.where(InstitutionEvent.id == event_id)
        eligible = {sid for (sid,) in (await self.db.execute(eligible_query)).all()}
        if eligible != set(wanted):
            raise ValidationError("Only students registered for this internship's institution or event can be selected.")
        already = await self.selected_ids(internship.id)
        fresh = [sid for sid in wanted if sid not in already]
        for sid in fresh:
            self.db.add(
                InternshipSelection(
                    organization_id=internship.organization_id,
                    internship_id=internship.id,
                    student_id=sid,
                    selected_by_user_id=user_id,
                    note=note,
                )
            )
        await self.db.flush()
        return len(fresh), len(wanted) - len(fresh)

    async def unselect(self, internship: OurInternship, student_id: uuid.UUID) -> None:
        selection = (
            await self.db.execute(
                select(InternshipSelection).where(
                    InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student_id
                )
            )
        ).scalar_one_or_none()
        if selection is None:
            raise NotFoundError("Selected student", student_id)
        reasons = await self.history_of(selection)
        if reasons:
            # deleting the selection would cascade away everything hanging off it (submissions, project choices, grants, exam results)
            raise ConflictError(
                "This student cannot be removed from the selected list because " + ", ".join(reasons) + ". Their records are kept; "
                "withdraw their LMS access instead (a revoked student stays in the history).",
                details={"code": "has_history", "reasons": reasons},
            )
        await self.db.delete(selection)
        await self.db.flush()

    async def history_of(self, selection: InternshipSelection) -> list[str]:
        """What the student has done or been given on this internship, in words. Empty means nothing would be lost by removing them.

        Removing a selection deletes the row and CASCADES to everything keyed on it, and detaches (SET NULL) the records that merely point at
        it. So this checks (1) every column of the selection that records something that happened to the student, and (2) every table that
        references the selection (tests/api/test_internship_history_preservation.py fails if a new referencing table or column appears that
        this does not know about)."""
        from modules.internship_learning.award_models import AwardGrant
        from modules.internship_learning.certificate_models import CertificateEligibility
        from modules.internship_learning.models import AssignmentSubmission
        from modules.internship_learning.project_models import ProjectChoice, ProjectSubmission
        from modules.internship_onboarding.models import (
            FinancialDocument,
            OnboardingApplication,
            OnboardingDocument,
            OnboardingEvent,
            PaymentOrder,
            PaymentTransaction,
        )
        from modules.our_internships.letter_models import OfferLetter
        from modules.workshop_exams.models import WorkshopExamAttendee

        async def count(model, *where) -> int:
            return (await self.db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()

        reasons = [label for column, label in SELECTION_HISTORY_COLUMNS.items() if _recorded(getattr(selection, column))]
        if _undelivered_offer(selection):
            # released but not yet delivered: the reference number was reserved for it, nothing has reached the student, so the reference
            # alone is not history (a sent, failed or attempted offer, or a generated letter, all still are)
            reasons = [r for r in reasons if r != SELECTION_HISTORY_COLUMNS["offer_reference"]]
        sid = selection.id
        for label, model, column in (
            ("they have assignment submissions", AssignmentSubmission, AssignmentSubmission.selection_id),
            ("they have chosen a project", ProjectChoice, ProjectChoice.selection_id),
            ("they have project submissions", ProjectSubmission, ProjectSubmission.selection_id),
            ("they have been given an award", AwardGrant, AwardGrant.selection_id),
            ("they have a certificate decision", CertificateEligibility, CertificateEligibility.selection_id),
            ("they are on an exam", WorkshopExamAttendee, WorkshopExamAttendee.selection_id),
            ("an offer letter was generated for them", OfferLetter, OfferLetter.selection_id),
        ):
            if await count(model, column == sid):
                reasons.append(label)
        application = (await self.db.execute(select(OnboardingApplication).where(OnboardingApplication.selection_id == sid))).scalar_one_or_none()
        if application is not None:
            app_id = application.id
            started = any(
                _recorded(getattr(application, f))
                for f in (
                    "token_issued_at", "started_at", "accepted_at", "declined_at", "reopened_at", "completed_at", "cancelled_at",
                    "deadline_override_at", "refund_request", "acceptance_meta", "fee_snapshot", "confirmed_phone",
                )
            ) or bool(application.info_proposed) or bool(application.form_responses) or application.info_review_status != "none"
            records = (
                await count(OnboardingDocument, OnboardingDocument.application_id == app_id)
                + await count(OnboardingEvent, OnboardingEvent.application_id == app_id)
                + await count(PaymentOrder, PaymentOrder.application_id == app_id)
                + await count(PaymentTransaction, PaymentTransaction.application_id == app_id)
                + await count(FinancialDocument, FinancialDocument.application_id == app_id)
            )
            if started or records:
                reasons.append("they have onboarding history (responses, documents, events, payments or receipts)")
        return list(dict.fromkeys(reasons))

    async def set_note(self, internship: OurInternship, student_id: uuid.UUID, note: str | None) -> None:
        selection = (
            await self.db.execute(
                select(InternshipSelection).where(
                    InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student_id
                )
            )
        ).scalar_one_or_none()
        if selection is None:
            raise NotFoundError("Selected student", student_id)
        selection.note = note
        await self.db.flush()

    async def selected(self, internship: OurInternship, only_student_id: uuid.UUID | None = None) -> list[SelectedStudent]:
        query = (
            select(InternshipSelection, InstitutionStudent, Institution)
            .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .join(Institution, Institution.id == InstitutionStudent.institution_id)
            .where(InternshipSelection.internship_id == internship.id)
            .order_by(InternshipSelection.created_at)
        )
        if only_student_id is not None:
            query = query.where(InternshipSelection.student_id == only_student_id)
        rows = (await self.db.execute(query)).all()
        if not rows:
            return []
        ids = {student.id for _, student, _ in rows}
        institution_id, event_id = self.scope_filters(internship, None, None)
        board = await PerformanceBuilder(self.db).build(
            internship.organization_id,
            institution_id=institution_id,
            event_id=event_id,
            only_student_ids=ids,
            selected_ids=ids,
            include_teams=True,
        )
        standings: dict[uuid.UUID, list] = {}
        for s in board.students:
            standings.setdefault(s.student_id, []).append(s)
        course_problem = await OnboardingService(self.db).course_problem(internship)
        return [
            SelectedStudent(
                student_id=student.id,
                name=student.name,
                email=student.email,
                phone=student.phone,
                institution_id=institution.id,
                institution_name=institution.name,
                note=selection.note,
                selected_at=selection.created_at,
                offer_reference=selection.offer_reference,
                offer_status=selection.offer_status,
                offer_sent_at=selection.offer_sent_at,
                offer_error=selection.offer_error,
                offer_response=selection.offer_response,
                offer_response_at=selection.offer_response_at,
                verification_status=selection.verification_status,
                verification_note=selection.verification_note,
                verified_at=selection.verified_at,
                payment_status=selection.payment_status,
                payment_amount=float(selection.payment_amount) if selection.payment_amount is not None else None,
                payment_reference=selection.payment_reference,
                payment_received_on=selection.payment_received_on,
                payment_confirmed_at=selection.payment_confirmed_at,
                lms_status=selection.lms_status,
                lms_granted_at=selection.lms_granted_at,
                stage=stage_of(selection),
                stage_label=STAGE_LABELS[stage_of(selection)],
                grant_blockers=grant_blockers(internship, selection, course_problem),
                standings=standings.get(student.id, []),
            )
            for selection, student, institution in rows
        ]
