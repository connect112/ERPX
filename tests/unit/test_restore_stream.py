"""Unit tests for scripts/restore_stream.py: the header-only filter and the producer -> consumer transaction pipeline.

No database: the producer and consumer are tiny Python subprocesses, so process failures (either side), early exits, stderr floods
and large streams are exercised for real.
"""

import io
import sys
import time

import pytest

from scripts.restore_stream import (
    MAX_PREAMBLE_LINES,
    STDERR_TAIL_BYTES,
    iter_restore_script,
    parse_tool_version,
    stream_restore,
)

pytestmark = pytest.mark.unit

HEADER = (
    b"--\n-- PostgreSQL database dump\n--\n\n"
    b"SET statement_timeout = 0;\nSET lock_timeout = 0;\nSET transaction_timeout = 0;\nSET client_encoding = 'UTF8';\n"
    b"SELECT pg_catalog.set_config('search_path', '', false);\n\n"
)


def _filter(data: bytes, chunk_size: int = 65536) -> bytes:
    return b"".join(iter_restore_script(io.BytesIO(data), chunk_size))


class TestToolVersion:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("pg_restore (PostgreSQL) 16.13", (16, 13)),
            ("pg_restore (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)", (17, 11)),
            ("psql (PostgreSQL) 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)", (18, 6)),
            ("pg_dump (PostgreSQL) 18beta1", (18, 0)),
            ("pg_restore (PostgreSQL) 9.6.24", (9, 6)),
        ],
    )
    def test_versions_are_parsed(self, text, expected):
        assert parse_tool_version(text) == expected

    def test_unrecognised_output_is_none(self):
        assert parse_tool_version("command not found") is None


class TestHeaderFilter:
    def test_the_header_line_is_dropped_and_everything_else_is_untouched(self):
        body = b"CREATE TABLE t (a text);\nCOPY public.t (a) FROM stdin;\nrow\n\\.\n"
        out = _filter(HEADER + body)
        assert b"SET transaction_timeout" not in out
        assert out == HEADER.replace(b"SET transaction_timeout = 0;\n", b"") + body

    def test_a_data_row_with_the_same_text_is_never_altered(self):
        # the defect of the old whole-file sanitiser: this COPY row starts with exactly the header line
        data = HEADER + b"CREATE TABLE notes (body text, n int);\nCOPY public.notes (body, n) FROM stdin;\nSET transaction_timeout = 0;\t7\nplain\t8\n\\.\n"
        out = _filter(data)
        assert b"SET transaction_timeout = 0;\t7\n" in out
        assert out.count(b"\t") == data.count(b"\t")

    def test_the_same_text_after_the_header_is_kept_even_as_a_statement_line(self):
        data = HEADER + b"CREATE TABLE t (a int);\nSET transaction_timeout = 0;\n"
        assert _filter(data).endswith(b"CREATE TABLE t (a int);\nSET transaction_timeout = 0;\n")

    def test_only_the_canonical_form_is_removed(self):
        for variant in (b"SET transaction_timeout = 5;\n", b"SET transaction_timeout TO 0;\n", b"set transaction_timeout = 0;\n"):
            assert variant in _filter(b"--\n" + variant + b"CREATE TABLE t (a int);\n")

    def test_psql_guard_lines_and_comments_do_not_end_the_header(self):
        data = b"\\restrict AbC123\n--\n-- comment\n--\nSET transaction_timeout = 0;\nSET statement_timeout = 0;\nCREATE TABLE t (a int);\n\\unrestrict AbC123\n"
        out = _filter(data)
        assert out == data.replace(b"SET transaction_timeout = 0;\n", b"")

    def test_windows_line_endings_in_the_header(self):
        data = b"--\r\nSET transaction_timeout = 0;\r\nSET lock_timeout = 0;\r\nCREATE TABLE t (a int);\r\n"
        assert _filter(data) == b"--\r\nSET lock_timeout = 0;\r\nCREATE TABLE t (a int);\r\n"

    @pytest.mark.parametrize("chunk_size", [1, 2, 3, 7, 64, 65536])
    def test_the_result_does_not_depend_on_chunk_boundaries(self, chunk_size):
        data = HEADER + b"CREATE TABLE t (a int);\nCOPY t FROM stdin;\n" + b"x\ty\n" * 1000 + b"\\.\n"
        assert _filter(data, chunk_size) == _filter(data)

    def test_a_script_with_a_very_long_comment_header_is_passed_through_unchanged(self):
        data = b"--\n" * (MAX_PREAMBLE_LINES + 50) + b"SET transaction_timeout = 0;\nCREATE TABLE t (a int);\n"
        assert _filter(data) == data

    def test_empty_and_header_only_inputs(self):
        assert _filter(b"") == b""
        assert _filter(b"SET transaction_timeout = 0;\n") == b""


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _consumer_recording_to(path, exit_code: int = 0, exit_after_bytes: int | None = None) -> list[str]:
    code = (
        "import sys\n"
        f"out = open({str(path)!r}, 'wb')\n"
        "got = 0\n"
        "while True:\n"
        "    b = sys.stdin.buffer.read1(65536)\n"
        "    if not b: break\n"
        "    out.write(b); out.flush(); got += len(b)\n"
        f"    if {exit_after_bytes!r} is not None and got >= {exit_after_bytes!r}: sys.exit({exit_code})\n"
        f"sys.exit({exit_code})\n"
    )
    return _py(code)


