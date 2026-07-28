"""
Pentrix / Lab Instances — ORM models.

Consolidates the spec's `vm-manager/` and `docker-labs/` folders into one
`LabInstance` table: both are "launch an isolated environment for a
student" — the only real difference is which provisioner backend
handles it, which is an implementation detail of the provisioner (see
`provisioning.py`), not a different data shape.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.pentrix.labs.models import Lab  # noqa: F401
from modules.students.models import Student  # noqa: F401


class LabInstanceStatus(str, enum.Enum):
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    EXPIRED = "expired"
    FAILED = "failed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class LabInstance(TimestampedBase):
    __tablename__ = "pentrix_lab_instances"

    lab_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pentrix_labs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Opaque handle returned by the provisioner (container ID, VM ID, etc).
    environment_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[LabInstanceStatus] = mapped_column(
        SAEnum(LabInstanceStatus, name="lab_instance_status", values_callable=_values),
        default=LabInstanceStatus.PROVISIONING,
        server_default=LabInstanceStatus.PROVISIONING.value,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
