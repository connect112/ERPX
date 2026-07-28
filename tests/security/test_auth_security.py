"""
Targeted security assertions: JWT integrity, token-type confusion,
password never leaking through the API, and basic injection-style input
being treated as inert data rather than executed.
"""

import pytest
from jose import jwt as pyjwt

from app.core.config import settings

pytestmark = [pytest.mark.security, pytest.mark.api]


async def test_tampered_jwt_signature_is_rejected(client, auth_headers):
    token = auth_headers["Authorization"].split(" ")[1]
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


async def test_jwt_signed_with_wrong_secret_is_rejected(client, superuser):
    user, _ = superuser
    forged = pyjwt.encode(
        {"sub": str(user.id), "type": "access"}, "not-the-real-secret-key", algorithm=settings.JWT_ALGORITHM
    )
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_access_token(client, superuser):
    """A refresh token has type=refresh; using it against an access-token-only endpoint must fail."""
    from app.core.security import create_refresh_token

    user, _ = superuser
    refresh_token = create_refresh_token(str(user.id))

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


async def test_expired_access_token_is_rejected(client, superuser):
    from datetime import datetime, timedelta, timezone

    user, _ = superuser
    expired_payload = {
        "sub": str(user.id),
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = pyjwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


async def test_password_never_returned_in_registration_response(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "no.leak@erpx.example.com", "password": "StrongPass1!", "full_name": "No Leak"},
    )
    body = response.json()
    serialized = str(body)
    assert "password" not in body
    assert "hashed_password" not in body
    assert "StrongPass1!" not in serialized


async def test_password_never_returned_from_me_endpoint(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


async def test_sql_metacharacters_in_search_are_treated_as_literal_text(client, auth_headers):
    """Parameterized queries mean a SQL-injection-style search string is just an unmatched literal, not an error or a bypass."""
    response = await client.get(
        "/api/v1/crm/leads", params={"search": "' OR '1'='1"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
