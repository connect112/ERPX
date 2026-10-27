"""
Offer letters for an internship: the template and where details go on it, the email, and releasing the letters.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError, ValidationError
from modules.institutions.models import Institution, InstitutionStudent
from modules.our_internships.models import InternshipSelection, OfferStatus, OurInternship, OurInternshipStatus
from modules.our_internships.offer_letter import (
    DEFAULT_BODY,
    DEFAULT_SUBJECT,
    FIELD_LABELS,
    PLACEHOLDERS,
    OfferLayout,
    TemplateError,
    attachment_name,
    build_offer_pdf,
    inspect_template,
    render_offer_email,
    unknown_placeholders,
)
from modules.our_internships.schemas import OfferSettings
from packages.email.service import EmailAttachment, email_service

SAMPLE_NAME = "Asha Rao"


def letter_date(internship: OurInternship) -> str:
    day = internship.offer_date or date.today()
    return f"{day.day} {day.strftime('%B %Y')}"


class OfferService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ loading

    async def get(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
        """The internship with its template document loaded (the bytes are not part of ordinary reads)."""
        internship = (
            await self.db.execute(
                select(OurInternship)
                .options(undefer(OurInternship.offer_template_data))
                .where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if internship is None:
            raise NotFoundError("Internship", internship_id)
        return internship

    @staticmethod
    def layout_of(internship: OurInternship) -> OfferLayout | None:
        return OfferLayout.model_validate(internship.offer_layout) if internship.offer_layout else None

    # ------------------------------------------------------------------ template

    async def set_template(self, internship: OurInternship, filename: str, data: bytes) -> None:
        try:
            pages = inspect_template(data)
        except TemplateError as exc:
            raise ValidationError(str(exc)) from exc
        internship.offer_template_filename = " ".join(filename.split())[:255] or "offer-letter.pdf"
        internship.offer_template_size = len(data)
        internship.offer_template_pages = pages
        internship.offer_template_data = data
        layout = self.layout_of(internship)
        # a new template with fewer pages cannot keep fields placed on pages it no longer has
        if layout and any(f.page > pages for f in layout.fields):
            internship.offer_layout = OfferLayout(fields=[f for f in layout.fields if f.page <= pages]).model_dump()
        await self.db.flush()

    async def remove_template(self, internship: OurInternship) -> None:
        if await self._count(internship.id, None, only_released=True):
            raise ConflictError("Offers have already been sent with this template, so it cannot be removed.")
        internship.offer_template_filename = None
        internship.offer_template_size = None
        internship.offer_template_pages = None
        internship.offer_template_data = None
        internship.offer_layout = None
        await self.db.flush()

    async def set_layout(self, internship: OurInternship, layout: OfferLayout) -> None:
        if not internship.offer_template_data:
            raise ValidationError("Upload the offer letter PDF first.")
        pages = internship.offer_template_pages or 1
        for field in layout.fields:
            if field.page > pages:
                raise ValidationError(f"The letter has {pages} page{'s' if pages != 1 else ''}; page {field.page} does not exist.")
        internship.offer_layout = layout.model_dump()
        await self.db.flush()

    # ------------------------------------------------------------------ email

    async def set_email(self, internship: OurInternship, subject: str | None, body: str | None, offer_date: date | None) -> None:
        bad = unknown_placeholders(subject or "", body or "")
        if bad:
            raise ValidationError(
                "These placeholders are not recognised: " + ", ".join("{{" + b + "}}" for b in bad)
                + ". Use: " + ", ".join("{{" + k + "}}" for k in PLACEHOLDERS) + "."
            )
        internship.offer_email_subject = subject
        internship.offer_email_body = body
        internship.offer_date = offer_date
        await self.db.flush()

    # ------------------------------------------------------------------ settings and readiness

    async def _count(self, internship_id: uuid.UUID, status: OfferStatus | None, only_released: bool = False) -> int:
        query = select(func.count()).select_from(InternshipSelection).where(InternshipSelection.internship_id == internship_id)
        if only_released:
            query = query.where(InternshipSelection.offer_status.in_([OfferStatus.QUEUED, OfferStatus.SENT]))
        elif status is not None:
            query = query.where(InternshipSelection.offer_status == status)
        return (await self.db.execute(query)).scalar_one()

    async def counts(self, internship_id: uuid.UUID) -> dict[str, int]:
        rows = (
            await self.db.execute(
                select(InternshipSelection.offer_status, func.count())
                .where(InternshipSelection.internship_id == internship_id)
                .group_by(InternshipSelection.offer_status)
            )
        ).all()
        counts = {s.value: 0 for s in OfferStatus}
        for status, count in rows:
            counts[status.value] = count
        counts["selected"] = sum(counts.values())
        return counts

    async def settings(self, internship: OurInternship) -> OfferSettings:
        counts = await self.counts(internship.id)
        layout = self.layout_of(internship)
        missing: list[str] = []
        if not internship.offer_template_data:
            missing.append("Upload the offer letter as a PDF.")
        elif layout is None or not any(f.key == "name" for f in layout.fields):
            missing.append("Mark where the student's name goes on the letter.")
        if counts["selected"] == 0:
            missing.append("Select at least one student.")
        return OfferSettings(
            has_template=bool(internship.offer_template_data),
            template_filename=internship.offer_template_filename,
            template_pages=internship.offer_template_pages,
            template_size=internship.offer_template_size,
            layout=layout,
            email_subject=internship.offer_email_subject or DEFAULT_SUBJECT,
            email_body=internship.offer_email_body or DEFAULT_BODY,
            email_is_default=internship.offer_email_subject is None and internship.offer_email_body is None,
            offer_date=internship.offer_date,
            placeholders=PLACEHOLDERS,
            field_labels=FIELD_LABELS,
            released_at=internship.offers_released_at,
            missing=missing,
            counts=counts,
        )

    # ------------------------------------------------------------------ letters

    def _require_template(self, internship: OurInternship, layout: OfferLayout | None) -> OfferLayout:
        if not internship.offer_template_data:
            raise ValidationError("Upload the offer letter PDF first.")
        if layout is None or not any(f.key == "name" for f in layout.fields):
            raise ValidationError("Mark where the student's name goes on the letter first.")
        return layout

    def values_for(self, internship: OurInternship, name: str, institution: str, reference: str) -> dict[str, str]:
        return {
            "name": name,
            "institution": institution,
            "internship": internship.title,
            "date": letter_date(internship),
            "reference": reference,
        }

    @staticmethod
    def sample_reference(internship: OurInternship) -> str:
        return f"OFR-{datetime.now(timezone.utc).year}-{internship.id.hex[:4].upper()}-001"

    def sample_letter(self, internship: OurInternship, layout: OfferLayout | None = None) -> bytes:
        layout = self._require_template(internship, layout or self.layout_of(internship))
        values = self.values_for(internship, SAMPLE_NAME, "Sri Venkateswara College", self.sample_reference(internship))
        return build_offer_pdf(internship.offer_template_data, layout, values)

    async def _selection(self, internship: OurInternship, student_id: uuid.UUID):
        row = (
            await self.db.execute(
                select(InternshipSelection, InstitutionStudent, Institution)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .join(Institution, Institution.id == InstitutionStudent.institution_id)
                .where(InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Selected student", student_id)
        return row

    async def student_letter(self, internship: OurInternship, student_id: uuid.UUID) -> tuple[bytes, str]:
        """The letter exactly as it would be sent to this student (a reference number is shown once one has been given)."""
        selection, student, institution = await self._selection(internship, student_id)
        layout = self._require_template(internship, self.layout_of(internship))
        reference = selection.offer_reference or self.sample_reference(internship)
        pdf = build_offer_pdf(internship.offer_template_data, layout, self.values_for(internship, student.name, institution.name, reference))
        return pdf, attachment_name(student.name)

    async def send_test(self, internship: OurInternship, to_email: str) -> None:
        """Send the real email with a sample letter to one address, so the wording and the stamping can be checked."""
        layout = self._require_template(internship, self.layout_of(internship))
        reference = self.sample_reference(internship)
        pdf = build_offer_pdf(
            internship.offer_template_data, layout, self.values_for(internship, SAMPLE_NAME, "Sri Venkateswara College", reference)
        )
        subject, text, html = render_offer_email(
            internship.offer_email_subject,
            internship.offer_email_body,
            {"full_name": SAMPLE_NAME, "internship_title": internship.title, "institution": "Sri Venkateswara College", "reference": reference},
        )
        sent = await email_service.send(
            to_email, "[Test] " + subject, text, html,
            attachments=[EmailAttachment(filename=attachment_name(SAMPLE_NAME), content=pdf, mime_type="application/pdf")],
        )
        if not sent:
            raise ServiceUnavailableError("The test email could not be sent. Check the email (SMTP) settings.")

    # ------------------------------------------------------------------ release

    async def release(
        self, internship: OurInternship, student_ids: list[uuid.UUID] | None, resend: bool
    ) -> tuple[list[uuid.UUID], int]:
        """Mark the chosen selections as queued and give each a reference number. Returns (selection ids to send,
        number skipped because their offer was already sent)."""
        self._require_template(internship, self.layout_of(internship))
        selections = list(
            (
                await self.db.execute(
                    select(InternshipSelection)
                    .where(InternshipSelection.internship_id == internship.id)
                    .order_by(InternshipSelection.created_at, InternshipSelection.id)
                )
            )
            .scalars()
            .all()
        )
        if not selections:
            raise ValidationError("Select at least one student before releasing offers.")
        chosen = selections
        if student_ids is not None:
            wanted = set(student_ids)
            chosen = [s for s in selections if s.student_id in wanted]
            if len(chosen) != len(wanted):
                raise ValidationError("Only students on the selected list can be sent an offer.")
        already_sent = 0
        targets: list[InternshipSelection] = []
        for selection in chosen:
            if selection.offer_status == OfferStatus.SENT and not resend:
                already_sent += 1
            elif selection.offer_status == OfferStatus.QUEUED and not resend:
                continue  # on its way already
            else:
                targets.append(selection)
        taken = {s.offer_reference for s in selections if s.offer_reference}
        year = datetime.now(timezone.utc).year
        sequence = len(taken)
        for selection in targets:
            if not selection.offer_reference:
                while True:
                    sequence += 1
                    reference = f"OFR-{year}-{internship.id.hex[:4].upper()}-{sequence:03d}"
                    if reference not in taken:
                        break
                taken.add(reference)
                selection.offer_reference = reference
            selection.offer_status = OfferStatus.QUEUED
            selection.offer_attempts = 0
            selection.offer_error = None
        if targets:
            internship.status = OurInternshipStatus.OFFERS_RELEASED
            internship.offers_released_at = internship.offers_released_at or datetime.now(timezone.utc)
        await self.db.flush()
        return [s.id for s in targets], already_sent

    async def revert_queue(self, selection_ids: list[uuid.UUID]) -> None:
        """The message broker was unreachable: put these back, so pressing Release again retries them."""
        rows = (await self.db.execute(select(InternshipSelection).where(InternshipSelection.id.in_(selection_ids)))).scalars().all()
        for selection in rows:
            if selection.offer_status == OfferStatus.QUEUED:
                selection.offer_status = OfferStatus.NOT_SENT
        await self.db.flush()
