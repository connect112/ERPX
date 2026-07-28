"""
Corporate / Projects — ORM models.

`Project` is the generic engagement container every specific service
(VAPT, SOC) hangs off via its own `project_id` foreign key, rather than
each service type carrying its own duplicated name/dates/status/manager
fields. VAPT and SOC add only what's specific to them.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.corporate.clients.models import Client  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class ProjectType(str, enum.Enum):
    VAPT = "vapt"
    SOC = "soc"
    CONSULTING = "consulting"
    TRAINING = "training"
    OTHER = "other"


class ProjectStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Project(TimestampedBase):
    __tablename__ = "corporate_projects"
    __table_args__ = (UniqueConstraint("organization_id", "project_code", name="uq_corporate_project_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_manager_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    project_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[ProjectType] = mapped_column(
        SAEnum(ProjectType, name="corporate_project_type", values_callable=_values),
        default=ProjectType.OTHER,
        server_default=ProjectType.OTHER.value,
        nullable=False,
        index=True,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="corporate_project_status", values_callable=_values),
        default=ProjectStatus.PLANNED,
        server_default=ProjectStatus.PLANNED.value,
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
