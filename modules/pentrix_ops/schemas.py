import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BookingOut(BaseModel):
    id: uuid.UUID
    pentrix_booking_id: str
    reference: str | None = None
    candidate_name: str
    candidate_email: str
    slot_start: datetime
    slot_end: datetime
    duration_minutes: int
    status: str
    status_label: str
    assigned_staff_user_id: uuid.UUID | None = None
    assigned_staff_name: str | None = None
    meeting_url: str | None = None
    notes: str | None = None
    reschedule_count: int = 0
    cancelled_by: str | None = None
    updated_at: datetime | None = None


class BookingPage(BaseModel):
    items: list[BookingOut]
    total: int
    page: int
    page_size: int


class StaffOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class AssignRequest(BaseModel):
    staff_user_id: uuid.UUID | None = None  # null takes the assignment off


class StatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class RescheduleRequest(BaseModel):
    slot_start: datetime


class MeetingRequest(BaseModel):
    meeting_url: str | None = Field(default=None, max_length=512)


class NotesRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class BlockRequest(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: str = Field(default="", max_length=200)


class AvailabilitySettings(BaseModel):
    """The rules Pentrix applies when a candidate books. Every field is optional on update: only what is sent changes."""

    timezone: str | None = None
    working_days: list[int] | None = None
    start_time: str | None = None
    end_time: str | None = None
    slot_minutes: int | None = None
    capacity: int | None = None
    advance_days: int | None = None
    min_notice_minutes: int | None = None
    available_from: str | None = None
    available_until: str | None = None
    cancel_cutoff_minutes: int | None = None
    max_reschedules: int | None = None
    meeting_url_template: str | None = None


class MessageOut(BaseModel):
    message: str


class SyncOut(BaseModel):
    updated: int


class FreeForm(BaseModel):
    """A pass-through for answers that are Pentrix's own shape (the slots, the closed periods)."""

    data: Any = None


# ---- candidates ---------------------------------------------------------------------------------------------------------------


class AssessmentLine(BaseModel):
    state: str
    attempts: int = 0
    readiness_commitment_pct: float | None = None
    technical_pct: float | None = None
    qualified: bool | None = None
    assessed_at: datetime | None = None


class BookingLine(BaseModel):
    status: str
    status_label: str
    slot_start: datetime | None = None
    slot_end: datetime | None = None
    scheduled: bool = False


class PaymentLine(BaseModel):
    status: str
    paid_total_paise: int = 0
    currency: str = "INR"
    last_paid_at: datetime | None = None
    payment_count: int = 0


class CandidateOut(BaseModel):
    id: uuid.UUID
    pentrix_user_id: str
    full_name: str
    email: str
    phone: str | None = None
    email_verified: bool = False
    registered_at: datetime
    assessment: AssessmentLine
    booking: BookingLine | None = None
    payment: PaymentLine
    marketing_opt_in: bool = False
    enrolled: bool = False
    last_activity_at: datetime | None = None


class CandidatePage(BaseModel):
    items: list[CandidateOut]
    total: int
    page: int
    page_size: int


class CandidateEdit(BaseModel):
    """Only these can be changed from ERPX. The email address is how the person signs in, so it is not editable here."""

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=24)


class EmailLine(BaseModel):
    id: uuid.UUID
    subject: str
    status: str
    template_key: str | None = None
    module: str | None = None
    error: str | None = None
    sent_at: datetime


class CandidateDetail(BaseModel):
    candidate: CandidateOut
    live: bool
    error: str | None = None
    profile: Any = None  # Pentrix's own shape: registration, assessment, bookings, payments, enrollment, activity
    emails: list[EmailLine] = []


class AssessmentDetail(BaseModel):
    candidate: CandidateOut
    live: bool
    error: str | None = None
    assessment: Any = None


class OverviewOut(BaseModel):
    configured: bool
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    totals: dict[str, int]
    bookings: dict[str, int]
    funnel: list[dict[str, Any]]
    payment_status: dict[str, int]
    recent_registrations: list[CandidateOut]


# ---- payments -----------------------------------------------------------------------------------------------------------------


class PaymentOut(BaseModel):
    id: uuid.UUID
    pentrix_payment_id: str
    candidate_id: uuid.UUID | None = None
    candidate_name: str
    candidate_email: str
    provider: str
    method: str
    purpose: str
    purpose_label: str
    amount_paise: int
    currency: str
    status: str
    status_label: str
    pentrix_status: str
    reference: str | None = None
    provider_order_id: str | None = None
    invoice_number: str | None = None
    receipt_number: str | None = None
    provisioning_status: str | None = None
    created_at: datetime | None = None
    paid_at: datetime | None = None
    failed_at: datetime | None = None
    refunded_at: datetime | None = None
    invoice_available: bool = False


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int


class PaymentSyncState(BaseModel):
    configured: bool
    last_synced_at: datetime | None = None
    last_error: str | None = None


class PaymentsSummaryOut(BaseModel):
    date: Any
    collected_today_paise: int
    successful_today: int
    refunded_today_paise: int
    pending_payments: int
    latest_payment: PaymentOut | None = None
    recent: list[PaymentOut]
    sync: PaymentSyncState


class DailyOut(BaseModel):
    date: Any
    status: str  # matched | mismatch | error | open | unreconciled
    reconciled: bool
    reconciled_at: datetime | None = None
    successful_count: int
    collected_paise: int
    pending_count: int
    failed_count: int
    refund_count: int
    refunded_paise: int
    partial_refund_count: int
    net_paise: int
    mismatches: list[dict[str, Any]] = []
    repaired_count: int = 0
    attempts: int = 0
    last_error: str | None = None


class DailyDetail(BaseModel):
    summary: DailyOut
    transactions: list[PaymentOut]
