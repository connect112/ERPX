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
