"""
Live classes module — HMAC verification for the self-hosted Jitsi
recording server's finalize script, which calls
`POST /api/v1/live-classes/recording-webhook` once a recording has been
uploaded. Not part of the RBAC-authenticated surface (no user JWT) — the
caller proves its identity by signing the raw request body.

Deliberately a separate secret/dependency from
modules/provisioning/dependencies.py's verify_internal_signature rather
than reusing it: that one trusts Pentrix-share, this one trusts a
different external system (the Jitsi box's finalize script), and the two
shouldn't share a blast radius if either secret leaks. Otherwise the
exact same scheme: `X-Jibri-Timestamp` (unix seconds) + `X-Jibri-Signature`
(hex HMAC-SHA256 of `f"{timestamp}.{raw_body}"`, keyed by
settings.JIBRI_WEBHOOK_SECRET), 5-minute replay window.
"""

import hashlib
import hmac
import time

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_REPLAY_WINDOW_SECONDS = 300


async def verify_jibri_signature(request: Request) -> None:
    if not settings.JIBRI_WEBHOOK_SECRET:
        # Fail closed: an unconfigured secret must never be treated as "no
        # verification required".
        raise AuthenticationError("The recording webhook is not configured on this instance.")

    signature = request.headers.get("X-Jibri-Signature")
    timestamp_header = request.headers.get("X-Jibri-Timestamp")
    if not signature or not timestamp_header:
        raise AuthenticationError("Missing X-Jibri-Signature/X-Jibri-Timestamp headers.")

    try:
        timestamp = int(timestamp_header)
    except ValueError as exc:
        raise AuthenticationError("X-Jibri-Timestamp must be a unix timestamp.") from exc

    if abs(time.time() - timestamp) > _REPLAY_WINDOW_SECONDS:
        raise AuthenticationError("X-Jibri-Timestamp is outside the allowed window.")

    body = await request.body()
    signed_payload = f"{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        settings.JIBRI_WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationError("Invalid signature.")
