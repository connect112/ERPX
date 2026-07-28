"""
Audit module — ORM models.

`AuditLog` rows are written automatically by `modules.audit.hooks`
(SQLAlchemy session events), not by application code calling into this
module directly — every module gets audit logging for free just by using
the shared `AsyncSession`/`TimestampedBase` machinery every other module
already uses. See `modules/audit/hooks.py` for the capture mechanism.

Rows are append-only: there is deliberately no `updated_at` (an audit
entry that could itself be silently edited after the fact isn't an audit
trail).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import UUIDPrimaryKeyMixin
from app.db.session import Base


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_org_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", values_callable=_values), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # CREATE: full new-state snapshot. UPDATE: {"field": {"old": ..., "new": ...}}.
    # DELETE: full last-known-state snapshot. Always JSON-serializable.
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
