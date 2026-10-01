"""add trainer_joined_at to live_classes

Revision ID: 0047
Revises: 0046
Create Date: 2026-10-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set the first time the trainer mints their own join-token for this
    # class (see get_live_class_join_token_as_trainer / mark_trainer_joined
    # in modules/live_classes). Students can't get their own join-token
    # until this is set, so they never land in an empty room before the
    # trainer has actually shown up -- the trainer "opening the door" for
    # them, regardless of how early the class's status flips to LIVE.
    op.add_column(
        "live_classes", sa.Column("trainer_joined_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("live_classes", "trainer_joined_at")
