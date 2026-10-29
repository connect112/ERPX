"""
Pentrix operations API (`/pentrix-ops`).

Viewing every Pentrix appointment needs `pentrix_ops.bookings.view`; assigning, rescheduling, cancelling, changing status or meeting
details and the availability rules need `pentrix_ops.bookings.manage`. A team member the appointments are assigned to has only
`pentrix_ops.bookings.assigned`: they see their own appointments and may mark them in progress, completed or no show and add notes;
they cannot see anyone else's. Every check is made here, on the server.
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix_ops.candidates import CandidateFilters, PentrixCandidateService
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.payments import PaymentFilters, PentrixPaymentService, today_ist
from modules.pentrix_ops.schemas import (
    AssessmentDetail,
    AssignRequest,
    AvailabilitySettings,
    BlockRequest,
    BookingOut,
    BookingPage,
    CandidateDetail,
    CandidateEdit,
    CandidateOut,
    CandidatePage,
    DailyDetail,
    DailyOut,
    MeetingRequest,
    MessageOut,
    NotesRequest,
    OverviewOut,
    PaymentOut,
    PaymentPage,
    PaymentsSummaryOut,
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
OverviewView = Depends(require_permissions("pentrix_ops.overview.view"))
RegistrationsView = Depends(require_permissions("pentrix_ops.registrations.view"))
RegistrationsManage = Depends(require_permissions("pentrix_ops.registrations.manage"))
AssessmentsView = Depends(require_permissions("pentrix_ops.assessments.view"))
PaymentsView = Depends(require_permissions("pentrix_ops.payments.view"))
PaymentsManage = Depends(require_permissions("pentrix_ops.payments.manage"))
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


# ------------------------------------------------------------------ overview, registrations and assessments (Pentrix candidates)


@router.get("/overview", response_model=OverviewOut)
async def overview(organization_id: uuid.UUID = Org, user: User = OverviewView, db: AsyncSession = Db):
    await _scope(organization_id, db)
    return await PentrixCandidateService(db).overview(organization_id)


def _filters(
    q: str | None, assessment: list[str] | None, qualification: list[str] | None, booking: list[str] | None, payment: list[str] | None,
    registered_from: datetime | None, registered_to: datetime | None,
) -> CandidateFilters:
    return CandidateFilters(
        q=q, assessment=assessment or [], qualification=qualification or [], booking=booking or [], payment=payment or [],
        registered_from=registered_from, registered_to=registered_to,
    )


async def _candidate_page(
    db: AsyncSession, organization_id: uuid.UUID, filters: CandidateFilters, sort: str, order: str, page: int, page_size: int
) -> CandidatePage:
    rows, total = await PentrixCandidateService(db).search(organization_id, filters, sort=sort, descending=order == "desc", page=page, page_size=page_size)
    return CandidatePage(items=[CandidateOut(**PentrixCandidateService.out(r)) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/candidates", response_model=CandidatePage)
async def list_candidates(
    q: str | None = Query(default=None, max_length=100),
    assessment: list[str] | None = Query(default=None, description="not_started | in_progress | completed | pending"),
    qualification: list[str] | None = Query(default=None, description="qualified | not_qualified | pending"),
    booking: list[str] | None = Query(default=None, description="scheduled | not_scheduled | completed | cancelled | no_show"),
    payment: list[str] | None = Query(default=None, description="paid | pending | failed | refunded | none | not_paid"),
    registered_from: datetime | None = None,
    registered_to: datetime | None = None,
    sort: str = Query(default="registered"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    organization_id: uuid.UUID = Org,
    user: User = RegistrationsView,
    db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    filters = _filters(q, assessment, qualification, booking, payment, registered_from, registered_to)
    return await _candidate_page(db, organization_id, filters, sort, order, page, page_size)


@router.post("/candidates/sync", response_model=SyncOut)
async def sync_candidates_now(organization_id: uuid.UUID = Org, user: User = RegistrationsView, db: AsyncSession = Db):
    """Pull the latest candidates from Pentrix now (it also happens every minute by itself)."""
    await _scope(organization_id, db)
    return SyncOut(updated=await PentrixCandidateService(db).sync())


@router.get("/candidates/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(candidate_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = RegistrationsView, db: AsyncSession = Db):
    await _scope(organization_id, db)
    return await PentrixCandidateService(db).detail(organization_id, candidate_id)


@router.patch("/candidates/{candidate_id}", response_model=CandidateOut)
async def edit_candidate(candidate_id: uuid.UUID, payload: CandidateEdit, organization_id: uuid.UUID = Org, user: User = RegistrationsManage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("Nothing to change.")
    service = PentrixCandidateService(db)
    return CandidateOut(**service.out(await service.update(organization_id, candidate_id, changes, user.id)))


@router.get("/assessments", response_model=CandidatePage)
async def list_assessments(
    q: str | None = Query(default=None, max_length=100),
    assessment: list[str] | None = Query(default=None),
    qualification: list[str] | None = Query(default=None),
    booking: list[str] | None = Query(default=None),
    payment: list[str] | None = Query(default=None),
    registered_from: datetime | None = None,
    registered_to: datetime | None = None,
    sort: str = Query(default="assessed"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    organization_id: uuid.UUID = Org,
    user: User = AssessmentsView,
    db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    filters = _filters(q, assessment, qualification, booking, payment, registered_from, registered_to)
    return await _candidate_page(db, organization_id, filters, sort, order, page, page_size)


@router.get("/assessments/{candidate_id}", response_model=AssessmentDetail)
async def get_assessment(candidate_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = AssessmentsView, db: AsyncSession = Db):
    """Attempts, scores and the criteria for one candidate: no contact, booking or payment history."""
    await _scope(organization_id, db)
    return await PentrixCandidateService(db).assessment_detail(organization_id, candidate_id)


# ------------------------------------------------------------------ payments (Pentrix payments, invoices and the daily summary)


def _payment_filters(
    q: str | None, status: list[str] | None, purpose: str | None, date_from: datetime | None, date_to: datetime | None, candidate: str | None
) -> PaymentFilters:
    return PaymentFilters(q=q, status=status or [], purpose=purpose, date_from=date_from, date_to=date_to, candidate_pentrix_id=candidate)


def _payment_out(pair) -> PaymentOut:
    return PaymentOut(**PentrixPaymentService.out(*pair))


@router.get("/payments", response_model=PaymentPage)
async def list_payments(
    q: str | None = Query(default=None, max_length=100),
    status: list[str] | None = Query(default=None, description="pending | paid | failed | refunded | partially_refunded"),
    purpose: str | None = Query(default=None, max_length=40),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    candidate: str | None = Query(default=None, description="a Pentrix candidate id"),
    sort: str = Query(default="date"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    organization_id: uuid.UUID = Org,
    user: User = PaymentsView,
    db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    filters = _payment_filters(q, status, purpose, date_from, date_to, candidate)
    rows, total = await PentrixPaymentService(db).search(organization_id, filters, sort=sort, descending=order == "desc", page=page, page_size=page_size)
    return PaymentPage(items=[_payment_out(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/payments/summary", response_model=PaymentsSummaryOut)
async def payments_summary(organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    """Today's collections, pending payments and the latest transactions (the Overview and the main dashboard)."""
    await _scope(organization_id, db)
    data = await PentrixPaymentService(db).summary(organization_id)
    data["latest_payment"] = PaymentOut(**data["latest_payment"]) if data["latest_payment"] else None
    data["recent"] = [PaymentOut(**r) for r in data["recent"]]
    return data


