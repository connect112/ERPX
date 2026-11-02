"""
The standalone bootstrap seed (apps/api/scripts/seed.py, run by the api container's entrypoint before the app starts)
must register every table its inserts depend on. Inside the running app, app.main imports every model; the seed runs
without it, so a missing import only shows up on a fresh database as NoReferencedTableError at the first flush (e.g.
Organization's FKs to accounting_accounts and payroll_salary_components). This imports the seed alone in a fresh
interpreter, as the entrypoint does, and resolves every foreign key of every table the seed writes. No database.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

API_DIR = Path(__file__).resolve().parents[2] / "apps" / "api"
REPO_DIR = API_DIR.parents[1]

# every table scripts.seed inserts into or updates
SEEDED_TABLES = ("organizations", "users", "user_profiles", "roles", "permissions", "role_permissions", "user_roles", "courses")

PROBE = f"""
import json
import scripts.seed  # noqa: F401  (only what the seed itself imports)
from app.db.session import Base
from sqlalchemy.exc import NoReferencedTableError

missing = []
for name in {SEEDED_TABLES!r}:
    table = Base.metadata.tables.get(name)
    if table is None:
        missing.append(f"{{name}} (table not registered)")
        continue
    for fk in table.foreign_keys:
        try:
            fk.column
        except NoReferencedTableError:
            missing.append(f"{{fk.parent}} -> {{fk.target_fullname}}")
print(json.dumps(missing))
"""


def test_the_standalone_seed_registers_every_table_its_inserts_reference():
    env = {**os.environ, "PYTHONPATH": f"{REPO_DIR}{os.pathsep}{API_DIR}", "ENVIRONMENT": "test",
           "JWT_SECRET_KEY": "test_secret_key_at_least_32_characters_long"}  # fmt: skip
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=API_DIR, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    missing = json.loads(result.stdout.strip().splitlines()[-1])
    assert missing == [], f"scripts/seed.py must import the models these foreign keys point to: {missing}"
