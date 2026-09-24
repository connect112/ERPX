"""
API tests for GET /users (the "team members" admin screen) — a
self-service-provisioned Pentrix student also gets a UserProfile so
tenant-scoping dependencies resolve for them (see modules/provisioning),
but they're not a "team member" the way an employee/admin is. The
dedicated Students module/page is where student rosters belong, so this
list must exclude them — see modules/users/repository.py's
list_with_users_for_organization.
"""

import uuid
from datetime import date

import pytest

from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def test_users_list_excludes_students(client, db_session, organization, auth_headers):
    """A student with a UserProfile in this org must not appear in
    GET /users, even though a plain staff member with no special role
    does."""
    auth_repo = AuthRepository(db_session)
    profile_repo = UserProfileRepository(db_session)

    unique = uuid.uuid4().hex[:8]

    staff_user = await auth_repo.create_user(
        email=f"team-member.{unique}@erpx.example.com",
        hashed_password="x",
        full_name="Real Team Member",
    )
    staff_user.status = UserStatus.ACTIVE
    staff_user.is_email_verified = True
    await db_session.flush()
    await profile_repo.create(user_id=staff_user.id, organization_id=organization.id)

    student_user = await auth_repo.create_user(
        email=f"provisioned-student.{unique}@erpx.example.com",
        hashed_password="x",
        full_name="Provisioned Student",
    )
    student_user.status = UserStatus.ACTIVE
    student_user.is_email_verified = True
    await db_session.flush()
    await profile_repo.create(user_id=student_user.id, organization_id=organization.id)
    await StudentRepository(db_session).create(
        organization.id,
        user_id=student_user.id,
        full_name="Provisioned Student",
        course_name="Pentrix Program",
        enrollment_date=date(2026, 1, 1),
    )
    await db_session.flush()

    response = await client.get("/api/v1/users", headers=auth_headers)
    assert response.status_code == 200, response.text
    emails = [row["email"] for row in response.json()]

    assert staff_user.email in emails
    assert student_user.email not in emails
