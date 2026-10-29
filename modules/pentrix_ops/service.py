"""
Pentrix bookings in ERPX: the synchronised copy, assigning team members, the screens' actions (each one carried out in Pentrix, which
owns the booking, and the answer written back to the copy), and the regular pull of what changed.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import User, UserStatus
from modules.authorization.models import Permission, RolePermission, UserRole
from modules.organizations.models import Organization
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.models import ACTIVE_STATUSES, PentrixBooking, PentrixSyncState
from modules.users.models import UserProfile

logger = get_logger(__name__)

ASSIGNED_PERMISSION = "pentrix_ops.bookings.assigned"
BOOKINGS_CURSOR = "bookings_cursor"
STATUS_LABEL = {
    "requested": "Scheduled", "confirmed": "Confirmed", "in_progress": "In progress", "completed": "Completed", "cancelled": "Cancelled", "no_show": "No show",
}
# What the person a booking is assigned to may do to it; the rest is for administrators.
STAFF_STATUSES = {"in_progress", "completed", "no_show"}


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def pentrix_organization_id(db: AsyncSession) -> uuid.UUID:
    """The organisation the Pentrix operations belong to: PENTRIX_ORGANIZATION_SLUG when set, otherwise the oldest organisation that is
    not the Pentrix student programme's own."""
    if settings.PENTRIX_ORGANIZATION_SLUG:
        found = (await db.execute(select(Organization.id).where(Organization.slug == settings.PENTRIX_ORGANIZATION_SLUG))).scalar_one_or_none()
        if found:
            return found
    found = (
        await db.execute(select(Organization.id).where(Organization.slug != "gir-pentrix-program").order_by(Organization.created_at).limit(1))
    ).scalar_one_or_none()
    if found is None:
        raise NotFoundError("Organization", "pentrix")
    return found