@router.post("/payments/sync", response_model=SyncOut)
async def sync_payments_now(organization_id: uuid.UUID = Org, user: User = PaymentsManage, db: AsyncSession = Db):
    """Pull the latest payments from Pentrix now. This is also the retry after a failed synchronisation (it happens every minute by itself)."""
    await _scope(organization_id, db)
    return SyncOut(updated=await PentrixPaymentService(db).sync())


def _range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    last = date_to or today_ist()
    return (date_from or last - timedelta(days=13)), last


@router.get("/payments/daily", response_model=list[DailyOut])
async def daily_summaries(date_from: date | None = None, date_to: date | None = None, organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    """One entry per calendar day in India (newest first), 14 days by default."""
    await _scope(organization_id, db)
    first, last = _range(date_from, date_to)
    return [DailyOut(**d) for d in await PentrixPaymentService(db).days(organization_id, first, last)]


@router.get("/payments/daily/export")
async def export_daily_summaries(date_from: date | None = None, date_to: date | None = None, organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    await _scope(organization_id, db)
    first, last = _range(date_from, date_to)
    service = PentrixPaymentService(db)
    content = service.days_csv(await service.days(organization_id, first, last))
    return Response(content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="pentrix-daily-summary-{first}-to-{last}.csv"'})


@router.get("/payments/daily/{day}", response_model=DailyDetail)
async def daily_detail(day: date, organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixPaymentService(db)
    summary = (await service.days(organization_id, day, day))[0]
    return DailyDetail(summary=DailyOut(**summary), transactions=[_payment_out(r) for r in await service.day_transactions(organization_id, day)])


@router.get("/payments/daily/{day}/export")
async def export_daily_transactions(day: date, organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixPaymentService(db)
    content = service.transactions_csv(await service.day_transactions(organization_id, day))
    return Response(content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="pentrix-payments-{day}.csv"'})


@router.post("/payments/daily/{day}/reconcile", response_model=DailyOut)
async def reconcile_day(day: date, organization_id: uuid.UUID = Org, user: User = PaymentsManage, db: AsyncSession = Db):
    """Check a closed day against Pentrix again (and repair what differs). A day that is still going cannot be reconciled."""
    await _scope(organization_id, db)
    if day >= today_ist():
        raise ValidationError("A day can be reconciled once it has ended.")
    service = PentrixPaymentService(db)
    row = await service.reconcile(organization_id, day)
    return DailyOut(**service.summary_out(row, day))


@router.get("/payments/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixPaymentService(db)
    return _payment_out(await service.with_candidate(await service.get(organization_id, payment_id)))


@router.get("/payments/{payment_id}/invoice")
async def payment_invoice(payment_id: uuid.UUID, download: bool = False, organization_id: uuid.UUID = Org, user: User = PaymentsView, db: AsyncSession = Db):
    """The invoice for a payment that was made, as a PDF (shown in the browser, or downloaded with ?download=true)."""
    await _scope(organization_id, db)
    service = PentrixPaymentService(db)
    payment, candidate = await service.with_candidate(await service.get(organization_id, payment_id))
    pdf, filename = service.invoice_pdf(payment, candidate)
    safe = "".join(c for c in filename if c.isalnum() or c in "-_.") or "invoice.pdf"
    disposition = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'{disposition}; filename="{safe}"'})


# ------------------------------------------------------------------ from Pentrix (signed, no user)


@internal_router.post("/bookings", response_model=MessageOut, dependencies=[Depends(verify_internal_signature)])
async def receive_booking(request: Request, db: AsyncSession = Db):
    """Pentrix tells ERPX a booking changed. Signed with the shared secret; an older message never overwrites a newer state."""
    data = await request.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise ValidationError("A booking is required.")
    await PentrixBookingService(db).upsert(await pentrix_organization_id(db), data)
    return MessageOut(message="Stored.")


@internal_router.post("/candidates", response_model=MessageOut, dependencies=[Depends(verify_internal_signature)])
async def receive_candidate(request: Request, db: AsyncSession = Db):
    """Pentrix tells ERPX a candidate's summary changed. Signed with the shared secret; an older message never overwrites a newer state."""
    data = await request.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise ValidationError("A candidate is required.")
    await PentrixCandidateService(db).upsert(await pentrix_organization_id(db), data)
    return MessageOut(message="Stored.")


@internal_router.post("/payments", response_model=MessageOut, dependencies=[Depends(verify_internal_signature)])
async def receive_payment(request: Request, db: AsyncSession = Db):
    """Pentrix tells ERPX a payment changed. Signed with the shared secret; matched only by Pentrix's payment id, and an older message
    never overwrites a newer state."""
    data = await request.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise ValidationError("A payment is required.")
    await PentrixPaymentService(db).upsert(await pentrix_organization_id(db), data)
    return MessageOut(message="Stored.")
