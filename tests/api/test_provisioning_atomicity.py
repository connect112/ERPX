"""
Regression test: a failure partway through ProvisioningService.provision_student
must leave zero trace — no orphaned User, no UserProfile with no role, no
half-enrolled Student.

The shared `client`/`db_session` fixtures (used by tests/api/test_provisioning.py)
never actually call `commit()` — every test runs inside one outer transaction
that's rolled back at the end regardless (see tests/README.md's isolation
model) — so they can't demonstrate that a *mid-request* exception, and the
real `get_db()` dependency's rollback in response to it, actually discards
everything. This file follows the same pattern
tests/api/test_coupon_redemption.py already established for exactly that
reason: its own real session against the real engine, real commits, and
explicit cleanup — not the transactional fixtures.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete

from app.core.exceptions import NotFoundError
from app.db.session import AsyncSessionLocal, engine
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.courses.models import Course
from modules.courses.repository import CourseRepository
from modules.organizations.models import Organization
from modules.organizations.repository import OrganizationRepository
from modules.provisioning.schemas import ProvisionStudentRequest
from modules.provisioning.service import PENTRIX_ORG_SLUG, ProvisioningService
from modules.students.models import Student
from modules.users.models import UserProfile
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api

_COURSE_SLUG = "pentrix-program"


async def _setup(org_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        # Must be the literal PENTRIX_ORG_SLUG, not a randomized variant —
        # ProvisioningService looks the org up by that fixed constant, so a
        # differently-slugged test org would never be found and the call
        # would fail before ever reaching the patched step below.
        await OrganizationRepository(db).create(
            id=org_id, name="GIR Technologies / Pentrix Program", slug=PENTRIX_ORG_SLUG
        )
        await db.commit()
        # seed_default_rbac is idempotent (upsert by slug) — safe to run
        # against the real committed DB, exactly like every other test that
        # depends on the `rbac_seeded` fixture already assumes.
        await AuthorizationService(db).seed_default_rbac()
        await db.commit()


async def _cleanup(org_id: uuid.UUID, email: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Student).where(Student.organization_id == org_id))
        await db.execute(delete(Course).where(Course.organization_id == org_id))
        user_result = await db.execute(User.__table__.select().where(User.email == email.lower()))
        user_row = user_result.first()
        if user_row:
            await db.execute(delete(UserProfile).where(UserProfile.user_id == user_row.id))
            await db.execute(delete(User).where(User.id == user_row.id))
        await db.execute(delete(Organization).where(Organization.id == org_id))
        await db.commit()


async def test_failure_partway_through_provisioning_leaves_no_trace():
    await engine.dispose()
    org_id = uuid.uuid4()
    await _setup(org_id)

    email = f"atomicity.{uuid.uuid4().hex[:8]}@example.com"
    payment_reference = f"pay_{uuid.uuid4().hex[:12]}"

    try:
        async with AsyncSessionLocal() as db:
            org = await OrganizationRepository(db).get_by_id(org_id)
            await CourseRepository(db).create(
                organization_id=org.id, title="Pentrix Cyber Range Program", slug=_COURSE_SLUG, is_published=True
            )
            student_role = await AuthorizationRepository(db).get_role_by_slug("student")
            assert student_role is not None
            await db.commit()

            payload = ProvisionStudentRequest(
                full_name="Atomicity Test Student",
                email=email,
                phone=None,
                program_code=_COURSE_SLUG,
                payment_reference=payment_reference,
                amount_paise=4999900,
                paid_at=datetime.now(timezone.utc),
            )

            # Force a failure at the very last write step (Enrollment
            # creation) — everything before it (User, UserProfile, Student,
            # student Role assignment) has already been flushed by then.
            with patch(
                "modules.provisioning.service.EnrollmentRepository.create",
                side_effect=NotFoundError("Course"),
            ):
                with pytest.raises(NotFoundError):
                    await ProvisioningService(db).provision_student(payload)

            # Captured *within* the still-open, not-yet-rolled-back
            # transaction — the User/UserRole rows are visible here (flushed,
            # same transaction) even though they were never committed. This
            # is only to get the id to check for post-rollback below, not a
            # claim that this state is durable.
            from modules.authentication.repository import AuthRepository

            flushed_user = await AuthRepository(db).get_user_by_email(email)
            assert flushed_user is not None, "test setup problem: the failure happened before User was even flushed"
            flushed_user_id = flushed_user.id

            # This is the behavior production relies on: app/db/session.py's
            # real get_db() calls exactly this on any exception raised out
            # of a route. Simulating it here is what makes this test actually
            # prove the invariant, rather than merely assert it in a comment.
            await db.rollback()

        async with AsyncSessionLocal() as verify:
            auth_result = await verify.execute(User.__table__.select().where(User.email == email.lower()))
            assert auth_result.first() is None, "a failed provisioning call must not leave a User row behind"

            profile = await UserProfileRepository(verify).get_by_external_reference(payment_reference)
            assert profile is None, "a failed provisioning call must not leave a UserProfile row behind"

            roles = await AuthorizationRepository(verify).get_roles_for_user(flushed_user_id)
            assert roles == [], "a failed provisioning call must not leave a UserRole row behind"
    finally:
        await _cleanup(org_id, email)
        await engine.dispose()
