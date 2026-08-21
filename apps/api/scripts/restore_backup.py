"""
Standalone CLI restore tool for `modules/backups`' pg_dump backups.

Implements the design proposal in docs/project-hardening-audit.md (finding
#2, "Backup & Restore"): deliberately NOT a self-service API endpoint. The
API process that would serve a `POST /backups/{id}/restore` request is
itself backed by the same database being overwritten — restoring out from
under a live connection pool is a well-known way to corrupt in-flight
transactions. Real restores happen with the API stopped, run by an
operator with direct database/object-storage credentials, via this script.

Run from `apps/api/`:

    python -m scripts.restore_backup --backup-job-id <uuid> \\
        --database-url postgresql://erpx:...@target-host:5432/erpx \\
        --initiated-by "jane@gir-technologies.com"

Add `--dry-run` first, always, to see exactly what the script would do
without touching anything. See docs/operations/logging-runbook.md and
docs/deployment/production-checklist.md's Disaster Recovery section for
the full operational procedure.

Safety properties (see docs/project-hardening-audit.md's design proposal
for the reasoning behind each):
  - The restore target is ALWAYS an explicit `--database-url` argument —
    never inferred from settings.DATABASE_URL, so an operator can't
    accidentally restore into production while believing they're pointed
    at a drill/staging database.
  - Refuses to proceed if anything else is actively connected to the
    target database (pg_stat_activity check) — the API must be stopped.
  - Refuses to proceed if the target database already has tables, unless
    --yes-wipe-existing-schema is explicitly passed — the plain-SQL dumps
    this platform produces have no --clean directive, so replaying them
    against a non-empty database fails with constraint violations rather
    than cleanly replacing data.
  - Takes its own safety pg_dump of the target's current state before
    wiping/restoring (skippable only via explicit --skip-safety-backup),
    so a botched restore has an immediate way back.
  - Requires typed confirmation (the exact target database name) unless
    --force is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

from app.core.config import settings
from app.core.logging_config import configure_logging, get_logger

configure_logging(service_name="erpx-restore-script")
logger = get_logger(__name__)

PG_DUMP_HEADER = "-- PostgreSQL database dump"
DEFAULT_AUDIT_LOG_PATH = "restore_backup_audit.log"

# Session GUCs that a NEWER pg_dump writes into the dump header but an OLDER
# target server doesn't recognize — replaying them under ON_ERROR_STOP=1 aborts
# the whole restore. They are session-tuning knobs (all emitted as `= 0`, i.e.
# disabled) that have no bearing on the restored *data*, so stripping them is
# safe and lets a dump taken by a newer client restore into an older server.
#   - transaction_timeout: added in PostgreSQL 17; unknown to <=16. The image
#     ships pg_dump 17 (Debian trixie) while the shipped server is postgres 16,
#     so every dump this platform produces contains it — see apps/api/Dockerfile.
# Match the header form pg_dump emits: `SET <name> = <value>;` on its own line.
_INCOMPATIBLE_SESSION_GUCS = ("transaction_timeout",)
_INCOMPATIBLE_SET_RE = re.compile(
    r"^\s*SET\s+(?:" + "|".join(_INCOMPATIBLE_SESSION_GUCS) + r")\s*=", re.IGNORECASE
)


def sanitize_dump_for_restore(sql_file: str) -> str:
    """Return a path to a restore-ready copy of ``sql_file`` with version-skew
    session-GUC directives (see ``_INCOMPATIBLE_SESSION_GUCS``) stripped. If the
    dump contains none, the original path is returned unchanged (no copy made)."""
    with open(sql_file, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    kept = [ln for ln in lines if not _INCOMPATIBLE_SET_RE.match(ln)]
    stripped = len(lines) - len(kept)
    if stripped == 0:
        return sql_file

    sanitized_path = f"{sql_file}.sanitized.sql"
    with open(sanitized_path, "w", encoding="utf-8") as f:
        f.writelines(kept)
    logger.info(
        "restore_dump_sanitized",
        source=sql_file,
        sanitized=sanitized_path,
        lines_removed=stripped,
        gucs=list(_INCOMPATIBLE_SESSION_GUCS),
    )
    return sanitized_path


class ExitCode(IntEnum):
    SUCCESS = 0
    ARGUMENT_ERROR = 1
    BACKUP_NOT_FOUND_OR_INVALID = 2
    TARGET_SAFETY_CHECK_FAILED = 3
    CONFIRMATION_DECLINED = 4
    SAFETY_BACKUP_FAILED = 5
    RESTORE_FAILED = 6
    INTERNAL_ERROR = 7


class RestoreError(Exception):
    def __init__(self, message: str, exit_code: ExitCode):
        super().__init__(message)
        self.exit_code = exit_code


# --------------------------------------------------------------------------
# Pure helpers — no I/O, unit-tested directly.
# --------------------------------------------------------------------------

def redact_url(url: str) -> str:
    """Never print/log a password. Used for every user-facing message and
    every audit log line that mentions a connection string."""
    parsed = urlparse(url.replace("+asyncpg", ""))
    host = parsed.hostname or "?"
    port = parsed.port or 5432
    dbname = (parsed.path or "").lstrip("/") or "?"
    user = parsed.username or "?"
    return f"{user}@{host}:{port}/{dbname}"


def parse_db_url(url: str) -> dict:
    parsed = urlparse(url.replace("+asyncpg", ""))
    if not parsed.hostname or not (parsed.path or "").lstrip("/"):
        raise RestoreError(
            f"--database-url does not look like a valid Postgres connection string: {redact_url(url)}",
            ExitCode.ARGUMENT_ERROR,
        )
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "dbname": (parsed.path or "").lstrip("/"),
    }


def compute_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_pg_dump(path: str) -> bool:
    """pg_dump's plain-SQL output always starts with this exact comment
    line — a cheap, stable format sanity check before we ever hand the
    file to psql against a real database."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        head = f.read(4096)
    return PG_DUMP_HEADER in head


