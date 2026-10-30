"""
An internship's generated offer letters.

The stored PDF of each student's current letter is copied byte for byte, exactly as it was generated (with its letterhead,
signature and stamp), the same file the single download and the existing ZIP hand out. Letters that are pending, being
generated or failed have no PDF and are not offered.
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
from modules.our_internships.access import assert_internship_access
from modules.our_internships.letter_models import LetterStatus, OfferLetter

_DOWNLOADABLE = (LetterStatus.READY.value, LetterStatus.APPROVED.value, LetterStatus.RELEASED.value)

_PLACEHOLDERS = (
    Placeholder("student_name", "Student name", "Asha Rao"),
    Placeholder("email", "Email", "asha@example.com"),
    Placeholder("institution_name", "Institution", "City Engineering College"),
    Placeholder("reference", "Letter reference", "GIR-INT-2026-0042"),
    Placeholder("internship_title", "Internship", "Cloud Internship 2026"),
    Placeholder("program_name", "Program", "Cloud Internship 2026"),
    Placeholder("version", "Letter version", "1"),
    Placeholder("letter_status", "Letter status", "released"),
    Placeholder("generated_date", "Generated on", "2026-10-30"),
)


class OfferLettersSource(DocumentSource):
    key = "offer_letters"
    label = "Internship offer letters"
    module = "our_internships"
    document_type = "Offer Letter"
    scope_kind = "internship"
    status_options = (
        FilterOption("ready", "Generated"),
        FilterOption("approved", "Approved"),
        FilterOption("released", "Released"),
    )
    base_placeholders = _PLACEHOLDERS
    presets = (
        ("Student name and reference", "{{student_name}}_{{reference}}.pdf"),
        ("Institution, student name", "{{institution_name}}_{{student_name}}.pdf"),
        ("Program, student name", "{{program_name}}_{{student_name}}.pdf"),
    )
    folder_presets = (("By institution", "{{institution_name}}"), ("By letter status", "{{letter_status}}"))

    async def open_scope(self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> Scope:
        from modules.institutions.models import InstitutionStudent
        from modules.our_internships.models import OurInternship

        if scope_id is None:
            raise NotFoundError("Internship", "")
        internship = (
            await db.execute(select(OurInternship).where(OurInternship.id == scope_id, OurInternship.organization_id == organization_id))
        ).scalar_one_or_none()
        if internship is None:
            raise NotFoundError("Internship", scope_id)
        await assert_internship_access(db, user, internship.id, "view")
        # The student's imported columns (registration number, branch, ...) become placeholders.
        details = (
            await db.execute(
                select(InstitutionStudent.id, InstitutionStudent.details)
                .join(OfferLetter, OfferLetter.student_id == InstitutionStudent.id)
                .where(
                    OfferLetter.internship_id == internship.id,
                    OfferLetter.is_current.is_(True),
                    InstitutionStudent.organization_id == organization_id,
                )
            )
        ).all()
        labels: dict[str, str] = {}
        for _, data in details:
            for name in (data or {}):
                labels.setdefault(str(name), str(name))
        taken = {p.key for p in _PLACEHOLDERS} | {"document_type", "index", "export_date"}
        return Scope(
            id=internship.id,
            label=internship.title,
            organization_id=organization_id,
            extra={
                "internship": internship,
                "details": {sid: data or {} for sid, data in details},
                "custom": custom_placeholders(labels, taken),
            },
        )

    async def placeholders(self, db: AsyncSession, scope: Scope) -> list[Placeholder]:
        return [*_PLACEHOLDERS, *scope.extra["custom"]]

    async def query(self, db: AsyncSession, scope: Scope, search: str | None, status: str | None) -> list[ExportItem]:
        internship = scope.extra["internship"]
        statuses = (status,) if status in _DOWNLOADABLE else _DOWNLOADABLE
        if status and status not in _DOWNLOADABLE:
            return []
        rows = await db.execute(
            select(OfferLetter)
            .where(
                OfferLetter.internship_id == internship.id,
                OfferLetter.organization_id == scope.organization_id,
                OfferLetter.is_current.is_(True),
                OfferLetter.status.in_(statuses),
                OfferLetter.pdf_size.is_not(None),
            )
            .order_by(OfferLetter.student_name, OfferLetter.id)
        )
        items = []
        for letter in rows.scalars():
            if not matches(search, letter.student_name, letter.student_email, letter.reference, letter.institution_name):
                continue
            values: dict[str, object] = {
                "student_name": letter.student_name,
                "email": letter.student_email,
                "institution_name": letter.institution_name,
                "reference": letter.reference,
                "internship_title": internship.title,
                "program_name": internship.title,
                "version": letter.version,
                "letter_status": letter.status,
                "generated_date": letter.generated_at.date().isoformat() if letter.generated_at else "",
                **custom_values(scope.extra["custom"], scope.extra["details"].get(letter.student_id)),
            }
            items.append(
                ExportItem(
                    id=letter.id,
                    title=letter.student_name,
                    subtitle=f"{letter.reference} · {letter.institution_name}",
                    status=letter.status,
                    values=values,
                    extension="pdf",
                )
            )
        return items

    async def fetch(self, db: AsyncSession, scope: Scope, item: ExportItem) -> bytes:
        data = (
            await db.execute(
                select(OfferLetter.pdf_data)
                .where(OfferLetter.id == item.id, OfferLetter.organization_id == scope.organization_id)
            )
        ).scalar_one_or_none()
        if not data:
            raise NotFoundError("Offer letter", item.id)
        return bytes(data)
