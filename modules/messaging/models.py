"""
Messaging module — ORM models.

A private, 1:1 doubt-clarification channel between a student and a
trainer actually teaching them. There is no separate membership/pairing
table: which trainer(s) a student may talk to (and vice versa) is
derived live from `Batch.trainer_id` + `BatchEnrollment` -- see
service.py -- exactly like modules/live_classes already derives its own
student/trainer ownership checks. That keeps a batch reassignment or an
enrollment removal retroactively cut off *new* messages without this
module needing to know anything about batches beyond that derivation.

Admin's read-only oversight is not a separate audit-log table either:
it's a second, permission-gated view onto these exact same rows,
mirroring modules/corporate/tickets' split between client-facing and
admin-facing routes over one schema.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.documents.models import Document  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401
from modules.students.models import Student  # noqa: F401
from modules.trainers.models import Trainer  # noqa: F401


class MessagingConversation(TimestampedBase):
    __tablename__ = "messaging_conversations"
    __table_args__ = (
        UniqueConstraint("student_id", "trainer_id", name="uq_messaging_conversation_pair"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trainer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False, index=True
    )


class MessagingMessage(TimestampedBase):
    __tablename__ = "messaging_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messaging_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL (not CASCADE): a user account being deleted shouldn't erase
    # the conversation history the other side can still see.
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    # Service-level invariant, not a DB constraint: at least one of
    # body/attachment_document_id must be set (see service.py::send_message).
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
