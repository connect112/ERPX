"""
The certificate PDF of one attendee, built exactly the same way for the review preview and for the email.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from modules.organizations.models import Organization
from modules.workshop_exams.certificate_pdf import build_certificate_pdf
from modules.workshop_exams.certificate_template import NameAdjust, build_templated_certificate_pdf
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from modules.workshop_exams.service import WorkshopExamService


def verify_url(certificate_number: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/verify-workshop-certificate/{certificate_number}"


PLACE_LABELS = {"first": "1st place", "second": "2nd place", "third": "3rd place"}


async def certificate_email(
    db: AsyncSession, exam: WorkshopExam, full_name: str, team_name: str | None = None
) -> tuple[str, str, str]:
    """(subject, text, html) of the email that carries a certificate of this exam: the exam certificate email, or for a
    hackathon award its winner / participation email (with that hackathon's own wording when it has written one)."""
    from modules.email_templates.render import render_email

    if exam.hackathon_id is None:
        return await render_email(
            db, "workshop_certificate", {"full_name": full_name, "exam_title": exam.title}, organization_id=exam.organization_id
        )
    from modules.hackathons.models import Hackathon

    hackathon = (await db.execute(select(Hackathon).where(Hackathon.id == exam.hackathon_id))).scalar_one()
    key = "hackathon_winner_certificate" if exam.award in PLACE_LABELS else "hackathon_participation_certificate"
    return await render_email(
        db,
        key,
        {
            "full_name": full_name,
            "hackathon_title": hackathon.title,
            "place": PLACE_LABELS.get(exam.award or "", ""),
            "team_name": team_name or "",
        },
        organization_id=exam.organization_id,
        hackathon_id=exam.hackathon_id,
    )


def adjust_of(attendee: WorkshopExamAttendee) -> NameAdjust | None:
    return NameAdjust.model_validate(attendee.certificate_adjust) if attendee.certificate_adjust else None


async def render_certificate(
    db: AsyncSession, exam: WorkshopExam, attendee: WorkshopExamAttendee, certificate_number: str | None = None
) -> bytes:
    number = certificate_number or attendee.certificate_number
    assert number is not None
    template = await WorkshopExamService(db).get_template(exam.id) if exam.has_certificate_template else None
    if template is not None:
        # The admin's own artwork with this attendee's name printed on it.
        return build_templated_certificate_pdf(
            template_jpeg=template.data,
            width_px=template.width_px,
            height_px=template.height_px,
            layout=WorkshopExamService.layout_of(exam),
            attendee_name=attendee.name,
            certificate_number=number,
            verify_url=verify_url(number),
            adjust=adjust_of(attendee),
        )
    org = (await db.execute(select(Organization).where(Organization.id == exam.organization_id))).scalar_one_or_none()
    issuer = org.name if org else "GIR Technologies"
    body = exam.certificate_text or f'has participated in the workshop "{exam.title}".'
    return build_certificate_pdf(
        attendee_name=attendee.name,
        heading=exam.certificate_heading,
        body_text=body,
        issuer_name=issuer,
        issued_on=attendee.submitted_at
        or (attendee.created_at if attendee.certificate_only else datetime.now(timezone.utc)),
        certificate_number=number,
        verify_url=verify_url(number),
    )
