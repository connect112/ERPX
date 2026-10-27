"""
Offer letter generator -- stored settings, uploaded branding images, the generated letters, who they were emailed to, and an
audit trail of what was done.

Settings and images belong to the organisation (its defaults, ``internship_id`` empty) or to one internship (its overrides).
Each student's letter is kept per version: regenerating makes a new version and keeps the old one, so a letter that was sent
can always be looked at again.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db.base_model import TimestampedBase
from modules.our_internships import models as _internship_models  # noqa: F401  (the foreign keys point at its tables)


class LetterStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    APPROVED = "approved"
    RELEASED = "released"


class DeliveryStatus(str, enum.Enum):
    NONE = "none"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class OfferLetterSetting(TimestampedBase):
    """The saved settings: an organisation's defaults, or what one internship overrides. ``config`` is partial JSON."""

    __tablename__ = "offer_letter_settings"
    __table_args__ = (
        Index("uq_offer_letter_setting_org", "organization_id", unique=True, postgresql_where=text("internship_id IS NULL")),
        Index("uq_offer_letter_setting_internship", "internship_id", unique=True, postgresql_where=text("internship_id IS NOT NULL")),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    internship_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # The design was approved when the settings and images hashed to this; any later change makes the approval stale.
    approved_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OfferLetterAsset(TimestampedBase):
    """An uploaded image: logo, watermark, signature, stamp or an extra branding image."""

    __tablename__ = "offer_letter_assets"
    __table_args__ = (
        Index("uq_offer_letter_asset_org", "organization_id", "kind", unique=True, postgresql_where=text("internship_id IS NULL")),
        Index("uq_offer_letter_asset_internship", "internship_id", "kind", unique=True, postgresql_where=text("internship_id IS NOT NULL")),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    internship_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OfferLetter(TimestampedBase):
    """One version of one student's generated letter."""

    __tablename__ = "offer_letters"
    __table_args__ = (
        UniqueConstraint("selection_id", "version", name="uq_offer_letter_version"),
        # one current letter per student: asking for generation twice cannot make two
        Index("uq_offer_letter_current", "selection_id", unique=True, postgresql_where=text("is_current")),
        Index("ix_offer_letters_internship_current", "internship_id", "is_current"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    internship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False)
    selection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("our_internship_selections.id", ondelete="SET NULL"), nullable=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institution_students.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    reference: Mapped[str] = mapped_column(String(60), nullable=False)
    # What the letter says about the student, as it was when generated (the student may be edited later).
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_email: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=LetterStatus.PENDING.value, server_default=LetterStatus.PENDING.value, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pdf_data: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    pdf_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Hash of the settings, images and student details the PDF was made from; when it no longer matches, the letter is outdated.
    data_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Sending
    delivery_status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.NONE.value, server_default=DeliveryStatus.NONE.value, nullable=False)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    delivery_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class OfferLetterDelivery(TimestampedBase):
    """One attempt to email a letter: the history of sends, retries and failures."""

    __tablename__ = "offer_letter_deliveries"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    letter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offer_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # queued | sent | failed
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OfferLetterEvent(TimestampedBase):
    """Who configured, approved, generated, regenerated or released what, and when."""

    __tablename__ = "offer_letter_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    internship_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True, index=True)
    letter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offer_letters.id", ondelete="SET NULL"), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
