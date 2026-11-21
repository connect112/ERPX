import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.courses.models import Course  # noqa: F401
from modules.our_internships import models as _internship_models  # noqa: F401  (internship_id points at its table)


class DiscussionThread(TimestampedBase):
    __tablename__ = "lms_discussion_threads"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Set for an activity that belongs to ONE internship (a cohort): only that internship's granted students and staff reach it. Null
    # (every record that existed before) means course-wide, exactly as before.
    internship_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DiscussionReply(TimestampedBase):
    __tablename__ = "lms_discussion_replies"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lms_discussion_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
