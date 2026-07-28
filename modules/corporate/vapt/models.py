"""
Corporate / VAPT — ORM models.

`VAPTEngagement` hangs off a `Project` (project_type=VAPT by convention,
not enforced at the DB level) and owns a set of `VAPTFinding` rows — the
actual deliverable content of a penetration test.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.corporate.projects.models import Project  # noqa: F401
from modules.employees.models import Employee  # noqa: F401


class VAPTEngagementType(str, enum.Enum):
    WEB_APP = "web_app"
    MOBILE_APP = "mobile_app"
    NETWORK = "network"
    CLOUD = "cloud"
    API = "api"
    RED_TEAM = "red_team"
    OTHER = "other"


class VAPTEngagementStatus(str, enum.Enum):
    SCOPING = "scoping"
    IN_PROGRESS = "in_progress"
    REPORTING = "reporting"
    RETEST = "retest"
    CLOSED = "closed"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class FindingStatus(str, enum.Enum):
    OPEN = "open"
    RETESTING = "retesting"
    FIXED = "fixed"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class VAPTEngagement(TimestampedBase):
    __tablename__ = "corporate_vapt_engagements"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_tester_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    scope_description: Mapped[str] = mapped_column(Text, nullable=False)
    engagement_type: Mapped[VAPTEngagementType] = mapped_column(
        SAEnum(VAPTEngagementType, name="vapt_engagement_type", values_callable=_values), nullable=False
    )
    methodology: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[VAPTEngagementStatus] = mapped_column(
        SAEnum(VAPTEngagementStatus, name="vapt_engagement_status", values_callable=_values),
        default=VAPTEngagementStatus.SCOPING,
        server_default=VAPTEngagementStatus.SCOPING.value,
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class VAPTFinding(TimestampedBase):
    __tablename__ = "corporate_vapt_findings"

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_vapt_engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        SAEnum(FindingSeverity, name="vapt_finding_severity", values_callable=_values), nullable=False, index=True
    )
    cvss_score: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FindingStatus] = mapped_column(
        SAEnum(FindingStatus, name="vapt_finding_status", values_callable=_values),
        default=FindingStatus.OPEN,
        server_default=FindingStatus.OPEN.value,
        nullable=False,
        index=True,
    )
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
