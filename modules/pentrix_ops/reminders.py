"""
Reminder emails for Pentrix appointments: 30 minutes before, 5 minutes before, and at the start, to the candidate and to the assigned
team member, worded by the Email Studio templates `pentrix_booking_reminder_<30m|5m|now>_<candidate|staff>`.

How it stays correct without anyone keeping a page open: a scheduled task (every minute) looks at the appointments that are about to
start and sends what is due. Every send is recorded under a unique key (appointment, moment, person, appointment *time*), so

* running twice, or two runs overlapping, cannot send the same reminder twice;
* a rescheduled appointment has a new time, so it gets fresh reminders for the new time and none for the old;
* a cancelled, completed, no-show or already-started appointment gets nothing further;
* a reminder is sent only inside a short window after its moment (a worker that was down is not allowed to send "30 minutes to go"
  an hour late), and only if the appointment already existed at that moment (booking ten minutes ahead sends no 30-minute reminder).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from modules.authentication.models import User
from modules.email_templates.render import render_email
from modules.pentrix_ops.models import PentrixBooking, PentrixBookingReminder
from modules.pentrix_ops.service import pentrix_organization_id
from packages.email.service import email_service

logger = get_logger(__name__)

MOMENTS = (("30m", timedelta(minutes=30)), ("5m", timedelta(minutes=5)), ("now", timedelta(0)))
# A reminder is dropped, not sent late, once this much time has passed after its moment.
WINDOW = timedelta(minutes=10)
MAX_ATTEMPTS = 3
_SLACK = timedelta(seconds=90)  # a booking made a moment before a reminder's moment still counts as booked in time
_LISTED = ("requested", "confirmed")


@dataclass
class Summary:
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    details: list[str] = field(default_factory=list)


def _format(booking: PentrixBooking) -> dict[str, str]:
    tz = ZoneInfo(settings.PENTRIX_TIMEZONE)
    local = booking.slot_start.astimezone(tz)
    return {
        "booking_date": f"{local.strftime('%A')}, {local.day} {local.strftime('%B %Y')}",
        "booking_time": local.strftime("%I:%M %p").lstrip("0"),
        "timezone": "IST (India Standard Time)" if settings.PENTRIX_TIMEZONE == "Asia/Kolkata" else settings.PENTRIX_TIMEZONE,
        "duration_minutes": str(int((booking.slot_end - booking.slot_start).total_seconds() // 60)),
        "booking_reference": booking.reference or "",
    }


def _values(booking: PentrixBooking, audience: str, recipient_name: str, representative: str) -> dict[str, str]:
    if booking.meeting_url:
        link, label = booking.meeting_url, "Join the meeting"
    elif audience == "candidate":
        link, label = f"{settings.PENTRIX_PORTAL_URL.rstrip('/')}/portal/bookings", "View your booking"
    else:
        link, label = f"{settings.FRONTEND_URL.rstrip('/')}/pentrix/my-bookings", "View the booking"
    return {
        **_format(booking),
        "full_name": recipient_name or "there",
        "candidate_name": booking.candidate_name,
        "representative": representative or "the Pentrix team",
        "meeting_url": link,
        "meeting_label": label,
    }


def due(booking: PentrixBooking, now: datetime) -> list[str]:
    """Which moments are due for this appointment right now."""
    if booking.status not in _LISTED or now >= booking.slot_end:
        return []
    out = []
    for kind, lead in MOMENTS:
        moment = booking.slot_start - lead
        if moment <= now <= moment + WINDOW and moment + _SLACK >= booking.scheduled_at:
            out.append(kind)
    return out


async def _claim(db: AsyncSession, booking: PentrixBooking, kind: str, audience: str, recipient: str) -> PentrixBookingReminder | None:
    """The reminder row to send for, or None when it has already been sent, has used its attempts, or someone else just took it."""
    existing = (
        await db.execute(
            select(PentrixBookingReminder).where(
                PentrixBookingReminder.booking_id == booking.id, PentrixBookingReminder.kind == kind,
                PentrixBookingReminder.audience == audience, PentrixBookingReminder.slot_start == booking.slot_start,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing if existing.status != "sent" and existing.attempts < MAX_ATTEMPTS else None
    row = PentrixBookingReminder(booking_id=booking.id, kind=kind, audience=audience, slot_start=booking.slot_start, recipient=recipient)
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        return None  # another run created it a moment ago
    return row


async def send_due_reminders(db: AsyncSession, now: datetime | None = None) -> Summary:
    now = now or datetime.now(timezone.utc)
    summary = Summary()
    candidates = (
        await db.execute(
            select(PentrixBooking).where(
                PentrixBooking.status.in_(_LISTED),
                PentrixBooking.slot_start <= now + timedelta(minutes=31),
                PentrixBooking.slot_end > now,
            )
        )
    ).scalars().all()
    for booking in candidates:
        kinds = due(booking, now)
        if not kinds:
            continue
        staff = await db.get(User, booking.assigned_staff_user_id) if booking.assigned_staff_user_id else None
        representative = booking.assigned_staff_name or (staff.full_name if staff else "")
        people = [("candidate", booking.candidate_email, booking.candidate_name)]
        if staff is not None and staff.email:
            people.append(("staff", staff.email, staff.full_name))
        for kind in kinds:
            for audience, email, name in people:
                if not email:
                    summary.skipped += 1
                    continue
                row = await _claim(db, booking, kind, audience, email)
                if row is None:
                    summary.skipped += 1
                    continue
                row.attempts += 1
                try:
                    subject, text, html = await render_email(
                        db, f"pentrix_booking_reminder_{kind}_{audience}", _values(booking, audience, name, representative), organization_id=booking.organization_id
                    )
                    ok = await email_service.send(email, subject, text, html)
                    row.error = None if ok else "The mail server did not accept the message."
                except Exception as exc:  # noqa: BLE001 - one failed email must not stop the others
                    ok, row.error = False, str(exc)[:500]
                    logger.warning("pentrix_reminder_failed", booking=str(booking.id), kind=kind, audience=audience, error=row.error)
                row.status = "sent" if ok else "failed"
                row.sent_at = datetime.now(timezone.utc) if ok else None
                summary.sent += int(ok)
                summary.failed += int(not ok)
                await db.flush()
    return summary


__all__ = ["send_due_reminders", "due", "Summary", "pentrix_organization_id", "MOMENTS", "WINDOW"]
