"""
Corporate / SOC — ORM models.

`SOCService` is tied directly to a `Client` (not a `Project`) because
Security Operations Center monitoring is an ongoing subscription, not a
time-boxed engagement — a `project_id` is optional for the cases a
client's SOC subscription happens to be tracked as part of a broader
consulting project.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.corporate.clients.models import Client  # noqa: F401
from modules.corporate.projects.models import Project  # noqa: F401
from modules.employees.models import Employee  # noqa: F401


class SOCServiceType(str, enum.Enum):
    MONITORING = "monitoring"
    INCIDENT_RESPONSE = "incident_response"
    THREAT_HUNTING = "threat_hunting"
    LOG_MANAGEMENT = "log_management"


class SOCServiceStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class SOCService(TimestampedBase):
    __tablename__ = "corporate_soc_services"

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True
    )

    service_type: Mapped[SOCServiceType] = mapped_column(
        SAEnum(SOCServiceType, name="soc_service_type", values_callable=_values), nullable=False
    )
    sla_response_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SOCServiceStatus] = mapped_column(
        SAEnum(SOCServiceStatus, name="soc_service_status", values_callable=_values),
        default=SOCServiceStatus.ACTIVE,
        server_default=SOCServiceStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SOCIncident(TimestampedBase):
    __tablename__ = "corporate_soc_incidents"

    soc_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_soc_services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(
        SAEnum(IncidentSeverity, name="soc_incident_severity", values_callable=_values), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        SAEnum(IncidentStatus, name="soc_incident_status", values_callable=_values),
        default=IncidentStatus.OPEN,
        server_default=IncidentStatus.OPEN.value,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
