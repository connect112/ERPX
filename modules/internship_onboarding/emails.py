"""
Placeholder values for the offer letter email and the onboarding invitation, and sending the invitation.

A new link is issued at the moment an email is built, inside the worker; the raw token goes straight into that email
and is never stored, logged or put on the message queue.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.internship_onboarding import fees as fee_maths
from modules.internship_onboarding import ledger
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.models import OnboardingApplication
from modules.internship_onboarding.service import ApplicationService, config_of, effective_deadline, event
from modules.our_internships.models import InternshipSelection, OurInternship

logger = get_logger(__name__)
_STAGGER_SECONDS = 2
EMPTY = {k: "" for k in (
    "onboarding_link", "onboarding_deadline", "onboarding_start_date", "internship_fee", "late_fee", "total_payable",
    "application_reference",
)}  # fmt: skip


def money(amount: Decimal, currency: str) -> str:
    return f"{currency} {fee_maths.q(amount):,.2f}"


def when(value: datetime | None, tz: str, with_time: bool = True) -> str:
    if value is None:
        return ""
    local = value.astimezone(ZoneInfo(tz))
    return local.strftime("%d %b %Y, %I:%M %p %Z") if with_time else local.strftime("%d %b %Y")


async def onboarding_values(
    db: AsyncSession, internship: OurInternship, selection: InternshipSelection, config: OnboardingConfig | None = None,
) -> dict[str, str]:  # fmt: skip
    """The onboarding placeholders for one student, issuing them a fresh link. Empty values when onboarding is manual."""
    if config is None:
        _, config = await config_of(db, internship)
    if not config.modes.self_service:
        return dict(EMPTY)
    issued = await ApplicationService(db).issue_link(internship, selection, None, "email")
    app = issued.application
    snapshot = app.fee_snapshot or fee_maths.snapshot(config.fees)
    totals = await ledger.totals(db, app, fee_maths.total_of(snapshot))
    currency = config.fees.currency
    tz = config.deadlines.timezone
    payment = config.modes.require_payment
    return {
        "onboarding_link": issued.link,
        "onboarding_deadline": when(effective_deadline(app, config), tz),
        "onboarding_start_date": when(config.deadlines.opens_at, tz, with_time=False),
        "internship_fee": money(Decimal(snapshot["total"]), currency) if payment else "",
        "late_fee": money(totals.charges - totals.waivers, currency) if payment and totals.charges > totals.waivers else "",
        "total_payable": money(totals.payable, currency) if payment else "",
        "application_reference": app.reference,
    }


async def _send_invitation(application_id: uuid.UUID) -> None:
    from modules.email_templates.render import render_email_full
    from modules.institutions.models import InstitutionStudent
    from packages.email.history import set_send_meta
    from packages.email.service import email_service

    async with get_db_context() as db:
        app = (
            await db.execute(select(OnboardingApplication).where(OnboardingApplication.id == application_id).with_for_update())
        ).scalar_one_or_none()
        if app is None or app.cancelled_at is not None:
            return
        selection = await db.get(InternshipSelection, app.selection_id)
        internship = await db.get(OurInternship, app.internship_id)
        student = await db.get(InstitutionStudent, selection.student_id) if selection else None
        if selection is None or internship is None or student is None or not student.email:
            return
        values = await onboarding_values(db, internship, selection)
        if not values["onboarding_link"]:
            return
        subject, text, html, meta = await render_email_full(
            db, "internship_onboarding_invitation",
            {**values, "full_name": student.name, "student_name": student.name, "internship_name": internship.title},
            organization_id=internship.organization_id, recipient_email=student.email,
        )  # fmt: skip
        set_send_meta(meta)
        sent = await email_service.send(student.email, subject, text, html)
        await event(db, app, "invitation_sent" if sent else "invitation_failed", actor="system")
        if not sent:
            logger.warning("onboarding_invitation_not_sent", application_id=str(application_id))


@celery_app.task(name="internship_onboarding.send_invitation", bind=True, max_retries=3, default_retry_delay=120)
def send_invitation_task(self, application_id: str) -> None:
    try:
        run_async(_send_invitation(uuid.UUID(application_id)))
    except Exception as exc:  # noqa: BLE001 - retried; each retry issues a new link and the newest email wins
        logger.warning("onboarding_invitation_failed", application_id=application_id, exc_info=True)
        raise self.retry(exc=exc) from exc


def enqueue_invitations(application_ids: list[uuid.UUID]) -> None:
    for position, application_id in enumerate(application_ids):
        send_invitation_task.apply_async(args=[str(application_id)], countdown=position * _STAGGER_SECONDS)
