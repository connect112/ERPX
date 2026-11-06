"""
The migrations must form one line. Two branches that each add a revision on the same parent are fine on their own but leave two
heads once both are merged, and `alembic upgrade head` then refuses to run. If this fails after another branch was merged, set the
newer migration's down_revision to the other branch's revision.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

pytestmark = pytest.mark.unit

API = Path(__file__).resolve().parents[2] / "apps" / "api"


def test_there_is_exactly_one_alembic_head():
    cfg = Config(str(API / "alembic.ini"))
    cfg.set_main_option("script_location", str(API / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"several migration heads: {heads}"
