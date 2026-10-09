"""placements job feed: India filter, company career boards, background refresh marker

Revision ID: 0065
Revises: 0064
Create Date: 2026-10-09

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BOARDS = {
    "greenhouse": [
        "okta", "datadog", "elastic", "mongodb", "databricks", "twilio", "gitlab", "rubrik", "zscaler", "newrelic",
        "sumologic", "abnormalsecurity", "netskope", "guidepoint", "jfrog", "cloudflare", "stripe", "payoneer",
        "fivetran", "toast", "roblox", "singlestore", "yugabyte", "thoughtworks", "mixpanel", "airbnb", "coinbase",
    ],
    "lever": ["cred", "meesho", "paytm", "nium", "zeta", "pocketfm"],
}


def upgrade() -> None:
    op.add_column("placement_job_feed_settings", sa.Column("india_only", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("placement_job_feed_settings", sa.Column("boards", postgresql.JSONB(), nullable=True))
    op.add_column("placement_job_feed_settings", sa.Column("refresh_started_at", sa.DateTime(timezone=True), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE placement_job_feed_settings SET boards = CAST(:boards AS jsonb)"), {"boards": json.dumps(_BOARDS)})
    op.alter_column("placement_job_feed_settings", "boards", nullable=False)
    # The first version kept freshers only and found far too few jobs: keep every wanted role and let students filter.
    connection.execute(sa.text("UPDATE placement_job_feed_settings SET fresher_only = false"))
    connection.execute(sa.text("UPDATE placement_job_feed_settings SET source_state = '{}'::jsonb, sources = sources || '{\"greenhouse\": true, \"lever\": true}'::jsonb"))
    # The list of wanted words is replaced by the wider default (nobody has edited it yet).
    connection.execute(sa.text("UPDATE placement_job_feed_settings SET keywords = CAST(:kw AS jsonb)"), {"kw": json.dumps(["__reset__"])})


def downgrade() -> None:
    op.drop_column("placement_job_feed_settings", "refresh_started_at")
    op.drop_column("placement_job_feed_settings", "boards")
    op.drop_column("placement_job_feed_settings", "india_only")
