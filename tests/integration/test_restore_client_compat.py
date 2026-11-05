"""Restore compatibility and safety: PostgreSQL client tools 16, 17 and 18 against the test PostgreSQL server (16 in CI).

What is promised, and tested here:
  * a compressed archive restores when the restore client is at least as new as the pg_dump that made it (16/17/18 combinations),
  * an archive the client cannot read is refused BEFORE the target is touched (even when a schema wipe was requested),
  * a restore that fails part-way, on either side of the pipe, is rolled back and the original data is still there,
  * a data row that happens to contain the text of a version-skew header line is never altered,
  * ownership and privileges are not restored (--no-owner --no-privileges), exactly as before,
  * a large dump is streamed with bounded memory.
Not promised: universal cross-version support. Combinations that cannot work are refused; others are logged as untested.

Client tools are found in ERPX_PG_CLIENT_DIRS ("16=dir;17=dir;18=dir") or in /usr/lib/postgresql/<n>/bin. A missing client makes
the dependent tests SKIP locally, and FAIL when ERPX_REQUIRE_PG_CLIENTS=1 (which CI sets), so coverage cannot silently vanish.
"""

import os
import threading
import time
import uuid
from pathlib import Path

import asyncpg
import pytest

from app.core.config import settings
from scripts.restore_backup import ExitCode, RestoreError, build_restore_plan
from scripts.restore_stream import ArchiveInfo
from tests.integration.test_restore_backup_integration import (  # noqa: F401  (fixture + helpers shared with the existing module)
    _dump_database,
    _maintenance_url,
    _run,
    _seed_sample_data,
    _throwaway_url,
    throwaway_db,
)

pytestmark = pytest.mark.integration

VERSIONS = (16, 17, 18)


def _client_dirs() -> dict[int, str]:
    found: dict[int, str] = {}
    for part in filter(None, os.environ.get("ERPX_PG_CLIENT_DIRS", "").split(";")):
        version, directory = part.split("=", 1)
        found[int(version)] = directory.strip()
    for version in VERSIONS:
        default = f"/usr/lib/postgresql/{version}/bin"
        if version not in found and os.path.isdir(default):
            found[version] = default
    return found


def _tool(directory: str, name: str) -> str:
    for suffix in ("", ".cmd", ".exe"):
        candidate = Path(directory) / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(f"{name} not found in {directory}")


def _need(*versions: int) -> dict[int, str]:
    dirs = _client_dirs()
    missing = [v for v in versions if v not in dirs]
    if missing:
        message = f"PostgreSQL client tools {missing} not found (set ERPX_PG_CLIENT_DIRS or install them under /usr/lib/postgresql)"
        if os.environ.get("ERPX_REQUIRE_PG_CLIENTS") == "1":
            pytest.fail(message)
        pytest.skip(message)
    return dirs


def _use_clients(monkeypatch, dirs: dict[int, str], *, dump: int, restore: int, psql: int | None = None) -> None:
    monkeypatch.setattr(settings, "PG_DUMP_PATH", _tool(dirs[dump], "pg_dump"))
    monkeypatch.setattr(settings, "PG_RESTORE_PATH", _tool(dirs[restore], "pg_restore"))
    monkeypatch.setattr(settings, "PSQL_PATH", _tool(dirs[psql or restore], "psql"))


async def _admin(sql: str) -> None:
    conn = await asyncpg.connect(dsn=_maintenance_url())
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _source_db(seed) -> str:
    """A throwaway database filled by ``seed(conn)``; the caller drops it with _drop_db."""
    name = f"erpx_restore_src_{uuid.uuid4().hex[:12]}"
    await _admin(f'CREATE DATABASE "{name}"')
    url = _throwaway_url(name)
    conn = await asyncpg.connect(dsn=url)
    try:
        await seed(conn)
    finally:
        await conn.close()
    return url


async def _drop_db(url: str) -> None:
    name = url.rsplit("/", 1)[1]
    await _admin(f'DROP DATABASE IF EXISTS "{name}"')


async def _fetch(url: str, sql: str):
    conn = await asyncpg.connect(dsn=url)
    try:
        return await conn.fetch(sql)
    finally:
        await conn.close()


def _args(dump_path, target, tmp_path, *extra: str) -> list[str]:
    return ["--backup-file", str(dump_path), "--database-url", target, "--force", "--skip-safety-backup",
            "--audit-log-path", str(tmp_path / "audit.log"), *extra]


async def _make_archive(tmp_path, seed, name: str = "backup.dump", compressed: bool = True) -> Path:
    src = await _source_db(seed)
    try:
        path = tmp_path / name
        await _dump_database(src, str(path), compressed=compressed)
    finally:
        await _drop_db(src)
    return path


async def _seed_widgets(conn) -> None:
    await conn.execute("CREATE TABLE widgets (id serial PRIMARY KEY, name text NOT NULL)")
    await conn.execute("INSERT INTO widgets (name) VALUES ('alpha'), ('beta'), ('gamma')")