def _producer(script: bytes, exit_code: int = 0, stderr_bytes: int = 0) -> list[str]:
    code = (
        "import sys\n"
        f"sys.stdout.buffer.write({script!r}); sys.stdout.buffer.flush()\n"
        f"sys.stderr.write('E' * {stderr_bytes})\n"
        f"sys.exit({exit_code})\n"
    )
    return _py(code)


class TestStreamRestore:
    def test_success_wraps_the_script_in_one_transaction_and_commits_once(self, tmp_path):
        out = tmp_path / "psql_input.sql"
        result = stream_restore(_consumer_recording_to(out), producer_cmd=_producer(HEADER + b"CREATE TABLE t (a int);\n"))
        assert result.ok and result.committed_sent
        sent = out.read_bytes()
        assert sent.startswith(b"BEGIN;\n") and sent.endswith(b"COMMIT;\n")
        assert sent.count(b"COMMIT;") == 1 and b"ROLLBACK" not in sent
        assert b"SET transaction_timeout" not in sent and b"CREATE TABLE t (a int);" in sent

    def test_the_schema_wipe_is_inside_the_transaction_before_the_script(self, tmp_path):
        out = tmp_path / "in.sql"
        stream_restore(_consumer_recording_to(out), producer_cmd=_producer(b"CREATE TABLE t (a int);\n"), wipe_schema=True)
        sent = out.read_bytes()
        assert sent.startswith(b"BEGIN;\nDROP SCHEMA public CASCADE;\nCREATE SCHEMA public;\n")
        assert sent.index(b"DROP SCHEMA") < sent.index(b"CREATE TABLE t") < sent.index(b"COMMIT;")

    def test_no_wipe_means_no_drop(self, tmp_path):
        out = tmp_path / "in.sql"
        stream_restore(_consumer_recording_to(out), producer_cmd=_producer(b"SELECT 1;\n"))
        assert b"DROP SCHEMA" not in out.read_bytes()

    def test_a_failing_producer_gets_a_rollback_and_never_a_commit(self, tmp_path):
        out = tmp_path / "in.sql"
        result = stream_restore(_consumer_recording_to(out), producer_cmd=_producer(b"CREATE TABLE a (x int);\n", exit_code=3))
        assert not result.ok and not result.committed_sent
        assert result.producer_returncode == 3 and "pg_restore" in result.failure and "rolled back" in result.failure
        sent = out.read_bytes()
        assert sent.endswith(b"ROLLBACK;\n") and b"COMMIT" not in sent

    def test_a_consumer_that_exits_zero_cannot_make_a_failed_producer_succeed(self, tmp_path):
        result = stream_restore(_consumer_recording_to(tmp_path / "in.sql", exit_code=0), producer_cmd=_producer(b"SELECT 1;\n", exit_code=1))
        assert not result.ok

    def test_a_failing_consumer_fails_the_restore_even_if_the_producer_is_fine(self, tmp_path):
        result = stream_restore(_consumer_recording_to(tmp_path / "in.sql", exit_code=3), producer_cmd=_producer(b"SELECT 1;\n"))
        assert not result.ok and result.consumer_returncode == 3 and "psql" in result.failure

    def test_a_consumer_that_dies_early_stops_a_huge_producer_quickly(self, tmp_path):
        endless = _py("import sys\nline = b'INSERT INTO t VALUES (1);\\n' * 4000\nwhile True:\n    sys.stdout.buffer.write(line)\n")
        started = time.monotonic()
        result = stream_restore(_consumer_recording_to(tmp_path / "in.sql", exit_code=3, exit_after_bytes=200_000), producer_cmd=endless)
        assert time.monotonic() - started < 30, "the producer must be killed, not read to the end"
        assert not result.ok and not result.committed_sent
        assert b"COMMIT" not in (tmp_path / "in.sql").read_bytes()

    def test_a_consumer_that_cannot_start_a_connection_fails_cleanly(self, tmp_path):
        consumer = _py("import sys; sys.stderr.write('psql: error: connection refused'); sys.exit(2)")
        many_lines = _py("import sys\nsys.stdout.buffer.write(b'SELECT 1;\\n' * 100000)")
        result = stream_restore(consumer, producer_cmd=many_lines)
        assert not result.ok and "connection refused" in result.consumer_stderr

    def test_a_flood_of_stderr_cannot_deadlock_and_is_kept_to_a_tail(self, tmp_path):
        result = stream_restore(_consumer_recording_to(tmp_path / "in.sql"), producer_cmd=_producer(b"SELECT 1;\n", stderr_bytes=3_000_000))
        assert result.ok
        assert 0 < len(result.producer_stderr) <= STDERR_TAIL_BYTES + 8192

    def test_a_plain_file_is_streamed_without_a_producer_process(self, tmp_path):
        src = tmp_path / "dump.sql"
        src.write_bytes(HEADER + b"CREATE TABLE t (a int);\n")
        out = tmp_path / "in.sql"
        result = stream_restore(_consumer_recording_to(out), source_file=str(src))
        assert result.ok and result.producer_returncode is None or result.producer_returncode == 0
        assert b"SET transaction_timeout" not in out.read_bytes() and out.read_bytes().endswith(b"COMMIT;\n")

    def test_a_large_stream_is_passed_through_intact(self, tmp_path):
        big = _py("import sys\nfor i in range(200000):\n    sys.stdout.write('INSERT INTO t VALUES (%d, repeat(%d));\\n' % (i, i))\n")
        out = tmp_path / "in.sql"
        result = stream_restore(_consumer_recording_to(out), producer_cmd=big)
        assert result.ok
        sent = out.read_bytes()
        assert sent.count(b"INSERT INTO t") == 200000 and result.bytes_streamed > 5_000_000

    def test_exactly_one_source_must_be_given(self):
        with pytest.raises(ValueError):
            stream_restore(_py("pass"))
        with pytest.raises(ValueError):
            stream_restore(_py("pass"), producer_cmd=_py("pass"), source_file="x")

    def test_a_missing_producer_binary_does_not_leave_the_consumer_running(self):
        with pytest.raises(OSError):
            stream_restore(_py("import time; time.sleep(60)"), producer_cmd=["/definitely/not/a/binary"])
