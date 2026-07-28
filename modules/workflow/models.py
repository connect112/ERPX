"""
Workflow module — a generic, configurable approval-request engine.

Any other module (Leave, Expenses, Purchase Orders, ...) can plug into
this without its own approval plumbing: define an `ApprovalWorkflow` for
an `entity_type` string (e.g. "leave_application"), give it ordered
`ApprovalStep`s each naming the `Role` that must approve at that step,
then call `ApprovalRequestService.submit_request(entity_type, entity_id,
...)` whenever a record of that type needs sign-off. The engine tracks
`current_step_order` on the request and walks it forward on each
approval; a single rejection at any step terminates the whole request
rather than just that step, which matches how approval chains work in
practice (one "no" kills the request, it doesn't get skipped).

Deliberately keyed by `entity_type` + `entity_id` (the same polymorphic
pattern `modules.documents.Document` uses) rather than a FK per module,
so this module never needs to import or depend on Leave/Expenses/PO.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class ApprovalRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ApprovalWorkflow(TimestampedBase):
    __tablename__ = "approval_workflows"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", "name", name="uq_workflow_org_entity_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)


class ApprovalStep(TimestampedBase):
    __tablename__ = "approval_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_order", name="uq_approval_step_workflow_order"),
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ApprovalRequest(TimestampedBase):
    __tablename__ = "approval_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ApprovalRequestStatus] = mapped_column(
        SAEnum(ApprovalRequestStatus, name="approval_request_status", values_callable=_values),
        default=ApprovalRequestStatus.PENDING,
        server_default=ApprovalRequestStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalAction(TimestampedBase):
    __tablename__ = "approval_actions"

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        SAEnum(ApprovalDecision, name="approval_decision", values_callable=_values), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
