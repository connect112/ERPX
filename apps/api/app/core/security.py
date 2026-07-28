"""
Core cryptographic utilities: password hashing and JWT issuance/verification.

The Authentication module (modules/authentication) builds its endpoints
on top of these primitives rather than reimplementing crypto logic, so
there is exactly one place where token structure and hashing algorithm
can be audited or rotated.
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    subject: str,
    token_type: TokenType,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    if token_type == TokenType.ACCESS:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    return create_token(subject, TokenType.ACCESS, extra_claims)


def create_refresh_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    return create_token(subject, TokenType.REFRESH, extra_claims)


class TokenPayloadError(Exception):
    """Raised when a JWT is malformed, expired, or has the wrong type."""


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise TokenPayloadError(f"Invalid token: {exc}") from exc

    if payload.get("type") != expected_type.value:
        raise TokenPayloadError(
            f"Expected token type '{expected_type.value}', got '{payload.get('type')}'"
        )

    return payload