async def _seed_original(url: str) -> None:
    conn = await asyncpg.connect(dsn=url)
    try:
        await conn.execute("CREATE TABLE widgets (id serial PRIMARY KEY, name text NOT NULL)")
        await conn.execute("INSERT INTO widgets (name) VALUES ('original-1'), ('original-2')")
    finally:
        await conn.close()


async def _names(url: str) -> list[str]:
    return sorted(r["name"] for r in await _fetch(url, "SELECT name FROM widgets"))


@pytest.mark.parametrize("dump_v", VERSIONS)
@pytest.mark.parametrize("restore_v", VERSIONS)
class TestClientMatrix:
    async def test_restore_works_when_the_restore_client_can_read_the_archive_and_is_refused_safely_when_not(
        self, dump_v, restore_v, throwaway_db, tmp_path, monkeypatch
    ):
        dirs = _need(dump_v, restore_v)
        _use_clients(monkeypatch, dirs, dump=dump_v, restore=restore_v)
        archive = await _make_archive(tmp_path, _seed_widgets)
        await _seed_original(throwaway_db)

        exit_code = await _run(_args(archive, throwaway_db, tmp_path, "--yes-wipe-existing-schema"))

        if restore_v >= dump_v:
            assert exit_code == ExitCode.SUCCESS
            assert await _names(throwaway_db) == ["alpha", "beta", "gamma"]
        else:
            # an older pg_restore cannot read a newer archive: refused up front, nothing wiped
            assert exit_code == ExitCode.PREFLIGHT_FAILED
            assert await _names(throwaway_db) == ["original-1", "original-2"]


