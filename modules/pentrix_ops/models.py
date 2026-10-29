"""
Pentrix operations in ERPX: a copy of Pentrix's appointments (Pentrix stays the source of truth) plus what ERPX adds to them -- who on
the team they are assigned to, when reminders were sent -- and where the regular pull of changes had got to.
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase

# Statuses a booking can have in Pentrix (the same words).
ACTIVE_STATUSES = ("requested", "confirmed", "in_progress")


class PentrixBooking(TimestampedBase):
    __tablename__ = "pentrix_bookings"
    __table_args__ = (
        Index("ix_pentrix_bookings_org_slot", "organization_id", "slot_start"),
        Index("ix_pentrix_bookings_staff_slot", "assigned_staff_user_id", "slot_start"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    # The stable id Pentrix gave the booking. Never matched by name or email.
    pentrix_booking_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    reference: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    pentrix_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    candidate_email: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")

    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # The ERPX user the appointment is assigned to (kept in step with Pentrix, which shows the name to the candidate).
    assigned_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_staff_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reschedule_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cancelled_by: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Pentrix's own timestamps: an older message never overwrites a newer state.
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the appointment was last put on its current time (booked, or rescheduled). A reminder whose moment had already passed by
    # then is not sent: someone who books ten minutes ahead is not sent a "30 minutes to go" email.
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reminders: Mapped[list["PentrixBookingReminder"]] = relationship(back_populates="booking", cascade="all, delete-orphan")


class PentrixCandidate(TimestampedBase):
    """A synchronised summary of one Pentrix candidate, keyed by the id Pentrix gave them (never matched by name or email). It holds what
    the lists, filters and dashboards need; the full record (every attempt, booking and payment) is asked of Pentrix when someone opens a
    candidate. Pentrix is the source of truth, so a newer Pentrix state always wins."""

    __tablename__ = "pentrix_candidates"
    __table_args__ = (
        Index("ix_pentrix_candidates_org_registered", "organization_id", "registered_at"),
        Index("ix_pentrix_candidates_org_qualified", "organization_id", "qualified"),
        Index("ix_pentrix_candidates_org_payment", "organization_id", "payment_status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    pentrix_user_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="", index=True)
    phone: Mapped[str | None] = mapped_column(String(24), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Assessment: not_started | in_progress | completed. `qualified` stays NULL until there is a submitted result, so "not qualified"
    # only ever means the candidate took the assessment and did not meet the criteria.
    assessment_state: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started", server_default="not_started")
    assessment_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    readiness_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The appointment that matters: the next open one, otherwise the latest.
    booking_pentrix_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    booking_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    booking_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    booking_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # paid | refunded | pending | failed | none. "paid" only follows a payment Pentrix's provider-verified webhook confirmed.
    payment_status: Mapped[str] = mapped_column(String(12), nullable=False, default="none", server_default="none")
    paid_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    payment_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    last_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    enrolled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Pentrix's own stamp: an older message never overwrites a newer state.
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PentrixBookingReminder(TimestampedBase):
    """One reminder to one person for one appointment time. The unique key is what stops a reminder going out twice, however many
    times the scheduler runs or overlaps; a rescheduled appointment has a new time, so it earns new reminders."""

    __tablename__ = "pentrix_booking_reminders"
    __table_args__ = (UniqueConstraint("booking_id", "kind", "audience", "slot_start", name="uq_pentrix_reminder"),)

    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pentrix_bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # 30m | 5m | now
    audience: Mapped[str] = mapped_column(String(10), nullable=False)  # candidate | staff
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending", server_default="pending")  # pending | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    booking: Mapped[PentrixBooking] = relationship(back_populates="reminders")


class PentrixSyncState(TimestampedBase):
    """Where the pull of Pentrix changes had got to (a cursor Pentrix gave us)."""

    __tablename__ = "pentrix_sync_state"

    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
