"""
Live Classes module — self-hosted Jitsi Meet integration.

Every LiveClass gets its own Jitsi room, auto-provisioned (no external
scheduling API call — a room simply exists the moment someone with a
valid token joins it) and access-controlled via short-lived per-user
JWTs that Prosody's token auth plugin on the Jitsi server verifies
against the same shared secret (settings.JITSI_APP_SECRET). See
infrastructure/aws-single-host for the dedicated Jitsi EC2 instance this
talks to — a separate box from the main ERPX host, since the JVB media
bridge needs real CPU headroom for relaying live audio/video.
"""

import time
import uuid

from jose import jwt

from app.core.config import settings


def jitsi_enabled() -> bool:
    """False in local dev / every test run (JITSI_PUBLIC_URL unset) — live
    classes then fall back to a trainer-supplied external meeting_link
    instead of an auto-provisioned room."""
    return bool(settings.JITSI_PUBLIC_URL and settings.JITSI_APP_SECRET)


def build_room_name(live_class_id: uuid.UUID) -> str:
    # Hex (no dashes) keeps this a single unguessable URL-safe token —
    # Jitsi room names are otherwise unrestricted, but dashes/underscores
    # in some older client versions have been a source of subtle join bugs.
    return f"erpx-{live_class_id.hex}"


def build_meeting_link(live_class_id: uuid.UUID) -> str:
    return f"{settings.JITSI_PUBLIC_URL}/{build_room_name(live_class_id)}"


def mint_join_token(
    live_class_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    email: str | None,
    moderator: bool,
) -> str:
    """A short-lived, room-scoped JWT granting one specific user access to
    one specific live class's Jitsi room — minted fresh on every join
    request (see the /join-token routes below), never stored anywhere.
    `moderator` drives Jitsi's own in-call moderator UI (mute-others,
    kick, end-for-all): true for the trainer teaching that batch, false
    for a student — the caller has already done that ownership check
    before calling this.
    """
    now = int(time.time())
    payload = {
        "iss": settings.JITSI_APP_ID,
        "aud": settings.JITSI_APP_ID,
        "sub": jitsi_domain(),
        "room": build_room_name(live_class_id),
        "iat": now,
        "exp": now + settings.JITSI_TOKEN_EXPIRE_MINUTES * 60,
        "context": {
            "user": {
                "id": str(user_id),
                "name": name,
                "email": email or "",
                "moderator": moderator,
            }
        },
    }
    return jwt.encode(payload, settings.JITSI_APP_SECRET, algorithm="HS256")


def jitsi_domain() -> str:
    # settings.JITSI_PUBLIC_URL is e.g. "https://meet.pentrix.in" — but
    # Prosody's virtual host (and hence the `sub` claim it expects, and
    # the `domain` the frontend's IFrame API needs) is just the bare
    # hostname.
    return settings.JITSI_PUBLIC_URL.split("//", 1)[-1].rstrip("/")
