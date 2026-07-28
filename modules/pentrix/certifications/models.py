import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.students.models import Student  # noqa: F401


class PentrixCertification(TimestampedBase):
    __tablename__ = "pentrix_certifications"
    __table_args__ = (
        UniqueConstraint("student_id", "track_name", name="uq_pentrix_cert_student_track"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_name: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    points_at_issuance: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