def confirm_target(dbname: str, reader=input) -> bool:
    typed = reader(
        f"Type the target database name ({dbname!r}) to confirm this DESTRUCTIVE restore, "
        f"or anything else to abort: "
    ).strip()
    return typed == dbname


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------

@dataclass
class RestoreAuditEntry:
    started_at: datetime
    initiated_by: str
    target_database: str
    backup_source: str
    dry_run: bool
    status: str = "in_progress"
    completed_at: datetime | None = None
    safety_backup_path: str | None = None
    error_message: str | None = None
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        payload = {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "initiated_by": self.initiated_by,
            "target_database": self.target_database,
            "backup_source": self.backup_source,
            "dry_run": self.dry_run,
            "status": self.status,
            "safety_backup_path": self.safety_backup_path,
            "error_message": self.error_message,
            **self.extra,
        }
        return json.dumps(payload, sort_keys=True)


def write_audit_entry(entry: RestoreAuditEntry, log_path: str) -> None:
    """The PRIMARY audit trail — a local, append-only, JSON-lines log file.
    Always written, regardless of target database state (unlike the
    best-effort `restore_attempts` DB row — see record_restore_attempt).
    """
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry.to_json() + "\n")
    logger.info(
        "restore_audit_entry",
        status=entry.status,
        target_database=entry.target_database,
        initiated_by=entry.initiated_by,
        dry_run=entry.dry_run,
    )


