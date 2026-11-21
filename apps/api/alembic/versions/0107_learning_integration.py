"""Learning integration: cohort scoping for practicals, viva, discussions and assessments; real assessment questions; exam attendee -> selection

Revision ID: 0107
Revises: 0106
Create Date: 2026-11-18

Additive only. No existing row is deleted, moved or rewritten, except that the new nullable ``selection_id`` of exam attendees is filled
where (and only where) exactly one selection of the exam's internship matches the attendee's e-mail; everything else stays null and is
listed by ops/preflight/0107_learning_integration.sql.

- exam_practicals.internship_id, exam_vivas.internship_id, lms_discussion_threads.internship_id, lms_assessments.internship_id: null for
  every existing row, which keeps it course-wide exactly as it was.
- lms_assessment_questions: multiple-choice questions for an assessment. lms_assessments.show_result (true), lms_assessment_attempts.answers
  and total_marks: what a server-scored attempt needs. Existing attempts keep their score and have empty answers.
- course_resources: storage_key / original_filename / content_type / size_bytes / uploaded_by_user_id (all null for the existing link
  resources): what an uploaded file needs.
- workshop_exam_attendees.selection_id: the stable reference to the internship selection (null = not matched).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0107"
down_revision: Union[str, None] = "0106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCOPED = ("exam_practicals", "exam_vivas", "lms_discussion_threads", "lms_assessments")

BACKFILL_SQL = """
UPDATE workshop_exam_attendees a SET selection_id = m.selection_id
FROM (
    SELECT a2.id AS attendee_id, (array_agg(s.id::text))[1]::uuid AS selection_id
    FROM workshop_exam_attendees a2
    JOIN workshop_exams e ON e.id = a2.exam_id AND e.internship_id IS NOT NULL AND e.award IS NULL
    JOIN our_internship_selections s ON s.internship_id = e.internship_id
    JOIN institution_students p ON p.id = s.student_id AND lower(btrim(p.email)) = lower(btrim(a2.email))
    WHERE a2.certificate_only = false AND a2.selection_id IS NULL
    GROUP BY a2.id
    HAVING count(*) = 1
) m
WHERE a.id = m.attendee_id
"""


def upgrade() -> None:
    for table in SCOPED:
        op.add_column(table, sa.Column("internship_id", sa.UUID(), sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True))
        op.create_index(f"ix_{table}_internship_id", table, ["internship_id"])

    op.add_column("lms_assessments", sa.Column("show_result", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("lms_assessment_attempts", sa.Column("answers", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("lms_assessment_attempts", sa.Column("total_marks", sa.Integer(), nullable=True))
    op.create_table(
        "lms_assessment_questions",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", sa.UUID(), sa.ForeignKey("lms_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_indices", postgresql.JSONB(), nullable=False),
        sa.Column("allow_multiple", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marks", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lms_assessment_questions_assessment_id", "lms_assessment_questions", ["assessment_id"])

    op.add_column("course_resources", sa.Column("storage_key", sa.String(512), nullable=True))
    op.add_column("course_resources", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("course_resources", sa.Column("content_type", sa.String(150), nullable=True))
    op.add_column("course_resources", sa.Column("size_bytes", sa.Integer(), nullable=True))
    op.add_column("course_resources", sa.Column("uploaded_by_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    op.add_column(
        "workshop_exam_attendees",
        sa.Column("selection_id", sa.UUID(), sa.ForeignKey("our_internship_selections.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_workshop_exam_attendees_selection_id", "workshop_exam_attendees", ["selection_id"])
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    for column in ("uploaded_by_user_id", "size_bytes", "content_type", "original_filename", "storage_key"):
        op.drop_column("course_resources", column)
    op.drop_index("ix_workshop_exam_attendees_selection_id", table_name="workshop_exam_attendees")
    op.drop_column("workshop_exam_attendees", "selection_id")
    op.drop_index("ix_lms_assessment_questions_assessment_id", table_name="lms_assessment_questions")
    op.drop_table("lms_assessment_questions")
    op.drop_column("lms_assessment_attempts", "total_marks")
    op.drop_column("lms_assessment_attempts", "answers")
    op.drop_column("lms_assessments", "show_result")
    for table in reversed(SCOPED):
        op.drop_index(f"ix_{table}_internship_id", table_name=table)
        op.drop_column(table, "internship_id")
