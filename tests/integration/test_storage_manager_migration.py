"""Migration 0096 (Storage Manager) upgrade, rollback and re-upgrade on a throwaway database.

Production applies migrations when `erpx_api` starts, and an image older than this one cannot start while the database is at
0096. The rollback path is therefore `alembic downgrade 0095` first, so it has to be proven, with rows present, before deploy.
The test builds its own scratch database, so the shared test database is never touched.
"""

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings

REPO = Path(__file__).resolve().parents[2]
API = REPO / "apps" / "api"
NEW_TABLES = {"storage_trash", "storage_deletion_log"}

pytestmark = pytest.mark.skipif(
    not (API / "alembic" / "versions" / "0096_storage_manager.py").exists(), reason="migration 0096 is not on this branch"
)


def _connect(database: str):
    url = make_url(settings.DATABASE_URL)
    conn = psycopg2.connect(host=url.host, port=url.port or 5432, user=url.username, password=url.password, dbname=database)
    conn.autocommit = True
    return conn


def _alembic(database: str, *args: str) -> str:
    url = make_url(settings.DATABASE_URL).set(database=database).render_as_string(hide_password=False)
    env = dict(os.environ, DATABASE_URL=url, PYTHONPATH=str(REPO))
    result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=API, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-500:] + result.stderr[-800:]
    return result.stdout + result.stderr


def _shape(conn) -> dict:
    """Tables, columns, indexes and constraints as the catalog reports them (no pg_dump needed)."""
    with conn.cursor() as cur:
        cur.execute("select table_name, column_name, data_type, is_nullable, column_default from information_schema.columns "
                    "where table_schema = 'public' order by 1, ordinal_position")
        columns = cur.fetchall()
        cur.execute("select indexname, indexdef from pg_indexes where schemaname = 'public' order by 1")
        indexes = cur.fetchall()
        cur.execute("select conrelid::regclass::text, conname, pg_get_constraintdef(oid) from pg_constraint "
                    "where connamespace = 'public'::regnamespace order by 1, 2")
        constraints = cur.fetchall()
    return {"columns": columns, "indexes": indexes, "constraints": constraints}


@pytest.fixture
def scratch_database():
    name = f"erpx_mig0096_{uuid.uuid4().hex[:8]}"
    admin = _connect("postgres")
    with admin.cursor() as cur:
        cur.execute(f'create database "{name}"')
    try:
        yield name
    finally:
        with admin.cursor() as cur:
            cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s", (name,))
            cur.execute(f'drop database if exists "{name}"')
        admin.close()


def test_0096_upgrades_rolls_back_exactly_and_upgrades_again(scratch_database):
    _alembic(scratch_database, "upgrade", "0095")
    conn = _connect(scratch_database)
    before = _shape(conn)
    assert not NEW_TABLES & {c[0] for c in before["columns"]}

    log = _alembic(scratch_database, "upgrade", "head")
    assert re.findall(r"Running upgrade (\w+) -> (\w+)", log) == [("0095", "0096")]
    added = {c[0] for c in _shape(conn)["columns"]} - {c[0] for c in before["columns"]}
    assert added == NEW_TABLES

    # rows in both tables, tied to an organization, so a rollback is tested against data and not an empty schema
    with conn.cursor() as cur:
        cur.execute("insert into organizations (id, name, slug, created_at, updated_at) "
                    "values (gen_random_uuid(), 'Rollback Org', 'rollback-org', now(), now()) returning id")
        org = cur.fetchone()[0]
        cur.execute("insert into storage_trash (id, organization_id, source, original_key, trash_key, filename, size_bytes, "
                    "evidence, reason, deleted_at, created_at, updated_at) values (gen_random_uuid(), %s, 'orphans', 'a/b.txt', "
                    "'.trash/x/a/b.txt', 'b.txt', 10, '[]', 'test', now(), now(), now())", (org,))
        cur.execute("insert into storage_deletion_log (id, organization_id, action, source, object_key, evidence, created_at, "
                    "updated_at) values (gen_random_uuid(), %s, 'trash', 'orphans', 'a/b.txt', '[]', now(), now())", (org,))

    log = _alembic(scratch_database, "downgrade", "0095")
    assert re.findall(r"Running downgrade (\w+) -> (\w+)", log) == [("0096", "0095")]
    assert _shape(conn) == before, "rolling back 0096 must restore the 0095 schema exactly"
    with conn.cursor() as cur:
        cur.execute("select version_num from alembic_version")
        assert cur.fetchone()[0] == "0095"
        cur.execute("select count(*) from organizations where slug = 'rollback-org'")
        assert cur.fetchone()[0] == 1, "only the two new tables may be dropped; business rows stay"

    _alembic(scratch_database, "upgrade", "head")
    with conn.cursor() as cur:
        cur.execute("select version_num from alembic_version")
        assert cur.fetchone()[0] == "0096"
    conn.close()
