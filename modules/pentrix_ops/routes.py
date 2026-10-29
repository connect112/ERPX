"""
Pentrix operations API (`/pentrix-ops`).

Viewing every Pentrix appointment needs `pentrix_ops.bookings.view`; assigning, rescheduling, cancelling, changing status or meeting
details and the availability rules need `pentrix_ops.bookings.manage`. A team member the appointments are assigned to has only
`pentrix_ops.bookings.assigned`: they see their own appointments and may mark them in progress, completed or no show and add notes;
they cannot see anyone else's. Every check is made here, on the server.
"""
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.schemas import (
    AssignRequest,
    AvailabilitySettings,
    BlockRequest,
    BookingOut,
    BookingPage,
    MeetingRequest,
    MessageOut,
    NotesRequest,
    RescheduleRequest,
    StaffOut,
    StatusRequest,
    SyncOut,
)
from modules.pentrix_ops.service import PentrixBookingService, pentrix_organization_id
from modules.provisioning.dependencies import verify_internal_signature
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
internal_router = APIRouter()

View = Depends(require_permissions("pentrix_ops.bookings.view"))
Manage = Depends(require_permissions("pentrix_ops.bookings.manage"))
Assigned = Depends(require_permissions("pentrix_ops.bookings.assigned"))
Org = Depends(get_current_user_organization_id)
Db = Depends(get_db)


async def _scope(organization_id: uuid.UUID, db: AsyncSession) -> None:
    """The Pentrix operations belong to one organisation; people in any other get nothing."""
    if organization_id != await pentrix_organization_id(db):
        raise ValidationError("Pentrix operations are not set up for your organization.")


def _out(row) -> BookingOut:
    return BookingOut(**PentrixBookingService.out(row))


# ------------------------------------------------------------------ every appointment


@router.get("/bookings", response_model=BookingPage)
async def list_bookings(
    scope: str = Query(default="upcoming", pattern="^(upcoming|past|all)$"),
    status: list[str] | None = Query(default=None),
    staff: str | None = Query(default=None, description="a team member's id, or 'unassigned'"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    organization_id: uuid.UUID = Org,
    user: User = View,
    db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    try:
        rows, total = await PentrixBookingService(db).search(
            organization_id, scope=scope, statuses=status, staff=staff, date_from=date_from, date_to=date_to, q=q, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise ValidationError("That team member is not valid.") from exc
    return BookingPage(items=[_out(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    await _scope(organization_id, db)
    return _out(await PentrixBookingService(db).get(organization_id, booking_id))


@router.get("/staff", response_model=list[StaffOut])
async def staff(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    """Team members who can be given appointments."""
    await _scope(organization_id, db)
    return [StaffOut(id=u.id, full_name=u.full_name, email=u.email) for u in await PentrixBookingService(db).eligible_staff(organization_id)]


@router.post("/sync", response_model=SyncOut)
async def sync_now(organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    """Pull the latest from Pentrix now (it also happens every minute by itself)."""
    await _scope(organization_id, db)
    return SyncOut(updated=await PentrixBookingService(db).sync())


# ------------------------------------------------------------------ acting on one appointment (carried out in Pentrix)


@router.post("/bookings/{booking_id}/assign", response_model=BookingOut)
async def assign(booking_id: uuid.UUID, payload: AssignRequest, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.assign(organization_id, await service.get(organization_id, booking_id), payload.staff_user_id, user.id))


@router.post("/bookings/{booking_id}/status", response_model=BookingOut)
async def set_status(booking_id: uuid.UUID, payload: StatusRequest, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.set_status(organization_id, await service.get(organization_id, booking_id), payload.status, user.id))


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingOut)
async def reschedule(booking_id: uuid.UUID, payload: RescheduleRequest, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.reschedule(organization_id, await service.get(organization_id, booking_id), payload.slot_start, user.id))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
async def cancel(booking_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.cancel(organization_id, await service.get(organization_id, booking_id), user.id))


@router.put("/bookings/{booking_id}/meeting", response_model=BookingOut)
async def set_meeting(booking_id: uuid.UUID, payload: MeetingRequest, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.set_meeting(organization_id, await service.get(organization_id, booking_id), payload.meeting_url, user.id))


@router.put("/bookings/{booking_id}/notes", response_model=BookingOut)
async def set_notes(booking_id: uuid.UUID, payload: NotesRequest, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.set_notes(organization_id, await service.get(organization_id, booking_id), payload.notes, user.id))


@router.get("/availability")
async def availability(days: int | None = Query(default=None, ge=1, le=60), organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db) -> Any:
    """The slots a candidate could book, for choosing a new time when rescheduling on their behalf."""
    await _scope(organization_id, db)
    return await PentrixClient().availability(days)


# ------------------------------------------------------------------ the rules


@router.get("/availability-settings")
async def get_availability_settings(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db) -> Any:
    await _scope(organization_id, db)
    return await PentrixClient().get_settings()


@router.put("/availability-settings")
async def put_availability_settings(payload: AvailabilitySettings, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db) -> Any:
    await _scope(organization_id, db)
    return await PentrixClient().put_settings(payload.model_dump(exclude_unset=True), str(user.id))


@router.get("/closed-periods")
async def closed_periods(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db) -> Any:
    await _scope(organization_id, db)
    return await PentrixClient().blocks()


@router.post("/closed-periods", status_code=201)
async def add_closed_period(payload: BlockRequest, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db) -> Any:
    await _scope(organization_id, db)
    return await PentrixClient().add_block(payload.start_at.isoformat(), payload.end_at.isoformat(), payload.reason, str(user.id))


@router.delete("/closed-periods/{block_id}", response_model=MessageOut)
async def delete_closed_period(block_id: str, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    await PentrixClient().delete_block(block_id, str(user.id))
    return MessageOut(message="Removed.")


# ------------------------------------------------------------------ the team member's own appointments


@router.get("/my-bookings", response_model=BookingPage)
async def my_bookings(
    scope: str = Query(default="upcoming", pattern="^(upcoming|past|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    organization_id: uuid.UUID = Org,
    user: User = Assigned,
    db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    rows, total = await PentrixBookingService(db).search(organization_id, scope=scope, assigned_to=user.id, page=page, page_size=page_size)
    return BookingPage(items=[_out(r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/my-bookings/{booking_id}/status", response_model=BookingOut)
async def my_booking_status(booking_id: uuid.UUID, payload: StatusRequest, organization_id: uuid.UUID = Org, user: User = Assigned, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.staff_status(organization_id, await service.my_booking(organization_id, booking_id, user.id), payload.status, user.id))


@router.put("/my-bookings/{booking_id}/notes", response_model=BookingOut)
async def my_booking_notes(booking_id: uuid.UUID, payload: NotesRequest, organization_id: uuid.UUID = Org, user: User = Assigned, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixBookingService(db)
    return _out(await service.set_notes(organization_id, await service.my_booking(organization_id, booking_id, user.id), payload.notes, user.id))


# ------------------------------------------------------------------ from Pentrix (signed, no user)


@internal_router.post("/bookings", response_model=MessageOut, dependencies=[Depends(verify_internal_signature)])
async def receive_booking(request: Request, db: AsyncSession = Db):
    """Pentrix tells ERPX a booking changed. Signed with the shared secret; an older message never overwrites a newer state."""
    data = await request.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise ValidationError("A booking is required.")
    await PentrixBookingService(db).upsert(await pentrix_organization_id(db), data)
    return MessageOut(message="Stored.")
