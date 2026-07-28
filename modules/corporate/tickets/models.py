"""
Corporate / Tickets — ORM models.

`TicketComment.is_internal` distinguishes an internal engineering note
from a client-visible reply within the same thread, rather than
maintaining two separate comment tables.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.corporate.clients.models import Client  # noqa: F401
from modules.corporate.projects.models import Project  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class SupportTicket(TimestampedBase):
    __tablename__ = "corporate_support_tickets"
    __table_args__ = (UniqueConstraint("organization_id", "ticket_number", name="uq_support_ticket_org_number"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )

    ticket_number: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority", values_callable=_values),
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
        nullable=False,
        index=True,
    )
    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status", values_callable=_values),
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
        nullable=False,
        index=True,
    )
    raised_by_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    comments: Mapped[list["TicketComment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketComment.created_at"
    )


class TicketComment(TimestampedBase):
    __tablename__ = "corporate_ticket_comments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_support_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket: Mapped["SupportTicket"] = relationship(back_populates="comments")
