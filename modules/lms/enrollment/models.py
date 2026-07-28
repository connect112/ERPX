"""
LMS / Enrollment — ORM models.

`Enrollment` is the link between a Student (Students module) and a
Course (Courses module) — the prerequisite for Progress tracking,
Assignments, Assessments, and Certificates, all of which only make
sense for an enrolled student.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.students.models import Student  # noqa: F401


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


class Enrollment(TimestampedBase):
    __tablename__ = "lms_enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrolled_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(
            EnrollmentStatus,
            name="enrollment_status",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=EnrollmentStatus.ACTIVE,
        server_default=EnrollmentStatus.ACTIVE.value,
        nullable=False,
    )
