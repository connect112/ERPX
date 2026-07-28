"""
Reports module — ORM models.

There is no `ReportDefinition` table: the catalog of available reports
is static application metadata (which reports exist, which module owns
each, what parameters it takes), not tenant data — it lives in
`registry.py` as a plain Python structure, the same way
`authorization.service.DEFAULT_PERMISSIONS` is a code constant rather
than a seeded table nobody but the platform ever writes to.

`ReportExecution` is the audit trail of every report actually run —
worth persisting because a report over live data is not reproducible
after the fact the way a static definition would be. `ScheduledReport`
configures recurring runs; a Celery beat task (`tasks.py`) is the only
thing that ever creates `ReportExecution` rows on a schedule's behalf.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class ExportFormat(str, enum.Enum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class ReportExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class ScheduleFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ReportExecution(TimestampedBase):
    __tablename__ = "report_executions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    executed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scheduled_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )

    report_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    export_format: Mapped[ExportFormat] = mapped_column(
        SAEnum(ExportFormat, name="report_export_format", values_callable=_values), nullable=False
    )
    status: Mapped[ReportExecutionStatus] = mapped_column(
        SAEnum(ReportExecutionStatus, name="report_execution_status", values_callable=_values), nullable=False, index=True
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScheduledReport(TimestampedBase):
    __tablename__ = "scheduled_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    report_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    export_format: Mapped[ExportFormat] = mapped_column(
        SAEnum(ExportFormat, name="report_export_format", values_callable=_values), nullable=False
    )
    frequency: Mapped[ScheduleFrequency] = mapped_column(
        SAEnum(ScheduleFrequency, name="report_schedule_frequency", values_callable=_values), nullable=False
    )
    recipient_emails: Mapped[list] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