class TestSafetyAndData:
    async def test_ownership_and_privileges_are_not_restored(self, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(16, 17)
        _use_clients(monkeypatch, dirs, dump=16, restore=17)
        role = f"restore_test_owner_{uuid.uuid4().hex[:8]}"
        await _admin(f'CREATE ROLE "{role}" NOLOGIN')
        src = None
        try:
            async def seed(conn):
                await _seed_widgets(conn)
                await conn.execute(f'ALTER TABLE widgets OWNER TO "{role}"')
                await conn.execute("GRANT SELECT ON widgets TO PUBLIC")

            src = await _source_db(seed)
            archive = tmp_path / "owned.dump"
            await _dump_database(src, str(archive), compressed=True)
            exit_code = await _run(_args(archive, throwaway_db, tmp_path))
            assert exit_code == ExitCode.SUCCESS
            row = (await _fetch(throwaway_db, "SELECT tableowner, (SELECT relacl IS NULL FROM pg_class WHERE relname = 'widgets') AS no_acl "
                                              "FROM pg_tables WHERE tablename = 'widgets'"))[0]
            assert row["tableowner"] != role and row["no_acl"] is True
        finally:
            if src:
                await _drop_db(src)
            await _admin(f'DROP ROLE IF EXISTS "{role}"')

    @pytest.mark.parametrize("compressed", [True, False])
    async def test_a_data_row_equal_to_the_version_skew_header_line_survives(self, compressed, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(16, 18)
        _use_clients(monkeypatch, dirs, dump=18 if not compressed else 16, restore=18)

        async def seed(conn):
            await conn.execute("CREATE TABLE notes (body text, n int)")
            await conn.execute("INSERT INTO notes VALUES ('SET transaction_timeout = 0;', 7), ('plain', 8)")

        archive = await _make_archive(tmp_path, seed, "notes.dump" if compressed else "notes.sql", compressed=compressed)
        exit_code = await _run(_args(archive, throwaway_db, tmp_path))
        assert exit_code == ExitCode.SUCCESS
        rows = await _fetch(throwaway_db, "SELECT body, n FROM notes ORDER BY n")
        assert [(r["body"], r["n"]) for r in rows] == [("SET transaction_timeout = 0;", 7), ("plain", 8)]

    async def test_a_plain_dump_from_a_newer_client_restores_into_the_older_server(self, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(18)
        _use_clients(monkeypatch, dirs, dump=18, restore=18)
        archive = await _make_archive(tmp_path, _seed_widgets, "plain18.sql", compressed=False)
        assert b"SET transaction_timeout" in archive.read_bytes()[:2000]  # the header that used to break the restore
        assert await _run(_args(archive, throwaway_db, tmp_path)) == ExitCode.SUCCESS
        assert await _names(throwaway_db) == ["alpha", "beta", "gamma"]

    async def test_a_failure_inside_the_sql_is_rolled_back_and_nothing_partial_is_left(self, throwaway_db, tmp_path, monkeypatch):
        """psql fails part-way (a type with the name of a later table already exists): the tables created before the failure must go."""
        dirs = _need(16)
        _use_clients(monkeypatch, dirs, dump=16, restore=16)

        async def seed(conn):
            for name in ("aa", "bb", "zz_last"):
                await conn.execute(f"CREATE TABLE {name} (id int)")

        archive = await _make_archive(tmp_path, seed)
        conn = await asyncpg.connect(dsn=throwaway_db)
        try:
            await conn.execute("CREATE TYPE zz_last AS ENUM ('x')")
        finally:
            await conn.close()

        exit_code = await _run(_args(archive, throwaway_db, tmp_path))

        assert exit_code == ExitCode.RESTORE_FAILED
        tables = await _fetch(throwaway_db, "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        assert tables == [], "aa and bb were created before the failure and must have been rolled back"
        assert len(await _fetch(throwaway_db, "SELECT 1 FROM pg_type WHERE typname = 'zz_last'")) == 1
        assert '"restore_rolled_back": true' in (tmp_path / "audit.log").read_text()

    async def test_dry_run_runs_the_preflight_and_changes_nothing(self, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(16, 17)
        _use_clients(monkeypatch, dirs, dump=17, restore=17)
        archive = await _make_archive(tmp_path, _seed_widgets)
        await _seed_original(throwaway_db)

        assert await _run(_args(archive, throwaway_db, tmp_path, "--dry-run", "--yes-wipe-existing-schema")) == ExitCode.SUCCESS
        assert await _names(throwaway_db) == ["original-1", "original-2"]

        _use_clients(monkeypatch, dirs, dump=17, restore=16)  # now the restore client is older than the archive
        assert await _run(_args(archive, throwaway_db, tmp_path, "--dry-run", "--yes-wipe-existing-schema")) == ExitCode.PREFLIGHT_FAILED
        assert await _names(throwaway_db) == ["original-1", "original-2"]

    async def test_pg_restore_and_psql_from_different_releases_are_refused(self, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(16, 17)
        _use_clients(monkeypatch, dirs, dump=16, restore=17, psql=16)
        archive = await _make_archive(tmp_path, _seed_widgets)
        await _seed_original(throwaway_db)
        assert await _run(_args(archive, throwaway_db, tmp_path, "--yes-wipe-existing-schema")) == ExitCode.PREFLIGHT_FAILED
        assert await _names(throwaway_db) == ["original-1", "original-2"]

    async def test_an_archive_from_a_newer_server_than_the_target_is_refused(self, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(16)
        _use_clients(monkeypatch, dirs, dump=16, restore=16)
        archive = await _make_archive(tmp_path, _seed_widgets)
        newer = ArchiveInfo(dumped_by=(16, 0), dumped_from=(99, 0), toc_entries=1)
        monkeypatch.setattr("scripts.restore_backup.inspect_archive", lambda *a, **k: newer)
        with pytest.raises(RestoreError) as exc_info:
            await build_restore_plan(throwaway_db, str(archive), "custom", False)
        assert exc_info.value.exit_code == ExitCode.PREFLIGHT_FAILED
        assert "newer server" in str(exc_info.value)

    async def test_an_archive_made_by_a_newer_pg_dump_than_the_restore_client_is_refused(self, throwaway_db, tmp_path, monkeypatch):
        dirs = _need(16)
        _use_clients(monkeypatch, dirs, dump=16, restore=16)
        archive = await _make_archive(tmp_path, _seed_widgets)
        newer = ArchiveInfo(dumped_by=(99, 0), dumped_from=(16, 0), toc_entries=1)
        monkeypatch.setattr("scripts.restore_backup.inspect_archive", lambda *a, **k: newer)
        with pytest.raises(RestoreError) as exc_info:
            await build_restore_plan(throwaway_db, str(archive), "custom", False)
        assert exc_info.value.exit_code == ExitCode.PREFLIGHT_FAILED


class TestLargeDumpIsStreamed:
    async def test_a_large_plain_dump_restores_with_bounded_memory(self, throwaway_db, tmp_path, monkeypatch):
        psutil = pytest.importorskip("psutil")
        dirs = _need(16)
        _use_clients(monkeypatch, dirs, dump=16, restore=16)
        rows = 1_000_000
        big = tmp_path / "big.sql"
        with open(big, "wb") as f:
            f.write(b"--\n-- PostgreSQL database dump\n--\n\nSET statement_timeout = 0;\nSET transaction_timeout = 0;\n\n"
                    b"CREATE TABLE public.big (id integer, payload text);\n\nCOPY public.big (id, payload) FROM stdin;\n")
            line = "x" * 100
            for start in range(0, rows, 50_000):
                f.write("".join(f"{i}\t{line}\n" for i in range(start, start + 50_000)).encode())
            f.write(b"\\.\n")
        assert big.stat().st_size > 100_000_000

        process = psutil.Process()
        baseline = process.memory_info().rss
        peak = [baseline]
        stop = threading.Event()

        def sample():
            while not stop.wait(0.05):
                peak[0] = max(peak[0], process.memory_info().rss)

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        try:
            exit_code = await _run(_args(big, throwaway_db, tmp_path))
        finally:
            stop.set()
            sampler.join(timeout=2)

        assert exit_code == ExitCode.SUCCESS
        assert (await _fetch(throwaway_db, "SELECT count(*) AS n FROM big"))[0]["n"] == rows
        growth_mb = (peak[0] - baseline) / 1024 / 1024
        print(f"[restore memory] {big.stat().st_size // 1_000_000} MB dump, {rows} rows: peak growth of the restoring process {growth_mb:.1f} MB")
        assert growth_mb < 60, f"restoring a {big.stat().st_size // 1_000_000} MB dump grew this process by {growth_mb:.0f} MB"
