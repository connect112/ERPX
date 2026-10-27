"""Which certificate each enrolled student is eligible for: participation or completion, never both."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.our_internships import models as _internship_models  # noqa: F401  (the foreign keys point at its tables)


class CertificateKind(str, enum.Enum):
    PARTICIPATION = "participation"
    COMPLETION = "completion"


class CertificateEligibility(TimestampedBase):
    """One row per student: the single certificate they are to receive. The unique constraint is what guarantees a student
    can never be on both lists."""

    __tablename__ = "internship_certificate_eligibility"
    __table_args__ = (UniqueConstraint("internship_id", "selection_id", name="uq_certificate_eligibility_student"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[CertificateKind] = mapped_column(
        SAEnum(CertificateKind, name="internship_certificate_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    chosen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chosen_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
