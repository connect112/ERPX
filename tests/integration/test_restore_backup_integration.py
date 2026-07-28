"""
Integration tests for apps/api/scripts/restore_backup.py's real, destructive
paths — actual Postgres connections, actual `pg_dump`/`psql` subprocesses,
actual wipe-and-restore.

Deliberately never touches the shared `erpx_test` database the rest of the
suite depends on: every test here creates its own throwaway database
(`erpx_restore_test_<uuid>`), exercises the restore script against it, and
drops it in teardown — regardless of test outcome.
"""

import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest

from scripts.restore_backup import (
    ExitCode,
    RestoreError,
    _async_main,
    build_arg_parser,
    check_target_preconditions,
    wipe_target_schema,
)

pytestmark = pytest.mark.integration


async def _run(argv: list[str]) -> ExitCode:
    """`main()` (the real CLI entrypoint) wraps this in `asyncio.run()`,
    which can't nest inside pytest-asyncio's already-running loop — tests
    call the async core directly instead. `main()` itself is covered by
    the unit tests' argument-parsing coverage plus this module's own
    exercise of `_async_main`, which is the entire body of what `main()`
    delegates to."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return await _async_main(args)


def _maintenance_url() -> str:
    """Connects to the same Postgres server the rest of the suite already
    uses (DATABASE_URL), but to a fixed maintenance database, so we can
    CREATE/DROP a throwaway database around each test."""
    base = os.environ.get("DATABASE_URL", "postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx_test")
    parsed = urlparse(base.replace("+asyncpg", ""))
    return f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres"


def _throwaway_url(dbname: str) -> str:
    base = os.environ.get("DATABASE_URL", "postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx_test")
    parsed = urlparse(base.replace("+asyncpg", ""))
    return f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/{dbname}"


@pytest.fixture
async def throwaway_db():
    dbname = f"erpx_restore_test_{uuid.uuid4().hex[:12]}"
    admin_conn = await asyncpg.connect(dsn=_maintenance_url())
    try:
        await admin_conn.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await admin_conn.close()

    url = _throwaway_url(dbname)
    try:
        yield url
    finally:
        admin_conn = await asyncpg.connect(dsn=_maintenance_url())
        try:
            await admin_conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
                dbname,
            )
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        finally:
            await admin_conn.close()


async def _seed_sample_data(url: str) -> None:
    conn = await asyncpg.connect(dsn=url)
    try:
        await conn.execute("CREATE TABLE widgets (id serial PRIMARY KEY, name text NOT NULL)")
        await conn.execute("INSERT INTO widgets (name) VALUES ('alpha'), ('beta'), ('gamma')")
    finally:
        await conn.close()


async def _dump_database(url: str, dest_path: str) -> None:
    import subprocess

    from app.core.config import settings

    parsed = urlparse(url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    result = subprocess.run(
        [
            settings.PG_DUMP_PATH,
            "-h", parsed.hostname,
            "-p", str(parsed.port or 5432),
            "-U", parsed.username,
            "-d", parsed.path.lstrip("/"),
            "-f", dest_path,
            "--no-owner",
            "--no-privileges",
        ],
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")


class TestCheckTargetPreconditions:
    async def test_empty_database_has_no_tables(self, throwaway_db):
        has_tables = await check_target_preconditions(throwaway_db, allow_wipe=False)
        assert has_tables is False

    async def test_refuses_non_empty_database_without_wipe_flag(self, throwaway_db):
        await _seed_sample_data(throwaway_db)
        with pytest.raises(RestoreError) as exc_info:
            await check_target_preconditions(throwaway_db, allow_wipe=False)
        assert exc_info.value.exit_code == ExitCode.TARGET_SAFETY_CHECK_FAILED
        assert "already has" in str(exc_info.value)

    async def test_allows_non_empty_database_with_wipe_flag(self, throwaway_db):
        await _seed_sample_data(throwaway_db)
        has_tables = await check_target_preconditions(throwaway_db, allow_wipe=True)
        assert has_tables is True

    async def test_refuses_when_another_connection_is_active(self, throwaway_db):
        other_conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            with pytest.raises(RestoreError) as exc_info:
                await check_target_preconditions(throwaway_db, allow_wipe=False)
            assert exc_info.value.exit_code == ExitCode.TARGET_SAFETY_CHECK_FAILED
            assert "active connection" in str(exc_info.value)
        finally:
            await other_conn.close()

    async def test_unreachable_database_raises(self):
        with pytest.raises(RestoreError) as exc_info:
            await check_target_preconditions(
                "postgresql://erpx:erpx_secret@127.0.0.1:59999/does_not_exist", allow_wipe=False
            )
        assert exc_info.value.exit_code == ExitCode.TARGET_SAFETY_CHECK_FAILED


class TestWipeTargetSchema:
    async def test_wipe_removes_all_tables(self, throwaway_db):
        await _seed_sample_data(throwaway_db)
        await wipe_target_schema(throwaway_db)
        has_tables = await check_target_preconditions(throwaway_db, allow_wipe=False)
        assert has_tables is False


class TestFullRestoreFlow:
    async def test_dry_run_makes_no_changes(self, throwaway_db, tmp_path):
        await _seed_sample_data(throwaway_db)
        dump_path = tmp_path / "backup.sql"
        await _dump_database(throwaway_db, str(dump_path))

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--database-url", throwaway_db,
                "--dry-run",
                "--force",
                "--yes-wipe-existing-schema",
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.SUCCESS

        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            count = await conn.fetchval("SELECT count(*) FROM widgets")
            assert count == 3, "dry-run must not touch the target database"
        finally:
            await conn.close()

    async def test_restore_into_empty_database_recreates_data(self, throwaway_db, tmp_path):
        # Build the dump from a *separate* throwaway source so the target
        # for this test genuinely starts empty (closer to the real DR
        # scenario: restoring into a fresh database).
        source_dbname = f"erpx_restore_test_src_{uuid.uuid4().hex[:12]}"
        admin_conn = await asyncpg.connect(dsn=_maintenance_url())
        await admin_conn.execute(f'CREATE DATABASE "{source_dbname}"')
        await admin_conn.close()
        source_url = _throwaway_url(source_dbname)
        try:
            await _seed_sample_data(source_url)
            dump_path = tmp_path / "backup.sql"
            await _dump_database(source_url, str(dump_path))
        finally:
            admin_conn = await asyncpg.connect(dsn=_maintenance_url())
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{source_dbname}"')
            await admin_conn.close()

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--database-url", throwaway_db,
                "--force",
                "--skip-safety-backup",
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.SUCCESS

        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            names = await conn.fetch("SELECT name FROM widgets ORDER BY name")
            assert [r["name"] for r in names] == ["alpha", "beta", "gamma"]
        finally:
            await conn.close()

        assert (tmp_path / "audit.log").exists()
        audit_content = (tmp_path / "audit.log").read_text()
        assert '"status": "succeeded"' in audit_content

    async def test_refuses_non_empty_target_without_wipe_flag(self, throwaway_db, tmp_path):
        await _seed_sample_data(throwaway_db)
        dump_path = tmp_path / "backup.sql"
        await _dump_database(throwaway_db, str(dump_path))

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--database-url", throwaway_db,
                "--force",
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.TARGET_SAFETY_CHECK_FAILED

    async def test_wipe_and_restore_over_existing_data(self, throwaway_db, tmp_path):
        await _seed_sample_data(throwaway_db)
        dump_path = tmp_path / "backup.sql"
        await _dump_database(throwaway_db, str(dump_path))

        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            await conn.execute("INSERT INTO widgets (name) VALUES ('should-be-wiped-away')")
        finally:
            await conn.close()

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--database-url", throwaway_db,
                "--force",
                "--skip-safety-backup",
                "--yes-wipe-existing-schema",
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.SUCCESS

        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            names = {r["name"] for r in await conn.fetch("SELECT name FROM widgets")}
        finally:
            await conn.close()
        assert names == {"alpha", "beta", "gamma"}
        assert "should-be-wiped-away" not in names

    async def test_sha256_mismatch_is_rejected(self, throwaway_db, tmp_path):
        await _seed_sample_data(throwaway_db)
        dump_path = tmp_path / "backup.sql"
        await _dump_database(throwaway_db, str(dump_path))

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--expected-sha256", "0" * 64,
                "--database-url", throwaway_db,
                "--force",
                "--yes-wipe-existing-schema",
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.BACKUP_NOT_FOUND_OR_INVALID

    async def test_confirmation_declined_without_force(self, throwaway_db, tmp_path, monkeypatch):
        await _seed_sample_data(throwaway_db)
        dump_path = tmp_path / "backup.sql"
        await _dump_database(throwaway_db, str(dump_path))
        await wipe_target_schema(throwaway_db)

        monkeypatch.setattr("builtins.input", lambda _: "wrong-answer")

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--database-url", throwaway_db,
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.CONFIRMATION_DECLINED

        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            count = await conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
            assert count == 0, "a declined confirmation must not have restored anything"
        finally:
            await conn.close()

    async def test_restore_attempt_recorded_when_table_present(self, throwaway_db, tmp_path):
        """restore_attempts (apps/api/alembic/versions/0037_*.py) only gets
        a row when the target already has that table post-restore — here we
        create it manually to simulate an already-migrated target."""
        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            await conn.execute(
                "CREATE TYPE restore_attempt_status AS ENUM ('dry_run', 'succeeded', 'failed', 'aborted')"
            )
            await conn.execute(
                """
                CREATE TABLE restore_attempts (
                    id uuid PRIMARY KEY,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    backup_job_id uuid,
                    initiated_by varchar(255) NOT NULL,
                    target_database varchar(255) NOT NULL,
                    status restore_attempt_status NOT NULL,
                    safety_backup_path varchar(1024),
                    error_message text,
                    started_at timestamptz NOT NULL,
                    completed_at timestamptz
                )
                """
            )
            await conn.execute("CREATE TABLE widgets (id serial PRIMARY KEY, name text NOT NULL)")
            await conn.execute("INSERT INTO widgets (name) VALUES ('alpha')")
        finally:
            await conn.close()

        dump_path = tmp_path / "backup.sql"
        await _dump_database(throwaway_db, str(dump_path))

        exit_code = await _run(
            [
                "--backup-file", str(dump_path),
                "--database-url", throwaway_db,
                "--force",
                "--skip-safety-backup",
                "--yes-wipe-existing-schema",
                "--initiated-by", "pytest-integration",
                "--audit-log-path", str(tmp_path / "audit.log"),
            ]
        )
        assert exit_code == ExitCode.SUCCESS

        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            row = await conn.fetchrow(
                "SELECT initiated_by, status FROM restore_attempts ORDER BY created_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        assert row is not None
        assert row["initiated_by"] == "pytest-integration"
        assert row["status"] == "succeeded"
