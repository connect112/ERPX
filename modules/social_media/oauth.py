"""
Connecting an Instagram professional account ("Instagram API with Instagram Login" business login).

The flow, from Meta's documentation: send the person to Instagram's authorize page with our app id, a redirect address and
the permissions we want; Instagram sends them back with a one-hour, single-use `code`; the server exchanges the code (with the
app secret) for a short-lived token, then for a long-lived (about 60 days) one, which is stored encrypted and refreshed before
it expires. Nothing here runs in the browser, and the app secret and tokens never leave the server.

Meta's token endpoints take secrets in the query string, so the HTTP client's request logging is made to redact them.

Not yet exercised against a live Meta app; response shapes are read defensively (the docs show the short-lived answer as a
`data` array, older descriptions as a flat object).
"""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWTError

from app.core.config import settings
from app.core.exceptions import ValidationError

STATE_AUDIENCE = "social-connect"
STATE_LIFETIME = timedelta(minutes=10)
TIMEOUT = 30.0
PROFESSIONAL_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}

_SECRET_PARAMS = re.compile(r"((?:access_token|client_secret|code|fb_exchange_token)=)[^&\s\"']+", re.IGNORECASE)


class _Redact(logging.Filter):
    """Removes tokens, codes and secrets from the URLs the HTTP client logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_SECRET_PARAMS.sub(r"\1[redacted]", str(a)) if isinstance(a, (str, httpx.URL)) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = _SECRET_PARAMS.sub(r"\1[redacted]", record.msg)
        return True


for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).addFilter(_Redact())


class OAuthError(Exception):
    """Something in the connection went wrong. `code` is a short word for the screen; `message` is safe to show."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def configured() -> bool:
    return bool(settings.INSTAGRAM_APP_ID and settings.INSTAGRAM_APP_SECRET)


def scopes() -> list[str]:
    return [s.strip() for s in settings.INSTAGRAM_SCOPES.split(",") if s.strip()]


def redirect_uri() -> str:
    return settings.INSTAGRAM_REDIRECT_URI.strip() or f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/social-media/connect/callback"


def webhook_url() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/social-media/webhooks/instagram"


# ---------------- state: ties the redirect back to the person who started it ----------------


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def make_state(organization_id: str, user_id: str, nonce: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    claims = {"org": organization_id, "user": user_id, "nonce": nonce, "aud": STATE_AUDIENCE, "exp": now + STATE_LIFETIME}
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm="HS256")


def read_state(state: str) -> dict:
    try:
        return jwt.decode(state, settings.JWT_SECRET_KEY, algorithms=["HS256"], audience=STATE_AUDIENCE)
    except PyJWTError:
        raise OAuthError("state", "This connection link has expired or isn't valid. Start the connection again.") from None


def authorize_url(state: str) -> str:
    query = {
        "client_id": settings.INSTAGRAM_APP_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": ",".join(scopes()),
        "state": state,
        "force_reauth": "true",
    }
    return f"{settings.INSTAGRAM_AUTHORIZE_URL}?{urlencode(query)}"


def clean_code(code: str) -> str:
    """Instagram appends '#_' to the code in the redirect; it is not part of the code."""
    return code.strip().removesuffix("#_").removesuffix("#")


# ---------------- tokens ----------------


async def _call(method: str, url: str, *, data: dict | None = None, params: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(method, url, data=data, params=params)
    except httpx.HTTPError:
        raise OAuthError("network", "Instagram couldn't be reached. Try again in a moment.") from None
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        error = body.get("error") if isinstance(body, dict) else None
        detail = ""
        if isinstance(error, dict):
            detail = str(error.get("message") or "")
        elif isinstance(body, dict):
            detail = str(body.get("error_message") or body.get("error_description") or "")
        # Never echo the provider's text back unscrubbed: it can quote our request.
        detail = _SECRET_PARAMS.sub(r"\1[redacted]", detail)[:200]
        raise OAuthError("exchange", f"Instagram refused the request{(': ' + detail) if detail else '.'}")
    if not isinstance(body, dict):
        raise OAuthError("exchange", "Instagram's answer couldn't be read.")
    return body


def _permissions(value: object) -> list[str]:
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, list):
        return [str(p).strip() for p in value if str(p).strip()]
    return []


async def exchange_code(code: str) -> tuple[str, str, list[str]]:
    """(short-lived token, Instagram user id, permissions granted) for the code Instagram sent back."""
    body = await _call(
        "POST",
        settings.INSTAGRAM_TOKEN_URL,
        data={
            "client_id": settings.INSTAGRAM_APP_ID,
            "client_secret": settings.INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(),
            "code": clean_code(code),
        },
    )
    entry = body["data"][0] if isinstance(body.get("data"), list) and body["data"] else body
    token, user_id = entry.get("access_token"), entry.get("user_id")
    if not token or not user_id:
        raise OAuthError("exchange", "Instagram's answer didn't include an access token.")
    return str(token), str(user_id), _permissions(entry.get("permissions"))


def _graph(path: str) -> str:
    return f"{settings.INSTAGRAM_GRAPH_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


async def long_lived(short_token: str) -> tuple[str, int]:
    """(long-lived token, seconds until it expires). Done on the server because it uses the app secret."""
    body = await _call(
        "GET",
        _graph("access_token"),
        params={"grant_type": "ig_exchange_token", "client_secret": settings.INSTAGRAM_APP_SECRET, "access_token": short_token},
    )
    return _token_and_expiry(body)


async def refresh(token: str) -> tuple[str, int]:
    """A fresh 60-day token for one that is at least a day old and not yet expired."""
    body = await _call("GET", _graph("refresh_access_token"), params={"grant_type": "ig_refresh_token", "access_token": token})
    return _token_and_expiry(body)


def _token_and_expiry(body: dict) -> tuple[str, int]:
    token, expires = body.get("access_token"), body.get("expires_in")
    if not token or not isinstance(expires, int) or expires <= 0:
        raise OAuthError("exchange", "Instagram's answer didn't include a usable token.")
    return str(token), expires


def check_professional(account_type: str | None) -> None:
    if (account_type or "").upper() not in PROFESSIONAL_TYPES:
        raise ValidationError("This Instagram account isn't a Professional account. Switch it to Business or Creator in the Instagram app, then connect again.")
