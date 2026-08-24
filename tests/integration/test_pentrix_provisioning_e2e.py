"""
End-to-end verification of the full Pentrix-share -> ERPX provisioning
chain (Task 5). Spans what would otherwise be two separate process
boundaries:

  1. Pentrix-share's own webhook -> HMAC-signed call to this endpoint is
     covered on that side by
     backend/tests/test_erpx_provisioning.py::test_successful_webhook_calls_erpx_exactly_once_and_creates_enrollment
     (that repo's test suite, not this one) — it mocks
     ERPXProvisioningClient.provision_student and asserts exactly one call
     with the right payload shape. This file picks up from there: given a
     correctly-signed request arrives at ERPX's provisioning endpoint (the
     real HTTP boundary, per tests/README.md's "mock the HTTP boundary if
     running both stacks in CI isn't practical" — spinning up a second
     Flask process from ERPX's own pytest run isn't practical or
     necessary; driving the endpoint directly with a real signed request
     exercises the exact same server-side code path a genuine call would),
     asserts ERPX ends up in the right state end-to-end:

  2. Provisioning creates a User with exactly the `student` role, a
     Student record, and a course Enrollment (re-asserted here as part of
     the full chain, not just in isolation — see test_provisioning.py for
     the endpoint's own focused unit coverage).

  3. That student's JWT then actually behaves like a student everywhere
     Task 1 touched: 200 on their own pentrix data, 403 on an
     administrative module, and 403 (not silently empty / not a leak) when
     trying to read a *different* student's pentrix data via the
     ownership check added in modules/pentrix/common/dependencies.py.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from modules.authorization.repository import AuthorizationRepository
from modules.courses.repository import CourseRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.organizations.repository import OrganizationRepository
from modules.provisioning.service import PENTRIX_ORG_SLUG
from modules.students.repository import StudentRepository

pytestmark = [pytest.mark.integration, pytest.mark.security]

_SECRET = "e2e-test-internal-secret"
_COURSE_SLUG = "pentrix-program"
PROVISIONING_URL = "/api/v1/internal/provisioning/students"


@pytest.fixture
def internal_secret(monkeypatch):
    monkeypatch.setattr(settings, "ERPX_INTERNAL_SERVICE_SECRET", _SECRET)
    return _SECRET


@pytest.fixture
async def pentrix_program(db_session):
    """Same seed shape as apps/api/scripts/seed.py::seed_pentrix_program(),
    against this test's own transactional session — see test_provisioning.py
    for why the real script isn't invoked directly here."""
    org = await OrganizationRepository(db_session).create(
        name="GIR Technologies / Pentrix Program", slug=PENTRIX_ORG_SLUG
    )
    course = await CourseRepository(db_session).create(
        organization_id=org.id, title="Pentrix Cyber Range Program", slug=_COURSE_SLUG, is_published=True
    )
    await db_session.flush()
    return org, course


def _signed_provisioning_request(payload: dict, secret: str) -> tuple[bytes, dict]:
    """Mirrors Pentrix-share's app/services/erpx_provisioning_client.py
    construction exactly — this is the real cross-repo contract, not a
    simplified stand-in for it."""
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-ERPX-Timestamp": timestamp,
        "X-ERPX-Signature": signature,
    }
    return body, headers


def _provisioning_payload(**overrides) -> dict:
    base = {
        "full_name": "E2E Pentrix Student",
        "email": f"e2e.pentrix.{uuid.uuid4().hex[:8]}@example.com",
        "phone": "+919999999999",
        "program_code": _COURSE_SLUG,
        "payment_reference": f"pay_e2e_{uuid.uuid4().hex[:12]}",
        "amount_paise": 4999900,
        "paid_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


async def _provision_student(client, internal_secret, **payload_overrides) -> uuid.UUID:
    body, headers = _signed_provisioning_request(_provisioning_payload(**payload_overrides), internal_secret)
    response = await client.post(PROVISIONING_URL, content=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "created"
    return uuid.UUID(response.json()["user_id"])


async def test_pentrix_payment_to_scoped_erpx_access_end_to_end(
    client, db_session, rbac_seeded, internal_secret, pentrix_program
):
    org, course = pentrix_program

    # ---- Step 1: the provisioning call Pentrix-share's webhook makes ----
    user_id = await _provision_student(client, internal_secret)

    # ---- Step 2: ERPX ends up with exactly a student, nothing more ----
    roles = await AuthorizationRepository(db_session).get_roles_for_user(user_id)
    assert [r.slug for r in roles] == ["student"]

    student = await StudentRepository(db_session).get_by_user_id(user_id)
    assert student is not None
    assert student.organization_id == org.id

    enrollments = await EnrollmentRepository(db_session).list_for_student(student.id)
    assert [e.course_id for e in enrollments] == [course.id]

    # ---- Step 3: that student's JWT behaves exactly like a student ----
    headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}

    # Own domain: 200.
    assert (await client.get("/api/v1/pentrix/labs", headers=headers)).status_code == 200
    assert (
        await client.get(f"/api/v1/pentrix/students/{student.id}/instances", headers=headers)
    ).status_code == 200

    # Administrative module: 403, not a silent empty list.
    assert (await client.get("/api/v1/crm/leads", headers=headers)).status_code == 403
    # Org-wide roster: also 403 — a student browsing every student.
    assert (await client.get("/api/v1/students", headers=headers)).status_code == 403

    # ---- Step 4: cannot reach a *different* student's Pentrix data ----
    other_user_id = await _provision_student(client, internal_secret)
    other_student = await StudentRepository(db_session).get_by_user_id(other_user_id)
    assert other_student is not None
    assert other_student.id != student.id

    forbidden = await client.get(
        f"/api/v1/pentrix/students/{other_student.id}/instances", headers=headers
    )
    assert forbidden.status_code == 403
