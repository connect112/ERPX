"""Streaming, transactional restore pipeline used by scripts/restore_backup.py.

Why this exists. A compressed (pg_dump -Fc) archive used to be restored with ``pg_restore -d <db>``. Two version rules make that
fragile, and both were reproduced against a PostgreSQL 16 server:

  * a pg_restore of version 17 or newer sends ``SET transaction_timeout = 0;`` when it restores straight into a 16 server, which
    16 rejects, and
  * a pg_restore of version 16 cannot read an archive made by pg_dump 17 or newer ("unsupported version (1.16)").

The restore therefore runs as a pipeline: ``pg_restore -f -`` (SQL script on stdout, no database connection) -> a header-only filter
-> ``psql -v ON_ERROR_STOP=1``. Everything between BEGIN and COMMIT is one transaction, including the optional schema wipe, and COMMIT
is only sent after the producer has exited cleanly, so a failure on either side leaves the target database as it was.

Nothing here imports the application's settings: tool paths and connection arguments are passed in, which keeps it unit-testable.
"""

from __future__ import annotations

import re
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import BinaryIO, Iterator

CHUNK_SIZE = 64 * 1024
# The SQL header pg_dump / pg_restore write before the first real statement is short. Looking further than this for header lines
# could only ever mean we are looking at data, so the filter gives up and passes everything through unchanged.
MAX_PREAMBLE_LINES = 400
STDERR_TAIL_BYTES = 8000

# The one line a newer client writes that an older server rejects. Matched in its exact canonical form, on a line of its own.
_SET_TRANSACTION_TIMEOUT = re.compile(rb"^SET transaction_timeout = 0;\r?\n?$")
# What may legitimately appear in the header: comments, SET statements, set_config() calls, psql's \restrict / \unrestrict guards
# (added to dumps by the 2025 security releases) and blank lines. The first line that is none of these ends the header.
_HEADER_LINE = re.compile(rb"^(--.*|SET .*;|SELECT pg_catalog\.set_config\(.*\);|\\(?:un)?restrict \S+|\s*)\r?\n?$")

_TOOL_VERSION = re.compile(r"\(PostgreSQL\)\s+(\d+)(?:\.(\d+))?")
_DUMPED_BY = re.compile(r"Dumped by pg_dump version:\s*(\d+)(?:\.(\d+))?")
_DUMPED_FROM = re.compile(r"Dumped from database version:\s*(\d+)(?:\.(\d+))?")


class ToolError(Exception):
    """A PostgreSQL client tool is missing or reports something we cannot interpret."""


class ArchiveUnreadable(Exception):
    """pg_restore cannot read the archive (for example it was made by a newer pg_dump). Nothing has been changed."""

    def __init__(self, message: str, *, too_new_for_client: bool = False):
        super().__init__(message)
        self.too_new_for_client = too_new_for_client


def parse_tool_version(text: str) -> tuple[int, int] | None:
    """``pg_restore (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)`` -> (17, 11). A pre-release such as ``18beta1`` -> (18, 0)."""
    match = _TOOL_VERSION.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 0)


