"""
Participation and completion certificates of an internship.

Each kind is a certificate-only workshop exam that belongs to the internship (`internship_id` + `award`), created on first
use -- the same device the hackathon award certificates use. That is what gives these certificates everything the exam
certificates have: an uploaded PNG/JPG design with the name (and ID) positioned on it, the ID format, review before
sending, per-person fixes, preview and test emails, public verification, and delivery by email.

Staff choose, per student, which one certificate they are eligible for. A student holds one choice only, so they can never
be on both lists, and once their certificate has been created the choice is fixed.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from modules.internship_learning.certificate_models import CertificateEligibility, CertificateKind
from modules.internship_learning.service import InternshipLearningService
from modules.our_internships.models import OurInternship
from modules.workshop_exams.certificate_template import CertificateLayout
from modules.workshop_exams.hackathon_certificates import HackathonCertificates, Plan
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee, WorkshopExamStatus
from modules.workshop_exams.service import WorkshopExamService

KINDS = tuple(k.value for k in CertificateKind)
LABELS = {"participation": "Participation", "completion": "Completion"}


@dataclass
class Person:
    full_name: str
    email: str | None
    team_name: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CertificateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning = InternshipLearningService(db)
        self.exams = WorkshopExamService(db)
        self.certificates = HackathonCertificates(db)

    # ---------------- the two certificate exams ----------------

    async def existing_exams(self, internship_id: uuid.UUID) -> dict[str, WorkshopExam]:
        rows = await self.db.execute(
            select(WorkshopExam).where(WorkshopExam.internship_id == internship_id, WorkshopExam.award.in_(KINDS))
        )
        return {e.award: e for e in rows.scalars()}

    async def ensure_exams(self, internship: OurInternship) -> dict[str, WorkshopExam]:
        exams = await self.existing_exams(internship.id)
        for kind in KINDS:
            if kind in exams:
                continue
            completion = kind == "completion"
            exams[kind] = await self.exams.create_exam(
                internship.organization_id,
                title=f"{internship.title}: {LABELS[kind]} certificate"[:255],
                duration_minutes=30,
                status=WorkshopExamStatus.DRAFT,
                internship_id=internship.id,
                award=kind,
                certificate_heading="Certificate of Completion" if completion else "Certificate of Participation",
                certificate_text=(
                    f'has successfully completed the internship "{internship.title}".'
                    if completion
                    else f'has participated in the internship "{internship.title}".'
                ),
                certificate_layout=CertificateLayout().model_dump(),
            )
        return exams

    # ---------------- who is eligible, and where each certificate stands ----------------

    async def _eligibility(self, internship_id: uuid.UUID) -> dict[uuid.UUID, CertificateEligibility]:
        rows = await self.db.execute(select(CertificateEligibility).where(CertificateEligibility.internship_id == internship_id))
        return {r.selection_id: r for r in rows.scalars()}

    async def _attendees(self, exams: dict[str, WorkshopExam]) -> dict[tuple[str, str], WorkshopExamAttendee]:
        if not exams:
            return {}
        by_exam = {e.id: kind for kind, e in exams.items()}
        rows = await self.db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id.in_(list(by_exam))))
        return {(by_exam[a.exam_id], a.email): a for a in rows.scalars()}

    async def rows(self, internship: OurInternship, exams: dict[str, WorkshopExam] | None = None) -> list[dict]:
        exams = exams if exams is not None else await self.existing_exams(internship.id)
        eligibility = await self._eligibility(internship.id)
        attendees = await self._attendees(exams)
        out = []
        for selection, person in await self.learning.enrolled(internship.id):
            chosen = eligibility.get(selection.id)
            kind = chosen.kind.value if chosen else None
            email = person.email.strip().lower()
            attendee = attendees.get((kind, email)) if kind else None
            other = [k for k in KINDS if k != kind and (k, email) in attendees]
            out.append(
                {
                    "selection_id": selection.id,
                    "student_name": person.name,
                    "student_email": person.email,
                    "kind": kind,
                    "delivery": self._delivery(kind, attendee, exams.get(kind) if kind else None),
                    "certificate_number": attendee.certificate_number if attendee else None,
                    "sent_at": attendee.certificate_sent_at if attendee else None,
                    # a certificate of the other kind already exists for this student (nothing can change then)
                    "locked": attendee is not None or bool(other),
                }
            )
        return out

    @staticmethod
    def _delivery(kind: str | None, attendee: WorkshopExamAttendee | None, exam: WorkshopExam | None) -> str:
        if kind is None:
            return "not_selected"
        if attendee is None:
            return "not_created"
        if attendee.certificate_sent_at is not None:
            return "sent"
        if exam is not None and exam.certificate_review and attendee.certificate_verified_at is None:
            return "held_for_review"
        return "queued"

    async def set_kind(
        self, internship: OurInternship, selection_ids: list[uuid.UUID], kind: str | None, user_id: uuid.UUID
    ) -> None:
        """Make these students eligible for `kind` (or, with None, for nothing). One certificate per student: choosing the
        other kind moves them. A student whose certificate has been created cannot be changed."""
        if kind is not None and kind not in KINDS:
            raise ValidationError("Choose participation or completion.")
        rows = {r["selection_id"]: r for r in await self.rows(internship)}
        unknown = [s for s in selection_ids if s not in rows]
        if unknown:
            raise ValidationError("Certificates can only go to students who have LMS access on this internship.")
        existing = await self._eligibility(internship.id)
        for selection_id in dict.fromkeys(selection_ids):
            row = rows[selection_id]
            if row["kind"] == kind:
                continue
            if row["locked"]:
                raise ConflictError(f"{row['student_name']} already has a certificate, so their choice cannot be changed.")
            if kind is None:
                await self.db.execute(
                    delete(CertificateEligibility).where(
                        CertificateEligibility.internship_id == internship.id, CertificateEligibility.selection_id == selection_id
                    )
                )
                continue
            current = existing.get(selection_id)
            if current:
                current.kind, current.chosen_at, current.chosen_by_user_id = CertificateKind(kind), _now(), user_id
            else:
                self.db.add(
                    CertificateEligibility(
                        organization_id=internship.organization_id,
                        internship_id=internship.id,
                        selection_id=selection_id,
                        kind=CertificateKind(kind),
                        chosen_at=_now(),
                        chosen_by_user_id=user_id,
                    )
                )
        await self.db.flush()

    # ---------------- preview and issue ----------------

    async def people(self, internship: OurInternship) -> dict[str, list[Person]]:
        eligibility = await self._eligibility(internship.id)
        people: dict[str, list[Person]] = {k: [] for k in KINDS}
        for selection, person in await self.learning.enrolled(internship.id):
            chosen = eligibility.get(selection.id)
            if chosen:
                people[chosen.kind.value].append(Person(person.name, person.email))
        return people

    async def plan(self, internship: OurInternship, exam: WorkshopExam, people: list[Person]) -> Plan:
        return await self.certificates.plan_for(exam, internship.title, people)

    async def issue(self, exam: WorkshopExam, plan: Plan) -> list[uuid.UUID]:
        return await self.certificates.issue(exam, plan)
