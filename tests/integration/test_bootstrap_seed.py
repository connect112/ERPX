"""
The api container's bootstrap (entrypoint: `alembic upgrade head`, then `python -m scripts.seed`) on a brand-new
database, run exactly that way in fresh interpreters: it must create the System organization, the bootstrap
superadmin and its profile, and the Pentrix program, and a second run must change nothing. Uses its own throwaway
database (created and dropped here); skipped if the test database user may not create databases.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration

API_DIR = Path(__file__).resolve().parents[2] / "apps" / "api"
REPO_DIR = API_DIR.parents[1]


def _connect_args(url, database: str) -> dict:
    return {"host": url.host, "port": url.port or 5432, "user": url.username, "password": url.password, "database": database}


@pytest.fixture
async def fresh_database():
    url = make_url(os.environ["DATABASE_URL"])
    name = f"erpx_seed_{uuid.uuid4().hex[:10]}"
    admin = await asyncpg.connect(**_connect_args(url, url.database))
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
    except asyncpg.InsufficientPrivilegeError:
        await admin.close()
        pytest.skip("the test database user may not create databases")
    try:
        yield url, name
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


def _run(args: list[str], database_url: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PYTHONPATH": f"{REPO_DIR}{os.pathsep}{API_DIR}",
        "DATABASE_URL": database_url,
        "ENVIRONMENT": "test",
        "SEED_SUPERADMIN_EMAIL": "bootstrap-check@example.com",
        "SEED_SUPERADMIN_PASSWORD": f"Bs-{uuid.uuid4().hex}",
    }
    return subprocess.run([sys.executable, *args], cwd=API_DIR, env=env, capture_output=True, text=True, timeout=600)


async def test_the_standalone_bootstrap_seed_completes_on_a_fresh_database_and_is_idempotent(fresh_database):
    url, name = fresh_database
    database_url = url.set(database=name).render_as_string(hide_password=False)
    migrated = _run(["-m", "alembic", "upgrade", "head"], database_url)
    assert migrated.returncode == 0, migrated.stderr[-3000:]

    first = _run(["-m", "scripts.seed"], database_url)
    assert first.returncode == 0, first.stderr[-3000:] + first.stdout[-3000:]
    assert "NoReferencedTableError" not in first.stdout + first.stderr
    second = _run(["-m", "scripts.seed"], database_url)
    assert second.returncode == 0, second.stderr[-3000:] + second.stdout[-3000:]
    assert "seed_superadmin_already_exists" in second.stdout + second.stderr

    db = await asyncpg.connect(**_connect_args(url, name))
    try:
        slugs = {r["slug"] for r in await db.fetch("SELECT slug FROM organizations")}
        superadmins = await db.fetchval("SELECT count(*) FROM users WHERE is_superuser AND email = 'bootstrap-check@example.com'")
        profiles = await db.fetchval("SELECT count(*) FROM user_profiles")
        organizations = await db.fetchval("SELECT count(*) FROM organizations")
    finally:
        await db.close()
    assert {"erpx-system", "gir-pentrix-program"} <= slugs
    assert (superadmins, profiles, organizations) == (1, 1, 2)  # the second run added nothing
