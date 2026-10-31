"""
Optional virus scanning of student uploads through a ClamAV daemon (clamd ``INSTREAM``), off unless ``CLAMAV_ENABLED``.

Off: files are only type-checked by their content and recorded as ``not_scanned``; nothing says they were scanned.
On: every upload is streamed to clamd before it is stored. An infected file is refused, and so is every upload while the
scanner cannot be reached or answers with an error (fail closed), so an unscanned file is never recorded as clean.
"""

import asyncio
import contextlib
import logging
import struct

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)

NOT_SCANNED, CLEAN = "not_scanned", "clean"
_CHUNK = 64 * 1024


class ScanError(Exception):
    pass


async def clamd_instream(host: str, port: int, data: bytes, timeout: float) -> str:
    """Send ``data`` to clamd and return its reply, e.g. ``stream: OK`` or ``stream: <signature> FOUND``."""

    async def run() -> bytes:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(b"zINSTREAM\0")
            for start in range(0, len(data), _CHUNK):
                chunk = data[start : start + _CHUNK]
                writer.write(struct.pack(">I", len(chunk)) + chunk)
                await writer.drain()
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            return await reader.readuntil(b"\0")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    try:
        reply = await asyncio.wait_for(run(), timeout)
    except (OSError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        raise ScanError(type(exc).__name__) from exc
    return reply.rstrip(b"\0").decode(errors="replace").strip()


async def scan(data: bytes, what: str) -> str:
    """The scan status to record for an upload, or an error that refuses it."""
    if not settings.CLAMAV_ENABLED:
        return NOT_SCANNED
    try:
        reply = await clamd_instream(settings.CLAMAV_HOST, settings.CLAMAV_PORT, data, settings.CLAMAV_TIMEOUT_SECONDS)
    except ScanError as exc:
        logger.error("Virus scanner unreachable (%s); refusing %s upload", exc, what)
        raise ServiceUnavailableError("Files cannot be checked for viruses right now. Try again in a few minutes.") from None
    if reply.endswith(" OK"):
        return CLEAN
    if reply.endswith(" FOUND"):
        logger.warning("Virus scanner refused a %s upload: %s", what, reply[:200])
        raise ValidationError("The virus scanner flagged this file, so it was not uploaded.")
    logger.error("Virus scanner error on a %s upload: %s", what, reply[:200])
    raise ServiceUnavailableError("Files cannot be checked for viruses right now. Try again in a few minutes.")
