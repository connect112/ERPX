"""
API tests for the internal, service-to-service provisioning endpoint
(`POST /api/v1/internal/provisioning/students`) — the hook Pentrix-share
calls on a PROGRAM_FEE payment success (Task 3, in the Pentrix-share repo)
to get a paying student a scoped ERPX account.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import date, datetime, timezone

import pytest

from app.core.config import settings
from modules.authorization.repository import AuthorizationRepository
from modules.courses.repository import CourseRepository
from modules.organizations.repository import OrganizationRepository
from modules.provisioning.service import PENTRIX_ORG_SLUG
from modules.users.repository import UserProfileRepository

pytestmark = [pytest.mark.api, pytest.mark.security]

_SECRET = "test-internal-secret"
_COURSE_SLUG = "pentrix-program"


@pytest.fixture
def internal_secret(monkeypatch):
    monkeypatch.setattr(settings, "ERPX_INTERNAL_SERVICE_SECRET", _SECRET)
    return _SECRET


@pytest.fixture
async def pentrix_program(db_session):
    """Seeds the fixed org/course the endpoint resolves `program_code`
    against, mirroring apps/api/scripts/seed.py::seed_pentrix_program()
    directly against the test's own transactional session (rather than
    running the real script against a separate connection — see
    tests/README.md's isolation model)."""
    org = await OrganizationRepository(db_session).create(
        name="GIR Technologies / Pentrix Program", slug=PENTRIX_ORG_SLUG
    )
    course = await CourseRepository(db_session).create(
        organization_id=org.id, title="Pentrix Cyber Range Program", slug=_COURSE_SLUG, is_published=True
    )
    await db_session.flush()
    return org, course


def _signed_request(payload: dict, secret: str, *, timestamp: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode("utf-8")
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.{body.decode('utf-8')}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-ERPX-Timestamp": str(ts),
        "X-ERPX-Signature": signature,
    }
    return body, headers


def _payload(**overrides) -> dict:
    base = {
        "full_name": "Pentrix Student",
        "email": f"pentrix.{uuid.uuid4().hex[:8]}@example.com",
        "phone": "+919999999999",
        "program_code": _COURSE_SLUG,
        "payment_reference": f"pay_{uuid.uuid4().hex[:12]}",
        "amount_paise": 4999900,
        "paid_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


URL = "/api/v1/internal/provisioning/students"


async def test_successful_provisioning_creates_user_with_exactly_student_role(
    client, db_session, rbac_seeded, internal_secret, pentrix_program
):
    payload = _payload()
    body, headers = _signed_request(payload, internal_secret)

    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "created"
    assert data["login_url"] == f"{settings.STUDENT_PORTAL_URL}/login"
    user_id = uuid.UUID(data["user_id"])

    # No password anywhere in the response.
    assert "password" not in response.text.lower()

    roles = await AuthorizationRepository(db_session).get_roles_for_user(user_id)
    assert [r.slug for r in roles] == ["student"]

    profile = await UserProfileRepository(db_session).get_by_user_id(user_id)
    assert profile is not None
    assert profile.external_reference == payload["payment_reference"]


async def test_duplicate_payment_reference_does_not_duplicate_the_user(
    client, db_session, rbac_seeded, internal_secret, pentrix_program
):
    payload = _payload()

    body1, headers1 = _signed_request(payload, internal_secret)
    first = await client.post(URL, content=body1, headers=headers1)
    assert first.status_code == 200
    assert first.json()["status"] == "created"
    user_id = first.json()["user_id"]

    body2, headers2 = _signed_request(payload, internal_secret)
    second = await client.post(URL, content=body2, headers=headers2)
    assert second.status_code == 200
    assert second.json()["status"] == "already_exists"
    assert second.json()["user_id"] == user_id


async def test_unknown_program_code_fails_clearly(client, rbac_seeded, internal_secret, pentrix_program):
    payload = _payload(program_code="not-a-real-program")
    body, headers = _signed_request(payload, internal_secret)

    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 422
    assert "not-a-real-program" in response.text


async def test_missing_org_or_course_fails_clearly_without_pentrix_program_seeded(
    client, rbac_seeded, internal_secret
):
    payload = _payload()
    body, headers = _signed_request(payload, internal_secret)

    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 422
    assert PENTRIX_ORG_SLUG in response.text


async def test_missing_student_role_fails_clearly(client, rbac_seeded, internal_secret, pentrix_program):
    # `rbac_seeded` is used (unlike the org/course case above) because
    # seed_default_rbac() is idempotent, real system data — once any test
    # in this suite has genuinely committed it (see
    # test_provisioning_atomicity.py, which must actually commit to
    # exercise real rollback), it stays seeded in the shared test database
    # for good, so "the role doesn't exist anywhere in the DB" is not a
    # reliably reproducible precondition to test against. Patching the
    # lookup directly exercises the same code path deterministically.
    from unittest.mock import patch

    payload = _payload()
    body, headers = _signed_request(payload, internal_secret)

    with patch(
        "modules.provisioning.service.AuthorizationRepository.get_role_by_slug", return_value=None
    ):
        response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 422
    assert "student" in response.text.lower()


async def test_missing_signature_headers_rejected(client, rbac_seeded, internal_secret, pentrix_program):
    body = json.dumps(_payload()).encode("utf-8")
    response = await client.post(URL, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 401


async def test_bad_signature_rejected(client, rbac_seeded, internal_secret, pentrix_program):
    body, headers = _signed_request(_payload(), "wrong-secret")
    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 401


async def test_stale_timestamp_rejected(client, rbac_seeded, internal_secret, pentrix_program):
    stale = int(time.time()) - 600  # 10 minutes ago, outside the 5-minute window
    body, headers = _signed_request(_payload(), internal_secret, timestamp=stale)
    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 401


async def test_unconfigured_secret_fails_closed(client, rbac_seeded, pentrix_program):
    # internal_secret fixture deliberately NOT used — ERPX_INTERNAL_SERVICE_SECRET
    # stays at its empty default. A request signed with *some* secret must
    # still be rejected, never treated as "no verification configured, allow it."
    body, headers = _signed_request(_payload(), "any-secret-the-caller-happens-to-use")
    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 401


async def test_email_already_used_by_another_account_fails_clearly(
    client, db_session, organization, rbac_seeded, internal_secret, pentrix_program
):
    from modules.authentication.repository import AuthRepository
    from app.core.security import hash_password

    existing_email = f"existing.{uuid.uuid4().hex[:8]}@example.com"
    await AuthRepository(db_session).create_user(
        email=existing_email, hashed_password=hash_password("Whatever1!"), full_name="Existing User"
    )
    await db_session.flush()

    body, headers = _signed_request(_payload(email=existing_email), internal_secret)
    response = await client.post(URL, content=body, headers=headers)
    assert response.status_code == 409
