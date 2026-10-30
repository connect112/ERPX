"""
When a student's onboarding becomes complete: record it once, and, when the internship grants LMS access automatically,
grant it through the existing ``OnboardingService.grant`` (idempotent: never a second account or enrolment).

Also the periodic sweep: catch up completions that were missed, retry automatic LMS grants that failed, and send the
deadline reminders (each reminder once per student and per configured day).
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from modules.internship_onboarding import state
from modules.internship_onboarding.models import OnboardingApplication, OnboardingEvent
from modules.internship_onboarding.service import ApplicationService, config_of, event, now
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship, PaymentStatus

logger = get_logger(__name__)


async def check(db: AsyncSession, application: OnboardingApplication) -> bool:
    """Record completion if every requirement is met. True when this call recorded it (the caller may enqueue follow-ups)."""
    if application.completed_at is not None or application.cancelled_at is not None:
        return False
    internship = await db.get(OurInternship, application.internship_id)
    selection = await db.get(InternshipSelection, application.selection_id)
    if internship is None or selection is None:
        return False
    _, config = await config_of(db, internship)
    facts = await ApplicationService(db).facts(config, selection, application)
    if state.overall_status(facts) != "completed":
        return False
    application.completed_at = now()
    await db.flush()
    await event(db, application, "onboarding_completed", actor="system")
    return True


async def check_and_queue(db: AsyncSession, application: OnboardingApplication) -> None:
    if await check(db, application):
        from modules.internship_onboarding.tasks import enqueue_follow_up

        enqueue_follow_up(application.id)


async def follow_up(db: AsyncSession, application_id: uuid.UUID) -> str:
    """After completion: grant LMS access when the internship does that automatically. Safe to run again."""
    from modules.institutions.models import InstitutionStudent
    from modules.our_internships.onboarding import OnboardingService, grant_blockers, notify_access

    application = await db.get(OnboardingApplication, application_id)
    if application is None or application.completed_at is None:
        return "not complete"
    internship = await db.get(OurInternship, application.internship_id)
    selection = await db.get(InternshipSelection, application.selection_id, with_for_update=True)
    if internship is None or selection is None:
        return "missing"
    _, config = await config_of(db, internship)
    if config.modes.lms_access != "automatic":
        return "manual LMS"
    if selection.lms_status == LmsStatus.GRANTED:
        return "already granted"
    if not config.modes.require_payment and selection.payment_status != PaymentStatus.PAID:
        # the LMS gate asks for a settled payment; for an internship without a fee there is nothing to pay
        selection.payment_status = PaymentStatus.PAID
        selection.payment_amount = Decimal("0.00")
        selection.payment_reference = "No fee"
        selection.payment_confirmed_at = now()
        await event(db, application, "payment_not_required", actor="system")
    blockers = grant_blockers(internship, selection)
    if blockers:
        reason = " ".join(blockers)[:300]
        last = (
            await db.execute(
                select(OnboardingEvent.detail).where(OnboardingEvent.application_id == application.id, OnboardingEvent.event == "lms_waiting")
                .order_by(OnboardingEvent.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()  # fmt: skip
        if (last or {}).get("reason") != reason:
            await event(db, application, "lms_waiting", actor="system", reason=reason)
        await db.flush()
        return "blocked"
    student = await db.get(InstitutionStudent, selection.student_id)
    outcome = await OnboardingService(db).grant(internship, selection, student, None)
    await event(db, application, "lms_granted", actor="system", course=outcome.course_title)
    await db.flush()
    await notify_access(outcome)
    return "granted"


async def _already(db: AsyncSession, application_id: uuid.UUID, name: str, days: int) -> bool:
    rows = await db.execute(
        select(OnboardingEvent.detail).where(OnboardingEvent.application_id == application_id, OnboardingEvent.event == name)
    )
    return any((d or {}).get("days") == days for d in rows.scalars())


async def sweep(db: AsyncSession) -> dict[str, int]:
    """Completions missed, automatic LMS grants to retry, and reminders that are due. Returns what it queued."""
    from modules.internship_onboarding.emails import enqueue_invitations

    completed = reminders = 0
    to_follow: list[uuid.UUID] = []
    to_remind: list[uuid.UUID] = []
    t = now()
    rows = (
        await db.execute(
            select(OnboardingApplication).where(OnboardingApplication.cancelled_at.is_(None)).order_by(OnboardingApplication.created_at)
        )
    ).scalars().all()
    configs: dict = {}
    for application in rows:
        if application.completed_at is None and await check(db, application):
            completed += 1
        if application.completed_at is not None:
            to_follow.append(application.id)
            continue
        if application.internship_id not in configs:
            internship = await db.get(OurInternship, application.internship_id)
            configs[application.internship_id] = (await config_of(db, internship))[1] if internship else None
        config = configs[application.internship_id]
        if config is None or not config.modes.self_service or not config.modes.reminders:
            continue
        selection = await db.get(InternshipSelection, application.selection_id)
        if selection is None or selection.offer_response.value == "declined" or application.token_hash is None:
            continue
        closes = application.deadline_override_at or config.deadlines.closes_at
        if closes is None or closes <= t:
            continue
        for days in config.communication.reminder_days:
            window_start = closes - timedelta(days=days)
            if window_start <= t < window_start + timedelta(hours=24) and not await _already(db, application.id, "reminder_sent", days):
                await event(db, application, "reminder_sent", actor="system", days=days)
                to_remind.append(application.id)
                reminders += 1
                break
    await db.commit()
    for application_id in to_follow:
        try:
            await follow_up(db, application_id)
            await db.commit()
        except Exception:  # noqa: BLE001 - recorded and retried on the next sweep
            await db.rollback()
            logger.warning("onboarding_follow_up_failed", application_id=str(application_id), exc_info=True)
    if to_remind:
        enqueue_invitations(to_remind)
    return {"completed": completed, "reminders": reminders, "followed_up": len(to_follow)}
