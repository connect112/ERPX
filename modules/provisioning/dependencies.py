"""
Provisioning module — HMAC verification for the internal, service-to-service
`POST /api/v1/internal/provisioning/students` endpoint. Not part of the
RBAC-authenticated surface (no user JWT) — the caller (Pentrix-share) proves
its identity by signing the raw request body, mirroring the pattern
Pentrix-share's own Razorpay/Stripe webhook adapters already use to verify
*their* inbound webhooks (see that repo's `backend/app/payments/
stripe_adapter.py`, whose `timestamp + "." + body` construction this
mirrors exactly, byte for byte, so both sides compute the same signature).

Scheme: `X-ERPX-Timestamp` (unix seconds) + `X-ERPX-Signature` (hex
HMAC-SHA256 of `f"{timestamp}.{raw_body}"`, keyed by
`settings.ERPX_INTERNAL_SERVICE_SECRET`). A 5-minute replay window on the
timestamp mirrors Stripe's own webhook-signature scheme.
"""

import hashlib
import hmac
import time

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_REPLAY_WINDOW_SECONDS = 300


async def verify_internal_signature(request: Request) -> None:
    if not settings.ERPX_INTERNAL_SERVICE_SECRET:
        # Fail closed: an unconfigured secret must never be treated as "no
        # verification required" — see app/core/config.py's comment on the
        # setting for why this isn't also a boot-time refusal.
        raise AuthenticationError("Internal provisioning is not configured on this instance.")

    signature = request.headers.get("X-ERPX-Signature")
    timestamp_header = request.headers.get("X-ERPX-Timestamp")
    if not signature or not timestamp_header:
        raise AuthenticationError("Missing X-ERPX-Signature/X-ERPX-Timestamp headers.")

    try:
        timestamp = int(timestamp_header)
    except ValueError as exc:
        raise AuthenticationError("X-ERPX-Timestamp must be a unix timestamp.") from exc

    if abs(time.time() - timestamp) > _REPLAY_WINDOW_SECONDS:
        raise AuthenticationError("X-ERPX-Timestamp is outside the allowed window.")

    # `request.body()` is cached by Starlette after the first read, so this
    # doesn't interfere with FastAPI's own separate parsing of the body into
    # the route's Pydantic model — both reads see the same bytes.
    body = await request.body()
    signed_payload = f"{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        settings.ERPX_INTERNAL_SERVICE_SECRET.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationError("Invalid signature.")
