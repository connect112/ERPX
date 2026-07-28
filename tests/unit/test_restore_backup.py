"""
Unit tests for apps/api/scripts/restore_backup.py's pure logic — argument
parsing, connection-string redaction/parsing, integrity-check primitives,
and the confirmation prompt. No database or network access (see
tests/integration/test_restore_backup_integration.py for the real-DB,
real-subprocess coverage of the destructive paths).
"""

import hashlib

import pytest

from scripts.restore_backup import (
    ExitCode,
    RestoreError,
    build_arg_parser,
    compute_sha256,
    confirm_target,
    looks_like_pg_dump,
    parse_db_url,
    redact_url,
)

pytestmark = pytest.mark.unit


def test_redact_url_never_includes_password():
    url = "postgresql+asyncpg://erpx:super_secret_password@db.internal:5433/erpx"
    redacted = redact_url(url)
    assert "super_secret_password" not in redacted
    assert redacted == "erpx@db.internal:5433/erpx"


def test_redact_url_handles_missing_parts():
    assert redact_url("postgresql://localhost/erpx") == "?@localhost:5432/erpx"


def test_parse_db_url_extracts_all_fields():
    parsed = parse_db_url("postgresql+asyncpg://erpx:secret@10.0.0.5:5433/erpx_prod")
    assert parsed == {
        "host": "10.0.0.5",
        "port": 5433,
        "user": "erpx",
        "password": "secret",
        "dbname": "erpx_prod",
    }


def test_parse_db_url_defaults_port_5432():
    parsed = parse_db_url("postgresql://erpx:secret@dbhost/erpx")
    assert parsed["port"] == 5432


def test_parse_db_url_rejects_url_with_no_dbname():
    with pytest.raises(RestoreError) as exc_info:
        parse_db_url("postgresql://erpx:secret@dbhost/")
    assert exc_info.value.exit_code == ExitCode.ARGUMENT_ERROR


def test_parse_db_url_rejects_url_with_no_host():
    with pytest.raises(RestoreError) as exc_info:
        parse_db_url("postgresql:///erpx")
    assert exc_info.value.exit_code == ExitCode.ARGUMENT_ERROR


def test_compute_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "backup.sql"
    f.write_bytes(b"-- PostgreSQL database dump\nSELECT 1;\n")
    expected = hashlib.sha256(f.read_bytes()).hexdigest()
    assert compute_sha256(str(f)) == expected


def test_compute_sha256_differs_for_different_content(tmp_path):
    f1 = tmp_path / "a.sql"
    f2 = tmp_path / "b.sql"
    f1.write_bytes(b"content one")
    f2.write_bytes(b"content two")
    assert compute_sha256(str(f1)) != compute_sha256(str(f2))


def test_looks_like_pg_dump_true_for_real_header(tmp_path):
    f = tmp_path / "backup.sql"
    f.write_text("-- PostgreSQL database dump\n--\n\nSET statement_timeout = 0;\n")
    assert looks_like_pg_dump(str(f)) is True


def test_looks_like_pg_dump_false_for_unrelated_content(tmp_path):
    f = tmp_path / "not_a_dump.sql"
    f.write_text("DROP TABLE users;\n")
    assert looks_like_pg_dump(str(f)) is False


def test_confirm_target_accepts_exact_match():
    assert confirm_target("erpx_prod", reader=lambda _: "erpx_prod") is True


def test_confirm_target_rejects_mismatch():
    assert confirm_target("erpx_prod", reader=lambda _: "erpx_prd") is False


def test_confirm_target_rejects_empty_input():
    assert confirm_target("erpx_prod", reader=lambda _: "") is False


def test_confirm_target_strips_whitespace_but_requires_exact_name():
    assert confirm_target("erpx_prod", reader=lambda _: "  erpx_prod  ") is True


class TestArgParser:
    def test_requires_database_url(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--backup-file", "x.sql"])

    def test_requires_exactly_one_backup_source(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--database-url", "postgresql://u:p@h/d"])

    def test_rejects_multiple_backup_sources(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "--backup-file", "x.sql",
                    "--storage-key", "backups/y.sql",
                    "--database-url", "postgresql://u:p@h/d",
                ]
            )

    def test_accepts_minimal_valid_invocation(self):
        parser = build_arg_parser()
        args = parser.parse_args(
            ["--backup-file", "x.sql", "--database-url", "postgresql://u:p@h/d"]
        )
        assert args.backup_file == "x.sql"
        assert args.database_url == "postgresql://u:p@h/d"
        assert args.force is False
        assert args.dry_run is False
        assert args.yes_wipe_existing_schema is False
        assert args.skip_safety_backup is False

    def test_flags_parse_correctly(self):
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "--storage-key", "backups/x.sql",
                "--database-url", "postgresql://u:p@h/d",
                "--force",
                "--dry-run",
                "--yes-wipe-existing-schema",
                "--skip-safety-backup",
            ]
        )
        assert args.force is True
        assert args.dry_run is True
        assert args.yes_wipe_existing_schema is True
        assert args.skip_safety_backup is True

    def test_backup_job_id_must_be_a_uuid(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["--backup-job-id", "not-a-uuid", "--database-url", "postgresql://u:p@h/d"]
            )


def test_exit_codes_are_distinct():
    values = [e.value for e in ExitCode]
    assert len(values) == len(set(values))
    assert ExitCode.SUCCESS == 0