async def record_restore_attempt(
    target_url: str,
    entry: RestoreAuditEntry,
    backup_job_id: uuid.UUID | None,
) -> None:
    """Best-effort secondary audit row in the target database's own
    `restore_attempts` table (apps/api/alembic/versions/0037_*.py) — only
    attempted if that table already exists there. Never raises: a restore
    that otherwise succeeded must not be reported as failed just because
    this optional bookkeeping step couldn't run."""
    try:
        conn = await asyncpg.connect(dsn=target_url.replace("+asyncpg", ""), timeout=10)
    except Exception:
        logger.warning("restore_attempt_record_skipped", reason="target_unreachable")
        return

    try:
        table_exists = await conn.fetchval(
            "SELECT to_regclass('public.restore_attempts') IS NOT NULL"
        )
        if not table_exists:
            logger.info("restore_attempt_record_skipped", reason="table_not_present_in_target")
            return

        await conn.execute(
            """
            INSERT INTO restore_attempts
                (id, backup_job_id, initiated_by, target_database, status,
                 safety_backup_path, error_message, started_at, completed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.uuid4(),
            backup_job_id,
            entry.initiated_by,
            entry.target_database,
            entry.status,
            entry.safety_backup_path,
            entry.error_message,
            entry.started_at,
            entry.completed_at,
        )
        logger.info("restore_attempt_recorded", status=entry.status)
    except Exception:
        logger.warning("restore_attempt_record_failed", exc_info=True)
    finally:
        await conn.close()


# --------------------------------------------------------------------------
# Backup resolution (job id / storage key / local file)
# --------------------------------------------------------------------------

@dataclass
class ResolvedBackup:
    local_path: str
    backup_job_id: uuid.UUID | None
    expected_sha256: str | None
    expected_size_bytes: int | None
    source_description: str
    downloaded: bool  # True if we fetched it from object storage (caller should clean it up)


async def resolve_backup_job(source_database_url: str, backup_job_id: uuid.UUID) -> dict:
    conn = await asyncpg.connect(dsn=source_database_url.replace("+asyncpg", ""), timeout=10)
    try:
        row = await conn.fetchrow(
            "SELECT id, status, storage_key, size_bytes, sha256 FROM backup_jobs WHERE id = $1",
            backup_job_id,
        )
    finally:
        await conn.close()

    if row is None:
        raise RestoreError(f"No backup job found with id {backup_job_id}.", ExitCode.BACKUP_NOT_FOUND_OR_INVALID)
    if row["status"] != "completed":
        raise RestoreError(
            f"Backup job {backup_job_id} has status {row['status']!r}, not 'completed' — refusing to restore from an incomplete/failed backup.",
            ExitCode.BACKUP_NOT_FOUND_OR_INVALID,
        )
    if not row["storage_key"]:
        raise RestoreError(f"Backup job {backup_job_id} has no storage_key.", ExitCode.BACKUP_NOT_FOUND_OR_INVALID)
    return dict(row)


async def download_from_storage(storage_key: str, work_dir: str) -> str:
    from packages.storage.client import get_storage_client

    dest_path = os.path.join(work_dir, os.path.basename(storage_key) or f"{uuid.uuid4()}.sql")
    storage = get_storage_client()
    if not await storage.object_exists(storage_key):
        raise RestoreError(f"Object {storage_key!r} does not exist in bucket {storage.bucket!r}.", ExitCode.BACKUP_NOT_FOUND_OR_INVALID)
    logger.info("restore_download_started", storage_key=storage_key)
    await storage.download_file(storage_key, dest_path)
    logger.info("restore_download_completed", storage_key=storage_key, path=dest_path)
    return dest_path


async def resolve_backup(args: argparse.Namespace, work_dir: str) -> ResolvedBackup:
    if args.backup_file:
        path = args.backup_file
        if not os.path.isfile(path):
            raise RestoreError(f"--backup-file {path!r} does not exist or is not a file.", ExitCode.BACKUP_NOT_FOUND_OR_INVALID)
        if os.path.getsize(path) == 0:
            raise RestoreError(f"--backup-file {path!r} is empty.", ExitCode.BACKUP_NOT_FOUND_OR_INVALID)
        return ResolvedBackup(
            local_path=path,
            backup_job_id=None,
            expected_sha256=args.expected_sha256,
            expected_size_bytes=None,
            source_description=f"local file: {path}",
            downloaded=False,
        )

    if args.storage_key:
        local_path = await download_from_storage(args.storage_key, work_dir)
        return ResolvedBackup(
            local_path=local_path,
            backup_job_id=None,
            expected_sha256=args.expected_sha256,
            expected_size_bytes=None,
            source_description=f"storage key: {args.storage_key}",
            downloaded=True,
        )

    # --backup-job-id
    job = await resolve_backup_job(args.source_database_url, args.backup_job_id)
    local_path = await download_from_storage(job["storage_key"], work_dir)
    return ResolvedBackup(
        local_path=local_path,
        backup_job_id=job["id"],
        expected_sha256=job["sha256"],
        expected_size_bytes=job["size_bytes"],
        source_description=f"backup job {job['id']} (storage key: {job['storage_key']})",
        downloaded=True,
    )


def verify_backup_integrity(resolved: ResolvedBackup, force: bool) -> None:
    actual_size = os.path.getsize(resolved.local_path)
    if resolved.expected_size_bytes is not None and actual_size != resolved.expected_size_bytes:
        raise RestoreError(
            f"Downloaded file size ({actual_size} bytes) does not match the recorded backup size "
            f"({resolved.expected_size_bytes} bytes) — the file may be corrupted or truncated.",
            ExitCode.BACKUP_NOT_FOUND_OR_INVALID,
        )

    actual_sha256 = compute_sha256(resolved.local_path)
    if resolved.expected_sha256:
        if actual_sha256 != resolved.expected_sha256:
            raise RestoreError(
                f"SHA-256 mismatch: expected {resolved.expected_sha256}, got {actual_sha256} — "
                "the backup file is corrupted or was tampered with. Refusing to restore.",
                ExitCode.BACKUP_NOT_FOUND_OR_INVALID,
            )
        logger.info("restore_integrity_verified", sha256=actual_sha256)
    else:
        logger.warning(
            "restore_integrity_unverified",
            reason="no_recorded_sha256",
            sha256=actual_sha256,
        )

    if not looks_like_pg_dump(resolved.local_path):
        msg = (
            f"{resolved.local_path!r} does not look like a pg_dump plain-SQL file "
            f"(missing {PG_DUMP_HEADER!r} header)."
        )
        if force:
            logger.warning("restore_format_check_failed_but_forced", path=resolved.local_path)
        else:
            raise RestoreError(msg + " Pass --force to proceed anyway.", ExitCode.BACKUP_NOT_FOUND_OR_INVALID)


# --------------------------------------------------------------------------
# Target database preconditions
# --------------------------------------------------------------------------

async def check_target_preconditions(target_url: str, allow_wipe: bool) -> bool:
    """Returns True if the target has existing tables (i.e. a wipe will
    actually happen). Raises RestoreError for anything that should block
    the restore outright."""
    try:
        conn = await asyncpg.connect(dsn=target_url.replace("+asyncpg", ""), timeout=10)
    except Exception as exc:
        raise RestoreError(
            f"Could not connect to target database {redact_url(target_url)}: {exc}",
            ExitCode.TARGET_SAFETY_CHECK_FAILED,
        ) from exc

    try:
        other_connections = await conn.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()"
        )
        if other_connections:
            raise RestoreError(
                f"{other_connections} other active connection(s) to {redact_url(target_url)} detected. "
                "Stop the API (and any other process using this database) before restoring — "
                "restoring under a live connection pool risks corrupting in-flight transactions.",
                ExitCode.TARGET_SAFETY_CHECK_FAILED,
            )

        table_count = await conn.fetchval(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        if table_count and not allow_wipe:
            raise RestoreError(
                f"Target database {redact_url(target_url)} already has {table_count} table(s) in the "
                "public schema. This platform's backups are plain-SQL dumps with no --clean directive, "
                "so replaying one against a non-empty database will fail with constraint violations. "
                "Point --database-url at a genuinely empty database, or pass "
                "--yes-wipe-existing-schema to have this script drop and recreate the public schema "
                "first (a safety backup is taken automatically unless --skip-safety-backup is passed).",
                ExitCode.TARGET_SAFETY_CHECK_FAILED,
            )
        return bool(table_count)
    finally:
        await conn.close()


def check_api_not_running(api_health_url: str) -> None:
    try:
        with urllib.request.urlopen(api_health_url, timeout=5) as resp:
            if 200 <= resp.status < 300:
                raise RestoreError(
                    f"--api-health-url {api_health_url!r} responded with HTTP {resp.status} — "
                    "the API appears to still be running. Stop it before restoring.",
                    ExitCode.TARGET_SAFETY_CHECK_FAILED,
                )
    except urllib.error.URLError:
        # Connection refused / timeout / DNS failure — exactly what we want
        # to see (the API is not reachable), not an error condition here.
        logger.info("restore_api_health_check_confirmed_stopped", url=api_health_url)


async def wipe_target_schema(target_url: str) -> None:
    conn = await asyncpg.connect(dsn=target_url.replace("+asyncpg", ""), timeout=30)
    try:
        logger.warning("restore_wiping_target_schema", target=redact_url(target_url))
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    finally:
        await conn.close()


# --------------------------------------------------------------------------
# pg_dump (safety backup) / psql (restore) subprocess execution
# --------------------------------------------------------------------------

def _run_subprocess(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(args, env=env, capture_output=True, text=True)


async def run_safety_backup(target_url: str, work_dir: str) -> str | None:
    db = parse_db_url(target_url)
    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_path = os.path.join(work_dir, f"pre-restore-safety-{db['dbname']}-{timestamp}.sql")

    logger.info("restore_safety_backup_started", target=redact_url(target_url), path=dest_path)
    result = await asyncio.to_thread(
        _run_subprocess,
        [
            settings.PG_DUMP_PATH,
            "-h", db["host"],
            "-p", str(db["port"]),
            "-U", db["user"],
            "-d", db["dbname"],
            "-f", dest_path,
            "--no-owner",
            "--no-privileges",
        ],
        env,
    )
    if result.returncode != 0 or not os.path.exists(dest_path):
        logger.error("restore_safety_backup_failed", stderr=result.stderr[:2000])
        return None

    logger.info("restore_safety_backup_completed", path=dest_path, size_bytes=os.path.getsize(dest_path))
    return dest_path


def _progress_heartbeat(stop_event: threading.Event, label: str) -> None:
    start = time.monotonic()
    while not stop_event.wait(timeout=10):
        elapsed = int(time.monotonic() - start)
        print(f"  ... {label} still running ({elapsed}s elapsed)", file=sys.stderr, flush=True)


async def run_psql_restore(target_url: str, sql_file: str) -> subprocess.CompletedProcess:
    db = parse_db_url(target_url)
    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    # Strip version-skew session-GUC directives a newer pg_dump may have written
    # that this (possibly older) target server would reject under ON_ERROR_STOP=1.
    restore_file = sanitize_dump_for_restore(sql_file)

    stop_event = threading.Event()
    heartbeat = threading.Thread(target=_progress_heartbeat, args=(stop_event, "restore"), daemon=True)
    heartbeat.start()
    logger.info("restore_psql_started", target=redact_url(target_url), sql_file=restore_file)
    try:
        result = await asyncio.to_thread(
            _run_subprocess,
            [
                settings.PSQL_PATH,
                "-h", db["host"],
                "-p", str(db["port"]),
                "-U", db["user"],
                "-d", db["dbname"],
                "-v", "ON_ERROR_STOP=1",
                "-f", restore_file,
            ],
            env,
        )
    finally:
        stop_event.set()
        heartbeat.join(timeout=1)

    return result


async def verify_restore(target_url: str) -> int:
    conn = await asyncpg.connect(dsn=target_url.replace("+asyncpg", ""), timeout=10)
    try:
        table_count = await conn.fetchval(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        await conn.fetchval("SELECT 1")
        return table_count
    finally:
        await conn.close()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="restore_backup",
        description="Restore a modules/backups pg_dump into a target Postgres database. "
                    "CLI-only, manual, confirmation-gated — see this file's module docstring.",
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--backup-job-id", type=uuid.UUID, help="BackupJob id to restore from.")
    source.add_argument("--storage-key", type=str, help="Object storage key to restore from directly.")
    source.add_argument("--backup-file", type=str, help="A local .sql dump file already on disk.")

    parser.add_argument(
        "--database-url", required=True, type=str,
        help="Explicit target Postgres connection string. NEVER inferred from settings.DATABASE_URL.",
    )
    parser.add_argument(
        "--source-database-url", type=str, default=settings.DATABASE_URL,
        help="Where to look up BackupJob metadata for --backup-job-id (read-only). "
             "Defaults to the app's configured DATABASE_URL.",
    )
    parser.add_argument("--expected-sha256", type=str, default=None, help="Expected SHA-256 for --backup-file/--storage-key (optional).")
    parser.add_argument("--initiated-by", type=str, default=None, help="Operator identifier for the audit trail. Defaults to the OS username.")
    parser.add_argument("--api-health-url", type=str, default=None, help="If set, refuse to restore if this URL responds successfully (API still up).")
    parser.add_argument("--force", action="store_true", help="Skip the interactive confirmation prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Validate everything and print the plan; make no changes.")
    parser.add_argument("--yes-wipe-existing-schema", action="store_true", help="Required if the target database already has tables.")
    parser.add_argument("--skip-safety-backup", action="store_true", help="Skip taking a pre-restore pg_dump of the target's current state.")
    parser.add_argument("--work-dir", type=str, default=None, help="Directory for downloaded/temporary files. Defaults to a fresh temp dir.")
    parser.add_argument("--audit-log-path", type=str, default=DEFAULT_AUDIT_LOG_PATH, help="Local audit log file path.")
    return parser


async def _async_main(args: argparse.Namespace) -> int:
    initiated_by = args.initiated_by or getpass.getuser()
    target_display = redact_url(args.database_url)
    entry = RestoreAuditEntry(
        started_at=datetime.now(timezone.utc),
        initiated_by=initiated_by,
        target_database=target_display,
        backup_source="(resolving)",
        dry_run=args.dry_run,
    )

    work_dir = args.work_dir or tempfile.mkdtemp(prefix="erpx_restore_")
    os.makedirs(work_dir, exist_ok=True)
    resolved = None

    try:
        print(f"[1/7] Resolving backup source...")
        resolved = await resolve_backup(args, work_dir)
        entry.backup_source = resolved.source_description
        print(f"      -> {resolved.source_description}")

        print("[2/7] Verifying backup integrity...")
        verify_backup_integrity(resolved, force=args.force)
        print("      -> OK")

        print("[3/7] Checking target database preconditions (connections, existing schema)...")
        target_has_tables = await check_target_preconditions(args.database_url, args.yes_wipe_existing_schema)
        if args.api_health_url:
            check_api_not_running(args.api_health_url)
        print(f"      -> reachable; existing tables: {target_has_tables}")

        print("[4/7] Restore plan:")
        print(f"      Target:          {target_display}")
        print(f"      Backup source:   {resolved.source_description}")
        print(f"      Will wipe first: {target_has_tables}")
        print(f"      Safety backup:   {'skipped (--skip-safety-backup)' if args.skip_safety_backup else 'yes'}")

        if args.dry_run:
            entry.status = "dry_run"
            entry.completed_at = datetime.now(timezone.utc)
            write_audit_entry(entry, args.audit_log_path)
            print("[DRY RUN] No changes made. Re-run without --dry-run to execute.")
            return ExitCode.SUCCESS

        if not args.force:
            print("[5/7] Confirmation required.")
            if not confirm_target(parse_db_url(args.database_url)["dbname"], reader=input):
                entry.status = "aborted"
                entry.error_message = "confirmation declined"
                entry.completed_at = datetime.now(timezone.utc)
                write_audit_entry(entry, args.audit_log_path)
                print("Aborted: confirmation text did not match. No changes made.")
                return ExitCode.CONFIRMATION_DECLINED
        else:
            print("[5/7] --force: skipping interactive confirmation.", file=sys.stderr)

        safety_backup_path = None
        if not args.skip_safety_backup:
            print("[6/7] Taking safety backup of target's current state...")
            safety_backup_path = await run_safety_backup(args.database_url, work_dir)
            if safety_backup_path is None:
                entry.status = "failed"
                entry.error_message = "safety backup failed"
                entry.completed_at = datetime.now(timezone.utc)
                write_audit_entry(entry, args.audit_log_path)
                print("Safety backup failed — aborting before touching the target database. "
                      "Pass --skip-safety-backup only if you have your own fallback.")
                return ExitCode.SAFETY_BACKUP_FAILED
            entry.safety_backup_path = safety_backup_path
            print(f"      -> {safety_backup_path}")
        else:
            print("[6/7] --skip-safety-backup: no safety backup taken.")

        if target_has_tables:
            await wipe_target_schema(args.database_url)

        print("[7/7] Restoring (this can take a while for a large database)...")
        result = await run_psql_restore(args.database_url, resolved.local_path)

        if result.returncode != 0:
            entry.status = "failed"
            entry.error_message = f"psql exited {result.returncode}: {result.stderr[-2000:]}"
            entry.completed_at = datetime.now(timezone.utc)
            write_audit_entry(entry, args.audit_log_path)
            await record_restore_attempt(args.database_url, entry, resolved.backup_job_id)
            print("RESTORE FAILED. The target database is now in a partially-restored, "
                  "likely inconsistent state.")
            if safety_backup_path:
                print(f"Rollback: restore again using the pre-restore safety backup at {safety_backup_path}")
            print(f"psql stderr (tail):\n{result.stderr[-2000:]}", file=sys.stderr)
            return ExitCode.RESTORE_FAILED

        table_count = await verify_restore(args.database_url)
        entry.status = "succeeded"
        entry.completed_at = datetime.now(timezone.utc)
        entry.extra["restored_table_count"] = table_count
        write_audit_entry(entry, args.audit_log_path)
        await record_restore_attempt(args.database_url, entry, resolved.backup_job_id)

        print(f"Restore succeeded. Target now has {table_count} table(s) in the public schema.")
        return ExitCode.SUCCESS

    except RestoreError as exc:
        entry.status = "failed"
        entry.error_message = str(exc)
        entry.completed_at = datetime.now(timezone.utc)
        write_audit_entry(entry, args.audit_log_path)
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    finally:
        if resolved and resolved.downloaded and os.path.exists(resolved.local_path):
            os.remove(resolved.local_path)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        parse_db_url(args.database_url)  # validate early, before any I/O
    except RestoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code

    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\nAborted by operator (Ctrl-C). No further changes made.", file=sys.stderr)
        return ExitCode.CONFIRMATION_DECLINED
    except Exception:
        logger.exception("restore_unexpected_error")
        print("An unexpected error occurred — see logs for the full traceback.", file=sys.stderr)
        return ExitCode.INTERNAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
