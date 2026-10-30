"""
Unit tests for the in-app backup safeguards: the disk-space check, compressed dumps, the schedule flag, retention
selection, and restoring both dump formats. No database, network or pg_dump needed.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from app.core import celery_app as celery_module
from app.core.config import settings
from modules.backups import service as backup_service
from modules.backups import tasks as backup_tasks
from modules.backups.models import BackupStatus
from modules.backups.retention import select_backups_to_prune
from scripts.restore_backup import (
    RestoreError,
    ResolvedBackup,
    build_restore_command,
    detect_dump_format,
    verify_backup_integrity,
)

pytestmark = pytest.mark.unit

GIB = 1024**3


# ---- disk-space check ------------------------------------------------------------------------------------------

def test_required_free_space_is_database_size_times_factor_plus_reserve(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DISK_SAFETY_FACTOR", 2.5)
    monkeypatch.setattr(settings, "BACKUP_MIN_FREE_BYTES", 2 * GIB)
    assert backup_service.required_free_bytes(1 * GIB) == int(2.5 * GIB) + 2 * GIB


def test_backup_is_refused_when_the_disk_is_too_full(monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DISK_SAFETY_FACTOR", 2.5)
    monkeypatch.setattr(settings, "BACKUP_MIN_FREE_BYTES", 2 * GIB)
    monkeypatch.setattr(backup_service.shutil, "disk_usage", lambda path: SimpleNamespace(free=3 * GIB))
    with pytest.raises(backup_service.InsufficientDiskSpaceError) as exc:
        backup_service.check_free_space("/tmp", 547 * 1024**2)   # production-sized database: needs about 3.3 GB
    message = str(exc.value)
    assert "3.0 GB free" in message and "nothing was written" in message


def test_backup_is_allowed_when_there_is_room(monkeypatch):
    monkeypatch.setattr(backup_service.shutil, "disk_usage", lambda path: SimpleNamespace(free=50 * GIB))
    backup_service.check_free_space("/tmp", 547 * 1024**2)   # no exception


# ---- compressed dumps ------------------------------------------------------------------------------------------

PARSED = urlparse("postgresql://erpx:pw@db.internal:5433/erpx")


def test_custom_format_asks_pg_dump_for_a_compressed_archive():
    command = backup_service.build_pg_dump_command("pg_dump", PARSED, "/tmp/x.dump", "custom")
    assert "-Fc" in command and command[command.index("-Z") + 1] == "6"
    assert command[command.index("-d") + 1] == "erpx" and command[command.index("-p") + 1] == "5433"
    assert "pw" not in " ".join(command)   # the password goes in the environment, never the command line


def test_plain_format_is_the_old_uncompressed_command():
    command = backup_service.build_pg_dump_command("pg_dump", PARSED, "/tmp/x.sql", "plain")
    assert "-Fc" not in command and "-Z" not in command


def test_file_suffix_and_type_follow_the_format():
    assert backup_service.backup_file_details("custom") == (".dump", "application/octet-stream")
    assert backup_service.backup_file_details("plain") == (".sql", "application/sql")


def test_compressed_backups_are_the_default():
    assert settings.BACKUP_FORMAT == "custom"


# ---- schedule flag ---------------------------------------------------------------------------------------------

def test_schedule_keeps_the_backup_by_default():
    assert settings.BACKUP_IN_APP_SCHEDULE_ENABLED is True
    assert "backups-trigger-daily" in celery_module.celery_app.conf.beat_schedule


def test_flag_off_removes_only_the_backup_entry():
    schedule = {"backups-trigger-daily": {}, "reports-run-due-scheduled-reports": {}}
    result = celery_module.apply_backup_schedule_flag(schedule, enabled=False)
    assert list(result) == ["reports-run-due-scheduled-reports"]


def test_flag_on_changes_nothing():
    schedule = {"backups-trigger-daily": {}, "other": {}}
    assert celery_module.apply_backup_schedule_flag(schedule, enabled=True) == {"backups-trigger-daily": {}, "other": {}}


def test_the_task_does_nothing_when_the_flag_is_off(monkeypatch):
    called = []
    monkeypatch.setattr(settings, "BACKUP_IN_APP_SCHEDULE_ENABLED", False)
    monkeypatch.setattr(backup_tasks, "run_async", lambda coro: called.append(coro))
    backup_tasks.trigger_daily_backup_task()
    assert called == []


# ---- retention selection ---------------------------------------------------------------------------------------

def _job(days_ago, status=BackupStatus.COMPLETED, key="set"):
    return SimpleNamespace(
        id=uuid.uuid4(), status=status, storage_key=(f"backups/{days_ago}.dump" if key == "set" else key),
        started_at=datetime(2026, 10, 30, tzinfo=timezone.utc) - timedelta(days=days_ago), size_bytes=1,
    )


def test_keep_zero_selects_nothing():
    assert select_backups_to_prune([_job(1), _job(2)], 0) == []


def test_the_newest_n_are_kept_and_older_ones_selected_oldest_first():
    jobs = [_job(d) for d in (1, 2, 3, 4, 5)]
    selected = select_backups_to_prune(jobs, 2)
    assert [j.storage_key for j in selected] == ["backups/5.dump", "backups/4.dump", "backups/3.dump"]


def test_failed_running_and_already_pruned_jobs_are_never_selected():
    jobs = [_job(1), _job(2, BackupStatus.FAILED), _job(3, BackupStatus.RUNNING), _job(4, key=None), _job(5), _job(6)]
    selected = select_backups_to_prune(jobs, 1)
    assert [j.storage_key for j in selected] == ["backups/6.dump", "backups/5.dump"]


# ---- restoring both formats ------------------------------------------------------------------------------------

DB = {"host": "h", "port": 5432, "user": "u", "password": "p", "dbname": "target"}


def test_a_compressed_archive_is_detected_by_its_magic_bytes(tmp_path):
    path = tmp_path / "a.dump"
    path.write_bytes(b"PGDMP\x01\x0e\x00" + b"\x00" * 50)
    assert detect_dump_format(str(path)) == "custom"


def test_plain_sql_and_unknown_files_are_told_apart(tmp_path):
    plain = tmp_path / "a.sql"
    plain.write_text("--\n-- PostgreSQL database dump\n--\n")
    junk = tmp_path / "b.bin"
    junk.write_bytes(b"not a dump")
    assert detect_dump_format(str(plain)) == "plain"
    assert detect_dump_format(str(junk)) == "unknown"


def test_restore_uses_pg_restore_for_archives_and_psql_for_sql():
    custom = build_restore_command("custom", DB, "/tmp/a.dump")
    plain = build_restore_command("plain", DB, "/tmp/a.sql")
    assert custom[0] == settings.PG_RESTORE_PATH and "--exit-on-error" in custom and custom[-1] == "/tmp/a.dump"
    assert plain[0] == settings.PSQL_PATH and "ON_ERROR_STOP=1" in plain and plain[-1] == "/tmp/a.sql"
    assert "p" not in custom[:1]   # no password on the command line


def _resolved(path):
    return ResolvedBackup(str(path), None, None, None, "test", False)


def test_integrity_check_accepts_a_compressed_archive(tmp_path):
    path = tmp_path / "a.dump"
    path.write_bytes(b"PGDMP" + b"\x00" * 20)
    verify_backup_integrity(_resolved(path), force=False)   # no exception


def test_integrity_check_still_rejects_unrelated_files(tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(b"hello")
    with pytest.raises(RestoreError):
        verify_backup_integrity(_resolved(path), force=False)
