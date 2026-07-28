"""create ai tables (conversations, question generator, resume builder, interview simulator, evaluation, recommendations, insight reports)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ai_conversation_type_enum = postgresql.ENUM("tutor", "chat_assistant", name="ai_conversation_type")
ai_message_role_enum = postgresql.ENUM("user", "assistant", name="ai_message_role")
ai_interview_session_status_enum = postgresql.ENUM("in_progress", "completed", name="ai_interview_session_status")
ai_insight_report_type_enum = postgresql.ENUM(
    "student_performance", "attendance_trends", "sales_pipeline", "financial_health", name="ai_insight_report_type"
)

# `question_type` and `question_difficulty` already exist (created in 0009 for
# Examinations' question bank) — reused here via create_type=False, not recreated.
_NEW_ENUMS = [
    ai_conversation_type_enum,
    ai_message_role_enum,
    ai_interview_session_status_enum,
    ai_insight_report_type_enum,
]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in _NEW_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- AI Tutor / AI Chat Assistant ----
    op.create_table(
        "ai_conversations",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_type", postgresql.ENUM("tutor", "chat_assistant", name="ai_conversation_type", create_type=False), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_ai_conversations_organization_id", "ai_conversations", ["organization_id"])
    op.create_index("ix_ai_conversations_initiated_by_user_id", "ai_conversations", ["initiated_by_user_id"])
    op.create_index("ix_ai_conversations_student_id", "ai_conversations", ["student_id"])
    op.create_index("ix_ai_conversations_conversation_type", "ai_conversations", ["conversation_type"])

    op.create_table(
        "ai_messages",
        *_tc(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", postgresql.ENUM("user", "assistant", name="ai_message_role", create_type=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])

    # ---- AI Question Generator ----
    op.create_table(
        "ai_generated_question_batches",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("question_type", postgresql.ENUM("mcq", "true_false", "short_answer", "essay", "coding", name="question_type", create_type=False), nullable=False),
        sa.Column("difficulty", postgresql.ENUM("easy", "medium", "hard", name="question_difficulty", create_type=False), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_ai_generated_question_batches_organization_id", "ai_generated_question_batches", ["organization_id"])

    op.create_table(
        "ai_generated_question_items",
        *_tc(),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_generated_question_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("imported_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_questions_bank.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_ai_generated_question_items_batch_id", "ai_generated_question_items", ["batch_id"])

    # ---- AI Resume Builder ----
    op.create_table(
        "ai_generated_resumes",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_role", sa.String(length=150), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_ai_generated_resumes_organization_id", "ai_generated_resumes", ["organization_id"])
    op.create_index("ix_ai_generated_resumes_student_id", "ai_generated_resumes", ["student_id"])

    # ---- AI Interview Simulator ----
    op.create_table(
        "ai_interview_sessions",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_or_topic", sa.String(length=255), nullable=False),
        sa.Column("status", postgresql.ENUM("in_progress", "completed", name="ai_interview_session_status", create_type=False), nullable=False, server_default="in_progress"),
        sa.Column("overall_feedback", sa.Text(), nullable=True),
        sa.Column("overall_score", sa.Numeric(4, 1), nullable=True),
    )
    op.create_index("ix_ai_interview_sessions_organization_id", "ai_interview_sessions", ["organization_id"])
    op.create_index("ix_ai_interview_sessions_student_id", "ai_interview_sessions", ["student_id"])
    op.create_index("ix_ai_interview_sessions_status", "ai_interview_sessions", ["status"])

    op.create_table(
        "ai_interview_exchanges",
        *_tc(),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interview_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("score_out_of_10", sa.Numeric(3, 1), nullable=True),
    )
    op.create_index("ix_ai_interview_exchanges_session_id", "ai_interview_exchanges", ["session_id"])

    # ---- AI Assignment Evaluation ----
    op.create_table(
        "ai_evaluation_results",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score_out_of_100", sa.Numeric(5, 2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("improvement_areas", sa.Text(), nullable=True),
    )
    op.create_index("ix_ai_evaluation_results_organization_id", "ai_evaluation_results", ["organization_id"])
    op.create_index("ix_ai_evaluation_results_reference_type", "ai_evaluation_results", ["reference_type"])
    op.create_index("ix_ai_evaluation_results_reference_id", "ai_evaluation_results", ["reference_id"])

    # ---- AI Course Recommendation ----
    op.create_table(
        "ai_course_recommendation_logs",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommended_course_ids", postgresql.JSONB(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
    )
    op.create_index("ix_ai_course_recommendation_logs_organization_id", "ai_course_recommendation_logs", ["organization_id"])
    op.create_index("ix_ai_course_recommendation_logs_student_id", "ai_course_recommendation_logs", ["student_id"])

    # ---- AI Analytics ----
    op.create_table(
        "ai_insight_reports",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_type", postgresql.ENUM("student_performance", "attendance_trends", "sales_pipeline", "financial_health", name="ai_insight_report_type", create_type=False), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
    )
    op.create_index("ix_ai_insight_reports_organization_id", "ai_insight_reports", ["organization_id"])
    op.create_index("ix_ai_insight_reports_report_type", "ai_insight_reports", ["report_type"])
    op.create_index("ix_ai_insight_reports_reference_id", "ai_insight_reports", ["reference_id"])


def downgrade() -> None:
    op.drop_table("ai_insight_reports")
    op.drop_table("ai_course_recommendation_logs")
    op.drop_table("ai_evaluation_results")
    op.drop_table("ai_interview_exchanges")
    op.drop_table("ai_interview_sessions")
    op.drop_table("ai_generated_resumes")
    op.drop_table("ai_generated_question_items")
    op.drop_table("ai_generated_question_batches")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    for enum_type in reversed(_NEW_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
