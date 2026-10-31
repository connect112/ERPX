"""
Internship onboarding: configuration, templates, one application per selected student, documents, events, and the
payment ledger.

The application is 1:1 with ``our_internship_selections``. The selection keeps the fields the manual process and the LMS
grant already rely on (offer response, verification, payment, LMS access), and the automated flow writes those same
fields, so there is one source of truth for each. Money is ``Numeric(12, 2)``; nothing financial is a float.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.our_internships import models as _internship_models  # noqa: F401  (foreign keys point at its tables)

_ORG = "organizations.id"


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey(_ORG, ondelete="CASCADE"), nullable=False, index=True)


class OnboardingConfigRecord(TimestampedBase):
    """The current onboarding settings of one internship. Every save also writes an immutable ``OnboardingConfigVersion``."""

    __tablename__ = "internship_onboarding_configs"

    organization_id: Mapped[uuid.UUID] = _org()
    internship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("internship_onboarding_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OnboardingConfigVersion(TimestampedBase):
    __tablename__ = "internship_onboarding_config_versions"
    __table_args__ = (UniqueConstraint("config_id", "version", name="uq_onboarding_config_version"),)

    organization_id: Mapped[uuid.UUID] = _org()
    config_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("internship_onboarding_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OnboardingTemplate(TimestampedBase):
    """A reusable onboarding setup. Applying it copies its settings into an internship; later edits never reach internships."""

    __tablename__ = "internship_onboarding_templates"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_onboarding_template_name"),)

    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OnboardingTemplateVersion(TimestampedBase):
    __tablename__ = "internship_onboarding_template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version", name="uq_onboarding_template_version"),)

    organization_id: Mapped[uuid.UUID] = _org()
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("internship_onboarding_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OnboardingCounter(TimestampedBase):
    """The last application number handed out per organization and year (locked row, so numbers never repeat)."""

    __tablename__ = "internship_onboarding_counters"
    __table_args__ = (UniqueConstraint("organization_id", "series", "year", name="uq_onboarding_counter_series"),)
    __audit_skip__ = True

    organization_id: Mapped[uuid.UUID] = _org()
    # "application" for references; "receipt" and "credit_note" for financial documents (migration 0100)
    series: Mapped[str] = mapped_column(String(20), default="application", server_default="application", nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class OnboardingApplication(TimestampedBase):
    __tablename__ = "internship_onboarding_applications"
    __table_args__ = (
        UniqueConstraint("organization_id", "reference", name="uq_onboarding_application_reference"),
        Index("ix_onboarding_applications_internship", "internship_id"),
    )
    # The link token only ever exists as a hash here, and even that stays out of the audit trail; the acceptance's
    # network details are kept on the row (limited) but not copied into the audit table.
    __audit_exclude_fields__ = {"token_hash", "acceptance_meta", "last_activity_at", "updated_at"}

    organization_id: Mapped[uuid.UUID] = _org()
    internship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False)
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    reference: Mapped[str] = mapped_column(String(40), nullable=False)
    # the link
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    token_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # progress
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_step: Mapped[str] = mapped_column(String(30), default="welcome", server_default="welcome", nullable=False)
    # information the student confirmed or proposed to change (original values are kept beside the proposal)
    info_original: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    info_proposed: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    info_review_status: Mapped[str] = mapped_column(String(20), default="none", server_default="none", nullable=False)
    form_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    form_responses: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # the offer decision (the selection's offer_response is the status; this is the record of the decision)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    declaration_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fee_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acceptance_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # individual deadline and late onboarding
    deadline_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class OnboardingDocument(TimestampedBase):
    """One uploaded version of one required document. New uploads add a version; old ones are superseded, never deleted."""

    __tablename__ = "internship_onboarding_documents"
    __table_args__ = (UniqueConstraint("application_id", "requirement_key", "version", name="uq_onboarding_document_version"),)

    organization_id: Mapped[uuid.UUID] = _org()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_key: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    content_type: Mapped[str] = mapped_column(String(60), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    # submitted | verified | rejected | superseded
    status: Mapped[str] = mapped_column(String(20), default="submitted", server_default="submitted", nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class OnboardingEvent(TimestampedBase):
    """The student's timeline: what happened, who did it (student, staff member or system) and why. Append-only."""

    __tablename__ = "internship_onboarding_events"
    __audit_skip__ = True  # it is itself the log; rows are never updated

    organization_id: Mapped[uuid.UUID] = _org()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(10), nullable=False)  # student | staff | system
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)


# ------------------------------------------------------------------ payments (migration 0099)


class PaymentOrder(TimestampedBase):
    """What the student is asked to pay, fixed when the obligation is created. A gateway order points at the provider's."""

    __tablename__ = "internship_payment_orders"
    __audit_exclude_fields__ = {"payment_session_id", "last_checked_at", "updated_at"}

    organization_id: Mapped[uuid.UUID] = _org()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # cashfree | bank_transfer | upi
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # created | active | paid | failed | expired | cancelled
    status: Mapped[str] = mapped_column(String(20), default="created", server_default="created", nullable=False, index=True)
    merchant_order_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_session_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymentTransaction(TimestampedBase):
    """The ledger. kind: payment (money in), refund (money out), charge (adds to what is owed, e.g. a late fee), waiver
    (reduces it). Amounts are always positive; the kind gives the direction. Rows are corrected by new rows, not edits
    of confirmed money."""

    __tablename__ = "internship_payment_transactions"
    __table_args__ = (
        # one live claim per bank/UPI reference in an organization: a UTR cannot be used twice
        Index(
            "uq_payment_reference_live",
            "organization_id",
            "reference_normalized",
            unique=True,
            postgresql_where=text("kind = 'payment' AND reference_normalized IS NOT NULL AND status IN ('awaiting_verification', 'confirmed')"),
        ),
        Index("uq_payment_provider_payment", "provider", "provider_payment_id", unique=True,
              postgresql_where=text("provider_payment_id IS NOT NULL")),
    )

    organization_id: Mapped[uuid.UUID] = _org()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("internship_payment_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # pending | awaiting_verification | confirmed | rejected | failed
    status: Mapped[str] = mapped_column(String(25), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference_normalized: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    proof_storage_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    proof_filename: Mapped[str | None] = mapped_column(String(160), nullable=True)
    proof_content_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    proof_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # a refund points at the payment it returns money from (migration 0100)
    refund_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("internship_payment_transactions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    provider_refund_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaymentWebhookEvent(TimestampedBase):
    """Every gateway notification received, by hash, so a repeated one is recognised and processed once."""

    __tablename__ = "internship_payment_webhooks"
    __audit_skip__ = True

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_ORG, ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    merchant_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(200), nullable=True)


class FinancialDocument(TimestampedBase):
    """A receipt (or tax invoice) for a confirmed payment, or a credit note for a confirmed refund. Issued once per
    transaction, never edited: the numbers, amounts and parties are fixed in ``details`` and in the stored PDF."""

    __tablename__ = "internship_financial_documents"
    __table_args__ = (UniqueConstraint("organization_id", "number", name="uq_financial_document_number"),)
    __audit_exclude_fields__ = {"email_attempts", "updated_at"}

    organization_id: Mapped[uuid.UUID] = _org()
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_payment_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # receipt | tax_invoice | credit_note
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # none (emails off) | pending | sent | failed
    email_status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending", nullable=False)
    email_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