class PentrixBookingService:
    def __init__(self, db: AsyncSession, client: PentrixClient | None = None):
        self.db = db
        self.client = client or PentrixClient()

    # ------------------------------------------------------------------ the copy

    async def upsert(self, organization_id: uuid.UUID, data: dict) -> PentrixBooking:
        """Write one Pentrix booking into the copy. An older message never overwrites a newer state, and the same one twice changes
        nothing."""
        now = datetime.now(timezone.utc)
        row = (await self.db.execute(select(PentrixBooking).where(PentrixBooking.pentrix_booking_id == data["id"]))).scalar_one_or_none()
        updated = parse_time(data.get("updated_at"))
        if row is not None and row.source_updated_at and updated and updated < row.source_updated_at:
            return row
        start, end = parse_time(data["slot_start"]), parse_time(data["slot_end"])
        if start is None or end is None:
            raise ValidationError("The booking has no time.")
        staff_id = await self._known_user(data.get("assigned_staff_ref"))
        if row is None:
            row = PentrixBooking(
                organization_id=organization_id, pentrix_booking_id=data["id"], slot_start=start, slot_end=end,
                scheduled_at=parse_time(data.get("created_at")) or now, status=data.get("status", "confirmed"), pentrix_user_id=data.get("user_id", ""),
            )
            self.db.add(row)
        elif row.slot_start != start:
            row.scheduled_at = updated or now  # a new time: its reminders start from now
        row.reference = data.get("reference")
        row.pentrix_user_id = data.get("user_id") or row.pentrix_user_id
        row.candidate_name = data.get("candidate_name") or ""
        row.candidate_email = data.get("candidate_email") or ""
        row.slot_start, row.slot_end = start, end
        row.status = data.get("status") or row.status
        row.assigned_staff_user_id = staff_id
        row.assigned_staff_name = data.get("assigned_staff_name")
        row.meeting_url = data.get("meeting_url")
        row.notes = data.get("notes")
        row.reschedule_count = int(data.get("reschedule_count") or 0)
        row.cancelled_by = data.get("cancelled_by")
        row.source_created_at = parse_time(data.get("created_at"))
        row.source_updated_at = updated
        await self.db.flush()
        await self.db.refresh(row)  # the database sets updated_at itself; read it back
        return row

    async def _known_user(self, ref: Any) -> uuid.UUID | None:
        if not ref:
            return None
        try:
            user_id = uuid.UUID(str(ref))
        except ValueError:
            return None
        return (await self.db.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none()

    async def sync(self, max_pages: int = 20) -> int:
        """Pull everything Pentrix changed since the saved cursor. Safe to run any time and as often as wanted."""
        org = await pentrix_organization_id(self.db)
        state = (await self.db.execute(select(PentrixSyncState).where(PentrixSyncState.key == BOOKINGS_CURSOR))).scalar_one_or_none()
        if state is None:
            state = PentrixSyncState(key=BOOKINGS_CURSOR, value="")
            self.db.add(state)
            await self.db.flush()
        cursor, count = state.value or None, 0
        try:
            for _ in range(max_pages):
                page = await self.client.changes(cursor)
                for item in page["items"]:
                    await self.upsert(org, item)
                    count += 1
                cursor = page.get("next_cursor") or cursor
                state.value = cursor or ""
                if not page.get("has_more"):
                    break
            state.last_error = None
        except Exception as exc:  # noqa: BLE001 - recorded, and the next run starts from the saved cursor
            state.last_error = str(exc)[:500]
            logger.warning("pentrix_sync_failed", error=str(exc)[:200])
            state.last_run_at = datetime.now(timezone.utc)
            await self.db.flush()
            raise
        state.last_run_at = datetime.now(timezone.utc)
        await self.db.flush()
        return count

    # ------------------------------------------------------------------ reading

    async def get(self, organization_id: uuid.UUID, booking_id: uuid.UUID) -> PentrixBooking:
        row = await self.db.get(PentrixBooking, booking_id)
        if row is None or row.organization_id != organization_id:
            raise NotFoundError("Pentrix booking", booking_id)
        return row

    async def search(
        self, organization_id: uuid.UUID, *, scope: str = "upcoming", statuses: list[str] | None = None, staff: str | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None, q: str | None = None, assigned_to: uuid.UUID | None = None,
        page: int = 1, page_size: int = 25,
    ) -> tuple[list[PentrixBooking], int]:
        now = datetime.now(timezone.utc)
        conditions = [PentrixBooking.organization_id == organization_id]
        if assigned_to is not None:
            conditions.append(PentrixBooking.assigned_staff_user_id == assigned_to)
        if scope == "upcoming":
            conditions += [PentrixBooking.slot_end >= now, PentrixBooking.status.in_(ACTIVE_STATUSES)]
        elif scope == "past":
            conditions.append(or_(PentrixBooking.slot_end < now, PentrixBooking.status.notin_(ACTIVE_STATUSES)))
        if statuses:
            conditions.append(PentrixBooking.status.in_(statuses))
        if staff == "unassigned":
            conditions.append(PentrixBooking.assigned_staff_user_id.is_(None))
        elif staff:
            conditions.append(PentrixBooking.assigned_staff_user_id == uuid.UUID(staff))
        if date_from:
            conditions.append(PentrixBooking.slot_start >= date_from)
        if date_to:
            conditions.append(PentrixBooking.slot_start < date_to)
        if q:
            like = f"%{q.strip()}%"
            conditions.append(or_(PentrixBooking.candidate_name.ilike(like), PentrixBooking.candidate_email.ilike(like), PentrixBooking.reference.ilike(like)))
        total = (await self.db.execute(select(func.count()).select_from(PentrixBooking).where(and_(*conditions)))).scalar_one()
        order = PentrixBooking.slot_start.asc() if scope == "upcoming" else PentrixBooking.slot_start.desc()
        rows = (
            await self.db.execute(select(PentrixBooking).where(and_(*conditions)).order_by(order).offset((max(page, 1) - 1) * page_size).limit(page_size))
        ).scalars().all()
        return list(rows), total

    # ------------------------------------------------------------------ team

    async def eligible_staff(self, organization_id: uuid.UUID) -> list[User]:
        """Active members of this organisation who may be given appointments (they hold the "assigned bookings" permission, directly
        through a role)."""
        query = (
            select(User)
            .join(UserProfile, UserProfile.user_id == User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(RolePermission, RolePermission.role_id == UserRole.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(UserProfile.organization_id == organization_id, User.status == UserStatus.ACTIVE, Permission.code == ASSIGNED_PERMISSION)
            .distinct()
            .order_by(User.full_name)
        )
        return list((await self.db.execute(query)).scalars().all())

    async def _overlapping(self, booking: PentrixBooking, staff_id: uuid.UUID) -> PentrixBooking | None:
        return (
            await self.db.execute(
                select(PentrixBooking).where(
                    PentrixBooking.assigned_staff_user_id == staff_id, PentrixBooking.id != booking.id, PentrixBooking.status.in_(ACTIVE_STATUSES),
                    PentrixBooking.slot_start < booking.slot_end, PentrixBooking.slot_end > booking.slot_start,
                ).limit(1)
            )
        ).scalar_one_or_none()

    # ------------------------------------------------------------------ actions (done in Pentrix, answer written back)

    async def _apply(self, organization_id: uuid.UUID, data: dict) -> PentrixBooking:
        return await self.upsert(organization_id, data)

    async def assign(self, organization_id: uuid.UUID, booking: PentrixBooking, staff_user_id: uuid.UUID | None, actor: uuid.UUID) -> PentrixBooking:
        if staff_user_id is None:
            return await self._apply(organization_id, await self.client.assign(booking.pentrix_booking_id, None, None, str(actor)))
        staff = next((u for u in await self.eligible_staff(organization_id) if u.id == staff_user_id), None)
        if staff is None:
            raise ValidationError("That person cannot be given appointments. Choose someone from the list of team members.")
        clash = await self._overlapping(booking, staff_user_id)
        if clash is not None:
            raise ConflictError(f"{staff.full_name} already has an appointment at that time ({clash.candidate_name or clash.reference}).")
        return await self._apply(organization_id, await self.client.assign(booking.pentrix_booking_id, str(staff.id), staff.full_name, str(actor)))

    async def set_status(self, organization_id: uuid.UUID, booking: PentrixBooking, status: str, actor: uuid.UUID) -> PentrixBooking:
        if status not in STATUS_LABEL:
            raise ValidationError("That is not a booking status.")
        return await self._apply(organization_id, await self.client.set_status(booking.pentrix_booking_id, status, str(actor)))

    async def reschedule(self, organization_id: uuid.UUID, booking: PentrixBooking, slot_start: datetime, actor: uuid.UUID) -> PentrixBooking:
        if booking.assigned_staff_user_id:  # the person it is assigned to must be free at the new time
            moved = PentrixBooking(id=booking.id, slot_start=slot_start, slot_end=slot_start + (booking.slot_end - booking.slot_start))
            clash = await self._overlapping(moved, booking.assigned_staff_user_id)
            if clash is not None:
                raise ConflictError(f"{booking.assigned_staff_name or 'The assigned team member'} already has an appointment at that time. Reassign it first.")
        return await self._apply(organization_id, await self.client.reschedule(booking.pentrix_booking_id, slot_start.isoformat(), str(actor)))

    async def cancel(self, organization_id: uuid.UUID, booking: PentrixBooking, actor: uuid.UUID) -> PentrixBooking:
        return await self._apply(organization_id, await self.client.cancel(booking.pentrix_booking_id, str(actor)))

    async def set_meeting(self, organization_id: uuid.UUID, booking: PentrixBooking, url: str | None, actor: uuid.UUID) -> PentrixBooking:
        return await self._apply(organization_id, await self.client.meeting(booking.pentrix_booking_id, url, str(actor)))

    async def set_notes(self, organization_id: uuid.UUID, booking: PentrixBooking, notes: str | None, actor: uuid.UUID) -> PentrixBooking:
        return await self._apply(organization_id, await self.client.notes(booking.pentrix_booking_id, notes, str(actor)))

    # ------------------------------------------------------------------ the person a booking is assigned to

    async def my_booking(self, organization_id: uuid.UUID, booking_id: uuid.UUID, user_id: uuid.UUID) -> PentrixBooking:
        row = await self.get(organization_id, booking_id)
        if row.assigned_staff_user_id != user_id:
            raise NotFoundError("Pentrix booking", booking_id)  # not theirs: it does not exist as far as they can tell
        return row

    async def staff_status(self, organization_id: uuid.UUID, booking: PentrixBooking, status: str, user_id: uuid.UUID) -> PentrixBooking:
        if status not in STAFF_STATUSES:
            raise ValidationError("You can mark an appointment in progress, completed or no show.")
        return await self.set_status(organization_id, booking, status, user_id)

    # ------------------------------------------------------------------ for the dashboards

    async def upcoming(self, organization_id: uuid.UUID, limit: int = 5) -> list[PentrixBooking]:
        rows, _ = await self.search(organization_id, scope="upcoming", page_size=limit)
        return rows

    @staticmethod
    def out(row: PentrixBooking) -> dict:
        return {
            "id": row.id, "pentrix_booking_id": row.pentrix_booking_id, "reference": row.reference,
            "candidate_name": row.candidate_name, "candidate_email": row.candidate_email,
            "slot_start": row.slot_start, "slot_end": row.slot_end,
            "duration_minutes": int((row.slot_end - row.slot_start).total_seconds() // 60),
            "status": row.status, "status_label": STATUS_LABEL.get(row.status, row.status),
            "assigned_staff_user_id": row.assigned_staff_user_id, "assigned_staff_name": row.assigned_staff_name,
            "meeting_url": row.meeting_url, "notes": row.notes, "reschedule_count": row.reschedule_count, "cancelled_by": row.cancelled_by,
            "updated_at": row.updated_at,
        }


__all__ = ["PentrixBookingService", "pentrix_organization_id", "ASSIGNED_PERMISSION", "STATUS_LABEL", "STAFF_STATUSES"]
