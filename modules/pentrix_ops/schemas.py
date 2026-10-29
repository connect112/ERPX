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
