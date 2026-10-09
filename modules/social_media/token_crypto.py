"""
Encryption of social account access tokens at rest.

Tokens are encrypted with Fernet (AES-128-CBC with an HMAC) before they are stored and decrypted only inside the
server when a call to Instagram is made. They are never returned by the API, never logged and never sent to the browser.
The key is SOCIAL_TOKEN_ENCRYPTION_KEY (a Fernet key) when set; otherwise one is derived from the server's JWT secret,
so tokens are always encrypted, and rotating that secret makes stored tokens unreadable (the account then has to be
reconnected, which is the safe failure).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class TokenUnreadable(Exception):
    """The stored token can't be decrypted (the key changed or the value is damaged)."""


def _fernet() -> Fernet:
    key = settings.SOCIAL_TOKEN_ENCRYPTION_KEY.strip()
    if key:
        return Fernet(key.encode())
    derived = hashlib.sha256(f"erpx-social-token:{settings.JWT_SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(stored: str) -> str:
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError):
        raise TokenUnreadable("The stored access token can't be read. Reconnect the account.") from None
