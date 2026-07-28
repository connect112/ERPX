"""create examinations tables (question bank, exams, evaluation, practicals, viva)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

question_type_enum = postgresql.ENUM(
    "mcq", "true_false", "short_answer", "essay", "coding", name="question_type"
)
question_difficulty_enum = postgresql.ENUM("easy", "medium", "hard", name="question_difficulty")
exam_status_enum = postgresql.ENUM("draft", "scheduled", "completed", "cancelled", name="exam_status")
exam_attempt_status_enum = postgresql.ENUM(
    "in_progress", "submitted", "evaluated", name="exam_attempt_status"
)


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
    for enum_type in (
        question_type_enum, question_difficulty_enum, exam_status_enum, exam_attempt_status_enum,
    ):
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Question Bank ----
    op.create_table(
        "exam_questions_bank",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", postgresql.ENUM("mcq", "true_false", "short_answer", "essay", "coding", name="question_type", create_type=False), nullable=False, server_default="mcq"),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("default_marks", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("difficulty", postgresql.ENUM("easy", "medium", "hard", name="question_difficulty", create_type=False), nullable=False, server_default="medium"),
    )
    op.create_index("ix_exam_questions_bank_organization_id", "exam_questions_bank", ["organization_id"])
    op.create_index("ix_exam_questions_bank_course_id", "exam_questions_bank", ["course_id"])

    # ---- Exams ----
    op.create_table(
        "exam_exams",
        *_tc(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exam_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("passing_marks", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("status", postgresql.ENUM("draft", "scheduled", "completed", "cancelled", name="exam_status", create_type=False), nullable=False, server_default="draft"),
    )
    op.create_index("ix_exam_exams_course_id", "exam_exams", ["course_id"])

    op.create_table(
        "exam_exam_questions",
        *_tc(),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_questions_bank.id", ondelete="CASCADE"), nullable=False),
        sa.Column("marks_allocated", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("exam_id", "question_id", name="uq_exam_question"),
        sa.UniqueConstraint("exam_id", "order_index", name="uq_exam_question_order"),
    )
    op.create_index("ix_exam_exam_questions_exam_id", "exam_exam_questions", ["exam_id"])
    op.create_index("ix_exam_exam_questions_question_id", "exam_exam_questions", ["question_id"])

    # ---- Evaluation ----
    op.create_table(
        "exam_attempts",
        *_tc(),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("status", postgresql.ENUM("in_progress", "submitted", "evaluated", name="exam_attempt_status", create_type=False), nullable=False, server_default="in_progress"),
        sa.UniqueConstraint("exam_id", "student_id", name="uq_exam_attempt_student"),
    )
    op.create_index("ix_exam_attempts_exam_id", "exam_attempts", ["exam_id"])
    op.create_index("ix_exam_attempts_student_id", "exam_attempts", ["student_id"])

    op.create_table(
        "exam_answers",
        *_tc(),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_questions_bank.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("marks_awarded", sa.Integer(), nullable=True),
        sa.Column("evaluated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),
    )
    op.create_index("ix_exam_answers_attempt_id", "exam_answers", ["attempt_id"])
    op.create_index("ix_exam_answers_question_id", "exam_answers", ["question_id"])

    # ---- Practicals ----
    op.create_table(
        "exam_practicals",
        *_tc(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("rubric", sa.Text(), nullable=True),
        sa.Column("total_marks", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("passing_marks", sa.Integer(), nullable=False, server_default="40"),
    )
    op.create_index("ix_exam_practicals_course_id", "exam_practicals", ["course_id"])

    op.create_table(
        "exam_practical_results",
        *_tc(),
        sa.Column("practical_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_practicals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("evaluated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("practical_id", "student_id", name="uq_practical_result_student"),
    )
    op.create_index("ix_exam_practical_results_practical_id", "exam_practical_results", ["practical_id"])
    op.create_index("ix_exam_practical_results_student_id", "exam_practical_results", ["student_id"])

    # ---- Viva ----
    op.create_table(
        "exam_vivas",
        *_tc(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("panel_members", sa.Text(), nullable=True),
        sa.Column("total_marks", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("passing_marks", sa.Integer(), nullable=False, server_default="20"),
    )
    op.create_index("ix_exam_vivas_course_id", "exam_vivas", ["course_id"])

    op.create_table(
        "exam_viva_results",
        *_tc(),
        sa.Column("viva_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("exam_vivas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("evaluated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("viva_id", "student_id", name="uq_viva_result_student"),
    )
    op.create_index("ix_exam_viva_results_viva_id", "exam_viva_results", ["viva_id"])
    op.create_index("ix_exam_viva_results_student_id", "exam_viva_results", ["student_id"])


def downgrade() -> None:
    op.drop_table("exam_viva_results")
    op.drop_table("exam_vivas")
    op.drop_table("exam_practical_results")
    op.drop_table("exam_practicals")
    op.drop_table("exam_answers")
    op.drop_table("exam_attempts")
    op.drop_table("exam_exam_questions")
    op.drop_table("exam_exams")
    op.drop_table("exam_questions_bank")
    for enum_type in (
        exam_attempt_status_enum, exam_status_enum, question_difficulty_enum, question_type_enum,
    ):
        enum_type.drop(op.get_bind(), checkfirst=True)
