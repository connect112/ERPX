"""
API tests for TOTP-based two-factor authentication: setup (QR code +
secret generation), confirm-and-enable, login gating once enabled, and
disable — the full lifecycle described in modules/authentication/service.py.
"""

import pyotp
import pytest

from modules.authentication.repository import AuthRepository

pytestmark = pytest.mark.api


@pytest.fixture
def register_payload():
    return {
        "email": "two.factor.user@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "Two Factor User",
    }


async def _register_verify_login(client, register_payload, db_session) -> dict:
    await client.post("/api/v1/auth/register", json=register_payload)
    user = await AuthRepository(db_session).get_user_by_email(register_payload["email"])
    await AuthRepository(db_session).mark_email_verified(user)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    return login_response.json()


async def test_setup_two_factor_returns_secret_and_qr_code(client, register_payload, db_session):
    tokens = await _register_verify_login(client, register_payload, db_session)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["secret"]
    assert body["otpauth_url"].startswith("otpauth://totp/")
    assert body["qr_code_base64"]


async def test_confirm_two_factor_with_invalid_code_is_rejected(client, register_payload, db_session):
    tokens = await _register_verify_login(client, register_payload, db_session)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post("/api/v1/auth/2fa/setup", headers=headers)
    response = await client.post("/api/v1/auth/2fa/confirm", json={"otp_code": "000000"}, headers=headers)
    assert response.status_code == 422


async def test_confirm_two_factor_with_valid_code_enables_it(client, register_payload, db_session):
    tokens = await _register_verify_login(client, register_payload, db_session)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_response = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    secret = setup_response.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()

    confirm_response = await client.post(
        "/api/v1/auth/2fa/confirm", json={"otp_code": valid_code}, headers=headers
    )
    assert confirm_response.status_code == 200

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["two_factor_enabled"] is True


async def test_login_requires_otp_once_two_factor_enabled(client, register_payload, db_session):
    tokens = await _register_verify_login(client, register_payload, db_session)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_response = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    secret = setup_response.json()["secret"]
    await client.post(
        "/api/v1/auth/2fa/confirm", json={"otp_code": pyotp.TOTP(secret).now()}, headers=headers
    )

    no_otp_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert no_otp_response.status_code == 200
    assert no_otp_response.json() == {"two_factor_required": True}

    wrong_otp_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
            "otp_code": "000000",
        },
    )
    assert wrong_otp_response.status_code == 401

    valid_otp_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
            "otp_code": pyotp.TOTP(secret).now(),
        },
    )
    assert valid_otp_response.status_code == 200
    assert "access_token" in valid_otp_response.json()


async def test_disable_two_factor_requires_valid_code(client, register_payload, db_session):
    tokens = await _register_verify_login(client, register_payload, db_session)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_response = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    secret = setup_response.json()["secret"]
    await client.post(
        "/api/v1/auth/2fa/confirm", json={"otp_code": pyotp.TOTP(secret).now()}, headers=headers
    )

    bad_disable = await client.post(
        "/api/v1/auth/2fa/disable", json={"otp_code": "000000"}, headers=headers
    )
    assert bad_disable.status_code == 422

    good_disable = await client.post(
        "/api/v1/auth/2fa/disable", json={"otp_code": pyotp.TOTP(secret).now()}, headers=headers
    )
    assert good_disable.status_code == 200

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["two_factor_enabled"] is False

    # 2FA is off again — login should no longer require an OTP code.
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()
