"""
Certificates of workshop exams: workshop and exam certificates, hackathon award certificates, and an internship's
participation and completion certificates (all three are workshop exams, see modules/workshop_exams).

Only certificates that have been issued -- the attendee holds a certificate number -- are offered. Each one is rendered
by ``render_certificate``, the same function the review preview and the certificate email use, with the attendee's
issued number and any name fix, so the download is the certificate the person received. Nothing is assigned or changed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.authentication.models import User
from modules.bulk_exports.sources.base import (
    DocumentSource,
    ExportItem,
    FilterOption,
    Placeholder,
    Scope,
    custom_placeholders,
    custom_values,
    matches,
)
from modules.our_internships.access import assert_exam_access, assert_internship_access
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee

AWARD_LABELS = {
    "first": "1st place",
    "second": "2nd place",
    "third": "3rd place",
    "participation": "Participation",
    "completion": "Completion",
}

_PLACEHOLDERS = (
    Placeholder("student_name", "Student name", "Asha Rao"),
    Placeholder("email", "Email", "asha@example.com"),
    Placeholder("certificate_id", "Certificate ID", "WS-2026-0042"),
    Placeholder("certificate_title", "Certificate heading", "Certificate of Participation"),
    Placeholder("certificate_type", "Certificate type", "Participation"),
    Placeholder("exam_title", "Exam title", "Cloud Basics Workshop"),
    Placeholder("program_name", "Program (workshop, hackathon or internship)", "Cloud Basics Workshop"),
    Placeholder("issue_date", "Issue date", "2026-10-30"),
    Placeholder("score", "Score", "18"),
)

_STATUSES = (
    FilterOption("sent", "Emailed"),
    FilterOption("not_sent", "Not emailed yet"),
    FilterOption("verified", "Verified"),
    FilterOption("not_verified", "Not verified"),
)

_PRESETS = (
    ("Student name and certificate ID", "{{student_name}}_{{certificate_id}}.pdf"),
    ("Certificate ID only", "{{certificate_id}}.pdf"),
    ("Program, student name", "{{program_name}}_{{student_name}}.pdf"),
    ("Student name, type, certificate ID", "{{student_name}}_{{certificate_type}}_{{certificate_id}}.pdf"),
)


def _status(attendee: WorkshopExamAttendee) -> str:
    return "sent" if attendee.certificate_sent_at else "not_sent"


def _wanted(attendee: WorkshopExamAttendee, status: str | None) -> bool:
    if status in (None, ""):
        return True
    if status in ("sent", "not_sent"):
        return _status(attendee) == status
    if status == "verified":
        return attendee.certificate_verified_at is not None
    if status == "not_verified":
        return attendee.certificate_verified_at is None
    return False


class _CertificateSource(DocumentSource):
    module = "workshop_exams"
    document_type = "Certificate"
    status_options = _STATUSES
    base_placeholders = _PLACEHOLDERS
    presets = _PRESETS
    folder_presets = (("By certificate type", "{{certificate_type}}"), ("By program", "{{program_name}}"))

    async def _program_name(self, db: AsyncSession, exam: WorkshopExam) -> str:
        if exam.internship_id is not None:
            from modules.our_internships.models import OurInternship

            title = (await db.execute(select(OurInternship.title).where(OurInternship.id == exam.internship_id))).scalar_one_or_none()
            return title or exam.title
        if exam.hackathon_id is not None:
            from modules.hackathons.models import Hackathon

            title = (await db.execute(select(Hackathon.title).where(Hackathon.id == exam.hackathon_id))).scalar_one_or_none()
            return title or exam.title
        return exam.title

    async def _prepare(self, db: AsyncSession, scope: Scope, exams: list[WorkshopExam]) -> Scope:
        scope.extra["exams"] = {e.id: e for e in exams}
        scope.extra["programs"] = {e.id: await self._program_name(db, e) for e in exams}
        labels: dict[str, str] = {}
        for exam in exams:
            for f in exam.info_fields or []:
                if isinstance(f, dict) and f.get("key"):
                    labels.setdefault(str(f["key"]), str(f.get("label") or f["key"]))
        scope.extra["custom"] = custom_placeholders(labels, {p.key for p in _PLACEHOLDERS} | {"document_type", "index", "export_date"})
        return scope

    async def placeholders(self, db: AsyncSession, scope: Scope) -> list[Placeholder]:
        return [*_PLACEHOLDERS, *scope.extra["custom"]]

    def _item(self, scope: Scope, exam: WorkshopExam, attendee: WorkshopExamAttendee) -> ExportItem:
        issued = attendee.submitted_at or attendee.created_at
        values: dict[str, object] = {
            "student_name": attendee.name,
            "email": attendee.email,
            "certificate_id": attendee.certificate_number,
            "certificate_title": exam.certificate_heading,
            "certificate_type": AWARD_LABELS.get(exam.award or "", exam.certificate_heading),
            "exam_title": exam.title,
            "program_name": scope.extra["programs"][exam.id],
            "issue_date": issued.date().isoformat() if issued else "",
            "score": "" if attendee.score is None or attendee.certificate_only else attendee.score,
            "document_type": exam.certificate_heading,
            **custom_values(scope.extra["custom"], attendee.info),
        }
        return ExportItem(
            id=attendee.id,
            title=attendee.name,
            subtitle=f"{attendee.certificate_number} · {attendee.email}",
            status=_status(attendee),
            values=values,
            extension="pdf",
            ref=(exam, attendee),
        )

    async def query(self, db: AsyncSession, scope: Scope, search: str | None, status: str | None) -> list[ExportItem]:
        exams: dict[uuid.UUID, WorkshopExam] = scope.extra["exams"]
        if not exams:
            return []
        rows = await db.execute(
            select(WorkshopExamAttendee)
            .where(WorkshopExamAttendee.exam_id.in_(list(exams)), WorkshopExamAttendee.certificate_number.is_not(None))
            .order_by(WorkshopExamAttendee.name, WorkshopExamAttendee.id)
        )
        return [
            self._item(scope, exams[a.exam_id], a)
            for a in rows.scalars()
            if _wanted(a, status) and matches(search, a.name, a.email, a.certificate_number)
        ]

    async def fetch(self, db: AsyncSession, scope: Scope, item: ExportItem) -> bytes:
        from modules.workshop_exams.certificate_render import render_certificate
        from modules.workshop_exams.service import WorkshopExamService

        exam, attendee = item.ref
        templates: dict = scope.extra.setdefault("templates", {})
        if exam.id not in templates:
            templates[exam.id] = await WorkshopExamService(db).get_template(exam.id) if exam.has_certificate_template else None
        return await render_certificate(db, exam, attendee, attendee.certificate_number, template=templates[exam.id])


class ExamCertificatesSource(_CertificateSource):
    """Certificates of one workshop exam (a workshop, a hackathon award, or an internship certificate exam)."""

    key = "exam_certificates"
    label = "Workshop and exam certificates"
    scope_kind = "exam"

    async def open_scope(self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> Scope:
        if scope_id is None:
            raise NotFoundError("Workshop exam", "")
        exam = (
            await db.execute(select(WorkshopExam).where(WorkshopExam.id == scope_id, WorkshopExam.organization_id == organization_id))
        ).scalar_one_or_none()
        if exam is None:
            raise NotFoundError("Workshop exam", scope_id)
        await assert_exam_access(db, user, exam.id, "view")
        return await self._prepare(db, Scope(id=exam.id, label=exam.title, organization_id=organization_id), [exam])


class InternshipCertificatesSource(_CertificateSource):
    """An internship's participation and completion certificates together."""

    key = "internship_certificates"
    label = "Internship participation and completion certificates"
    scope_kind = "internship"
    presets = (
        ("Student name, type, certificate ID", "{{student_name}}_{{certificate_type}}_{{certificate_id}}.pdf"),
        *_PRESETS,
    )

    async def open_scope(self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> Scope:
        from modules.our_internships.models import OurInternship

        if scope_id is None:
            raise NotFoundError("Internship", "")
        internship = (
            await db.execute(select(OurInternship).where(OurInternship.id == scope_id, OurInternship.organization_id == organization_id))
        ).scalar_one_or_none()
        if internship is None:
            raise NotFoundError("Internship", scope_id)
        await assert_internship_access(db, user, internship.id, "view")
        exams = (
            await db.execute(
                select(WorkshopExam)
                .where(
                    WorkshopExam.internship_id == internship.id,
                    WorkshopExam.organization_id == organization_id,
                    WorkshopExam.award.in_(("participation", "completion")),
                )
                .order_by(WorkshopExam.award)
            )
        ).scalars().all()
        return await self._prepare(db, Scope(id=internship.id, label=internship.title, organization_id=organization_id), list(exams))
