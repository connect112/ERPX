"""
Batches module — ORM models.

A `Batch` is a cohort of students taking a `Course` together on a shared
schedule — what Timetable entries and Live Classes actually get
scheduled against. Student enrollment into a batch is a `lms.enrollment`
concern (an `Enrollment` already links a student to a course); Batch
adds the "which group, which trainer, which dates" layer on top.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class BatchStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Batch(TimestampedBase):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_batch_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trainer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[BatchStatus] = mapped_column(
        SAEnum(BatchStatus, name="batch_status", values_callable=_values),
        default=BatchStatus.UPCOMING,
        server_default=BatchStatus.UPCOMING.value,
        nullable=False,
        index=True,
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class BatchEnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    REMOVED = "removed"


class BatchEnrollment(TimestampedBase):
    """
    Which students belong to which batch — kept as its own join table rather
    than a column on `lms.Enrollment`. `Enrollment` represents a student's
    overall academic status for a course (one row per student+course, enforced
    by a unique constraint); batch membership is a different-cardinality
    concept — a student can pass through more than one batch for the same
    course over time (a retake, a reschedule), and that shouldn't imply a
    second `Enrollment` row. This table's own uniqueness is per (batch,
    student), independent of `Enrollment` entirely.
    """

    __tablename__ = "batch_enrollments"
    __table_args__ = (UniqueConstraint("batch_id", "student_id", name="uq_batch_enrollment_batch_student"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[BatchEnrollmentStatus] = mapped_column(
        SAEnum(BatchEnrollmentStatus, name="batch_enrollment_status", values_callable=_values),
        default=BatchEnrollmentStatus.ACTIVE,
        server_default=BatchEnrollmentStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
