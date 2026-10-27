"""our internships: offer response, verification, manual payment confirmation and LMS access per selected student

Revision ID: 0082
Revises: 0081
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)

_ENUMS = {
    "our_internship_offer_response": ("awaiting", "accepted", "declined"),
    "our_internship_verification_status": ("pending", "verified", "rejected"),
    "our_internship_payment_status": ("pending", "paid"),
    "our_internship_lms_status": ("not_granted", "granted", "revoked"),
}


def _enum_column(name: str, enum_name: str, default: str) -> sa.Column:
    return sa.Column(name, postgresql.ENUM(name=enum_name, create_type=False), server_default=default, nullable=False)


def upgrade() -> None:
    for enum_name, values in _ENUMS.items():
        postgresql.ENUM(*values, name=enum_name).create(op.get_bind(), checkfirst=True)

    op.add_column("our_internships", sa.Column("lms_course_id", _UUID, sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_our_internships_lms_course_id", "our_internships", ["lms_course_id"])

    table = "our_internship_selections"
    op.add_column(table, _enum_column("offer_response", "our_internship_offer_response", "awaiting"))
    op.add_column(table, sa.Column("offer_response_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, _enum_column("verification_status", "our_internship_verification_status", "pending"))
    op.add_column(table, sa.Column("verification_note", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("verified_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column(table, _enum_column("payment_status", "our_internship_payment_status", "pending"))
    op.add_column(table, sa.Column("payment_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column(table, sa.Column("payment_reference", sa.String(120), nullable=True))
    op.add_column(table, sa.Column("payment_received_on", sa.Date(), nullable=True))
    op.add_column(table, sa.Column("payment_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("payment_confirmed_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column(table, _enum_column("lms_status", "our_internship_lms_status", "not_granted"))
    op.add_column(table, sa.Column("lms_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column(table, sa.Column("lms_student_id", _UUID, sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True))
    op.add_column(table, sa.Column("lms_granted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("lms_granted_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    table = "our_internship_selections"
    for column in (
        "lms_granted_by_user_id",
        "lms_granted_at",
        "lms_student_id",
        "lms_user_id",
        "lms_status",
        "payment_confirmed_by_user_id",
        "payment_confirmed_at",
        "payment_received_on",
        "payment_reference",
        "payment_amount",
        "payment_status",
        "verified_by_user_id",
        "verified_at",
        "verification_note",
        "verification_status",
        "offer_response_at",
        "offer_response",
    ):
        op.drop_column(table, column)
    op.drop_index("ix_our_internships_lms_course_id", table_name="our_internships")
    op.drop_column("our_internships", "lms_course_id")
    for enum_name in _ENUMS:
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