def tool_version(path: str, env: dict | None = None) -> tuple[int, int]:
    try:
        result = subprocess.run([path, "--version"], capture_output=True, text=True, env=env, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolError(f"Could not run {path!r}: {exc}") from exc
    version = parse_tool_version(result.stdout) if result.returncode == 0 else None
    if version is None:
        raise ToolError(f"{path!r} --version did not report a PostgreSQL version (exit {result.returncode}): {result.stderr[:200]}")
    return version


@dataclass(frozen=True)
class ArchiveInfo:
    dumped_by: tuple[int, int] | None  # pg_dump version that wrote the archive
    dumped_from: tuple[int, int] | None  # server version the archive was taken from
    toc_entries: int


def inspect_archive(pg_restore: str, path: str, env: dict | None = None) -> ArchiveInfo:
    """Read the archive's table of contents with the restore client. Fails (changing nothing) if this client cannot read it."""
    try:
        result = subprocess.run([pg_restore, "--list", path], capture_output=True, text=True, env=env, errors="replace")
    except OSError as exc:
        raise ToolError(f"Could not run {pg_restore!r}: {exc}") from exc
    if result.returncode != 0:
        err = " ".join(result.stderr.split())[:400]
        raise ArchiveUnreadable(
            f"pg_restore could not read the archive: {err}",
            too_new_for_client="unsupported version" in err,
        )
    by = _DUMPED_BY.search(result.stdout)
    frm = _DUMPED_FROM.search(result.stdout)
    entries = sum(1 for line in result.stdout.splitlines() if line[:1].isdigit())
    return ArchiveInfo(
        dumped_by=(int(by.group(1)), int(by.group(2) or 0)) if by else None,
        dumped_from=(int(frm.group(1)), int(frm.group(2) or 0)) if frm else None,
        toc_entries=entries,
    )


def scan_archive(pg_restore: str, path: str, env: dict | None = None) -> None:
    """Read the WHOLE archive once, discarding the output, so a truncated or corrupt file is found before anything is changed."""
    proc = subprocess.Popen(
        [pg_restore, "--no-owner", "--no-privileges", "-f", "-", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env,
    )
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise ArchiveUnreadable("the archive failed a full read-through: " + " ".join(err.decode(errors="replace").split())[:400])


def iter_restore_script(src: BinaryIO, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """Pass a SQL script through unchanged, except that the canonical ``SET transaction_timeout = 0;`` line is dropped when it is in
    the header. The header ends at the first line that is not a comment, SET, set_config() call, psql guard or blank line; from there
    on, bytes are passed through untouched, so application data (COPY rows, string literals) can never be altered.
    Memory use is constant: one line while in the header, then ``chunk_size`` bytes at a time."""
    for _ in range(MAX_PREAMBLE_LINES):
        line = src.readline()
        if not line:
            return
        if _SET_TRANSACTION_TIMEOUT.match(line):
            continue
        yield line
        if not _HEADER_LINE.match(line):
            break
    reader = getattr(src, "read1", None) or src.read
    while True:
        chunk = reader(chunk_size)
        if not chunk:
            return
        yield chunk


@dataclass
class StreamResult:
    ok: bool
    committed_sent: bool
    producer_returncode: int | None
    consumer_returncode: int | None
    producer_stderr: str = ""
    consumer_stderr: str = ""
    bytes_streamed: int = 0
    failure: str | None = None
    notes: list[str] = field(default_factory=list)


def _drain(stream, sink: deque) -> None:
    """Keep the last STDERR_TAIL_BYTES of a pipe, so a chatty tool can never fill the pipe and block."""
    try:
        reader = getattr(stream, "read1", None) or stream.read
        while True:
            data = reader(8192)
            if not data:
                return
            sink.append(data)
            while sum(len(d) for d in sink) > STDERR_TAIL_BYTES and len(sink) > 1:
                sink.popleft()
    except (OSError, ValueError):
        return


def _kill(proc: subprocess.Popen | None) -> None:
    if proc is not None and proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass


def stream_restore(
    consumer_cmd: list[str],
    *,
    producer_cmd: list[str] | None = None,
    source_file: str | None = None,
    wipe_schema: bool = False,
    env: dict | None = None,
    on_bytes=None,
) -> StreamResult:
    """Run producer -> header filter -> consumer as ONE transaction. Exactly one of producer_cmd / source_file is given.

    The consumer (psql) receives BEGIN, then the optional schema wipe, then the script, then COMMIT only if the producer exited 0
    and its output was read to the end; otherwise ROLLBACK. If the consumer dies first (a SQL error under ON_ERROR_STOP), the
    producer is killed and the open transaction is rolled back by the server when the connection closes."""
    if (producer_cmd is None) == (source_file is None):
        raise ValueError("give exactly one of producer_cmd or source_file")

    consumer = subprocess.Popen(consumer_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    producer = None
    src_handle = None
    try:
        if producer_cmd is not None:
            producer = subprocess.Popen(producer_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            src = producer.stdout
        else:
            src_handle = open(source_file, "rb")
            src = src_handle
    except OSError:
        _kill(consumer)
        raise

    consumer_err: deque = deque()
    producer_err: deque = deque()
    threads = [threading.Thread(target=_drain, args=(consumer.stderr, consumer_err), daemon=True)]
    if producer is not None:
        threads.append(threading.Thread(target=_drain, args=(producer.stderr, producer_err), daemon=True))
    for t in threads:
        t.start()

    result = StreamResult(ok=False, committed_sent=False, producer_returncode=None, consumer_returncode=None)
    consumer_gone = False
    try:
        try:
            consumer.stdin.write(b"BEGIN;\n")
            if wipe_schema:
                consumer.stdin.write(b"DROP SCHEMA public CASCADE;\nCREATE SCHEMA public;\n")
            for chunk in iter_restore_script(src):
                consumer.stdin.write(chunk)
                result.bytes_streamed += len(chunk)
                if on_bytes:
                    on_bytes(result.bytes_streamed)
            producer_rc = producer.wait() if producer is not None else 0
            result.producer_returncode = producer_rc
            if producer_rc == 0:
                consumer.stdin.write(b"COMMIT;\n")
                result.committed_sent = True
            else:
                consumer.stdin.write(b"ROLLBACK;\n")
                result.failure = f"the archive reader (pg_restore) exited {producer_rc}; the transaction was rolled back"
        except (BrokenPipeError, OSError, ValueError):
            consumer_gone = True
        finally:
            try:
                consumer.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
        if consumer_gone:
            _kill(producer)
        result.consumer_returncode = consumer.wait()
        if producer is not None:
            result.producer_returncode = producer.wait()
    finally:
        _kill(consumer)
        _kill(producer)
        if src_handle is not None:
            src_handle.close()
        for t in threads:
            t.join(timeout=5)

    result.consumer_stderr = b"".join(consumer_err).decode(errors="replace")
    result.producer_stderr = b"".join(producer_err).decode(errors="replace")
    if consumer_gone and result.failure is None:
        result.failure = f"psql stopped early (exit {result.consumer_returncode}); nothing was committed"
    elif result.consumer_returncode != 0 and result.failure is None:
        result.failure = f"psql exited {result.consumer_returncode}; nothing was committed"
    result.ok = bool(result.committed_sent and result.producer_returncode == 0 and result.consumer_returncode == 0 and not consumer_gone)
    return result
