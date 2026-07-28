"""
AI module — ORM models.

Every AI feature that produces content worth reviewing or auditing later
(a tutor/chat transcript, generated questions, a resume draft, an
interview transcript, an evaluation, a recommendation, an insight
report) persists its result — an LLM call is comparatively expensive
and non-deterministic, so unlike a live-computed balance, "ask again"
is not a free substitute for storage. AI Course Recommendation is the
one exception with a log-only table (`CourseRecommendationLog`): the
recommendation itself is advisory and re-derivable on demand, so only a
lightweight audit trail is kept, not a full transcript.

Generated exam questions land in `GeneratedQuestionItem` as drafts, not
directly in Examinations' `exam_questions_bank` — a human must approve
and import each one (`imported_question_id`), the same human-in-the-loop
boundary Procurement draws around turning a goods receipt into a
payable Expense.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.courses.models import Course  # noqa: F401
from modules.examinations.question_bank.models import Difficulty, Question, QuestionType  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401
from modules.students.models import Student  # noqa: F401


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ConversationType(str, enum.Enum):
    TUTOR = "tutor"
    CHAT_ASSISTANT = "chat_assistant"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class InterviewSessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class InsightReportType(str, enum.Enum):
    STUDENT_PERFORMANCE = "student_performance"
    ATTENDANCE_TRENDS = "attendance_trends"
    SALES_PIPELINE = "sales_pipeline"
    FINANCIAL_HEALTH = "financial_health"


# ---- AI Tutor / AI Chat Assistant ----


class Conversation(TimestampedBase):
    __tablename__ = "ai_conversations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )

    conversation_type: Mapped[ConversationType] = mapped_column(
        SAEnum(ConversationType, name="ai_conversation_type", values_callable=_values), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(TimestampedBase):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="ai_message_role", values_callable=_values), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ---- AI Question Generator ----


class GeneratedQuestionBatch(TimestampedBase):
    __tablename__ = "ai_generated_question_batches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(QuestionType, name="question_type", values_callable=_values), nullable=False
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        SAEnum(Difficulty, name="question_difficulty", values_callable=_values), nullable=False
    )
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)

    items: Mapped[list["GeneratedQuestionItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class GeneratedQuestionItem(TimestampedBase):
    __tablename__ = "ai_generated_question_items"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_generated_question_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    imported_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exam_questions_bank.id", ondelete="SET NULL"), nullable=True
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    batch: Mapped["GeneratedQuestionBatch"] = relationship(back_populates="items")


# ---- AI Resume Builder ----


class GeneratedResume(TimestampedBase):
    __tablename__ = "ai_generated_resumes"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )

    target_role: Mapped[str | None] = mapped_column(String(150), nullable=True)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)


# ---- AI Interview Simulator ----


class InterviewSession(TimestampedBase):
    __tablename__ = "ai_interview_sessions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role_or_topic: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[InterviewSessionStatus] = mapped_column(
        SAEnum(InterviewSessionStatus, name="ai_interview_session_status", values_callable=_values),
        default=InterviewSessionStatus.IN_PROGRESS,
        server_default=InterviewSessionStatus.IN_PROGRESS.value,
        nullable=False,
        index=True,
    )
    overall_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)

    exchanges: Mapped[list["InterviewExchange"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewExchange.order_index"
    )


class InterviewExchange(TimestampedBase):
    __tablename__ = "ai_interview_exchanges"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_out_of_10: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)

    session: Mapped["InterviewSession"] = relationship(back_populates="exchanges")


# ---- AI Assignment Evaluation ----


class AIEvaluationResult(TimestampedBase):
    __tablename__ = "ai_evaluation_results"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Opaque reference to the graded work (e.g. "assignment_submission", a
    # submission UUID) rather than a hard FK, since this evaluates work from
    # multiple modules (LMS assignments today, others later) without this
    # module needing a foreign key into each one.
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

    score_out_of_100: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_areas: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---- AI Course Recommendation ----


class CourseRecommendationLog(TimestampedBase):
    __tablename__ = "ai_course_recommendation_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )

    recommended_course_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---- AI Analytics ----


class AIInsightReport(TimestampedBase):
    __tablename__ = "ai_insight_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    report_type: Mapped[InsightReportType] = mapped_column(
        SAEnum(InsightReportType, name="ai_insight_report_type", values_callable=_values), nullable=False, index=True
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
