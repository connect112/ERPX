"""
Workshop Exams module -- ORM models.

A login-free MCQ exam for workshop attendees (e.g. a 200-person
workshop where nobody has, or needs, an ERPX account). Each attendee is
a plain name+email row with their own unguessable access token; the
token in their emailed link is the only credential, and their attempt
(started/answers/score) lives on the same row since there's exactly one
attempt per attendee. Deliberately separate from modules/examinations,
whose attempts and certificates require a Student + Course.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class WorkshopExamStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class WorkshopExam(TimestampedBase):
    __tablename__ = "workshop_exams"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workshop_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workshops.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30", nullable=False)
    status: Mapped[WorkshopExamStatus] = mapped_column(
        SAEnum(WorkshopExamStatus, name="workshop_exam_status", values_callable=_values),
        default=WorkshopExamStatus.DRAFT,
        server_default=WorkshopExamStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    show_result: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # Unguessable slug in the shared registration link students open to
    # fill in their details and take the exam (no pre-uploaded list needed).
    public_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    # Admin-defined extra questions about each student, asked on the
    # registration form after the always-present name + email:
    # [{"key", "label", "required", "type": "text"|"phone"|"select", "options": [...]}]
    info_fields: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)

    # When the certificate emails go out (admin-chosen). NULL = not
    # scheduled yet; certificates_dispatched_at is set once the scheduled
    # job (or "send now") has queued every certificate, so it never
    # dispatches the same exam twice.
    certificate_release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certificates_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certificate_heading: Mapped[str] = mapped_column(
        String(255), default="Certificate of Participation", server_default="Certificate of Participation",
        nullable=False,
    )
    certificate_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Admin-supplied certificate artwork (without a name). When present the
    # emailed certificate is that image with each attendee's name printed at
    # certificate_layout's position; the generated design is only the fallback.
    has_certificate_template: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    certificate_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # How certificate IDs look (see certificate_ids.py). NULL = the original WS-<year>-<hex> style.
    # `certificate_id_counter` counts the in-order numbers handed out so far; the next one is start + counter.
    certificate_id_pattern: Mapped[str | None] = mapped_column(String(80), nullable=True)
    certificate_id_start: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    # Optional step before sending: the admin looks at every certificate and marks it verified.
    certificate_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    certificate_id_counter: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class WorkshopExamCertificateTemplate(TimestampedBase):
    """The artwork bytes, kept apart from the exam row so listing exams never
    drags a multi-hundred-KB blob along. One row per exam."""

    __tablename__ = "workshop_exam_certificate_templates"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_exams.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkshopExamQuestion(TimestampedBase):
    __tablename__ = "workshop_exam_questions"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Indexes into `options`. One entry for a single-answer question; a
    # multiple-answer ("checkboxes") question is only right when the
    # attendee picks exactly this set.
    correct_indices: Mapped[list] = mapped_column(JSONB, nullable=False)
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    marks: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class WorkshopExamAttendee(TimestampedBase):
    __tablename__ = "workshop_exam_attendees"
    __table_args__ = (UniqueConstraint("exam_id", "email", name="uq_workshop_exam_attendee_email"),)

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Always stored lower-cased -- the unique constraint above relies on it.
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # What this person entered on the registration form (the admin's
    # extra info_fields), keyed by field key.
    info: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # {question_id: [chosen option indexes]} -- autosaved while answering.
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    certificate_number: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    certificate_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Added only to receive a certificate (a hackathon participant, say): never invited to, scored in or
    # counted in the exam itself.
    certificate_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # Review before sending: when the admin confirmed this certificate, and any fix to how the name is printed
    # ({"size", "dx", "dy"}, see certificate_template.NameAdjust).
    certificate_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certificate_adjust: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
