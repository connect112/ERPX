"""
GET /api/v1/lms/progress/{student_id}/course/{course_id}: a student reads only their own progress.

The Student role holds ``lms.progress.view``, and the route used to check only that permission, so any student could read any other student's lesson
progress (an insecure direct object reference). Now: the student themself, a superuser, or staff holding ``lms.progress.manage`` may read; everyone
else gets 403; a student of another organization is never returned; no or an invalid login fails closed. Synthetic data only.
"""

import uuid
from datetime import date

import pytest

from modules.organizations.repository import OrganizationRepository
from modules.students.models import Student
from tests.api.test_course_content_access import a_course, student_with_role
from tests.api.test_email_studio import user_with

pytestmark = pytest.mark.api


def url(student, course):
    return f"/api/v1/lms/progress/{student.id}/course/{course.id}"


async def world(client, db, organization):
    a, a_headers = await student_with_role(client, db, organization)
    b, b_headers = await student_with_role(client, db, organization)
    course, _, _ = await a_course(db, organization)
    return a, a_headers, b, b_headers, course


async def test_a_student_reads_their_own_progress(client, db_session, organization, rbac_seeded):
    a, a_headers, _, _, course = await world(client, db_session, organization)
    r = await client.get(url(a, course), headers=a_headers)
    assert r.status_code == 200, r.text
    assert r.json()["student_id"] == str(a.id)


async def test_a_student_cannot_read_another_students_progress_in_either_direction(client, db_session, organization, rbac_seeded):
    a, a_headers, b, b_headers, course = await world(client, db_session, organization)
    for headers, other in ((b_headers, a), (a_headers, b)):
        r = await client.get(url(other, course), headers=headers)
        assert r.status_code == 403, r.text
        assert str(other.id) not in r.text and "completed_lessons" not in r.text


async def test_staff_with_progress_manage_keep_access(client, db_session, organization, rbac_seeded):
    a, _, _, _, course = await world(client, db_session, organization)
    headers = await user_with(db_session, organization, ["lms.progress.view", "lms.progress.manage"])
    assert (await client.get(url(a, course), headers=headers)).status_code == 200


async def test_a_superuser_keeps_access(client, db_session, organization, auth_headers, rbac_seeded):
    a, _, _, _, course = await world(client, db_session, organization)
    assert (await client.get(url(a, course), headers=auth_headers)).status_code == 200


async def test_the_view_permission_alone_is_not_enough(client, db_session, organization, rbac_seeded):
    a, _, _, _, course = await world(client, db_session, organization)
    headers = await user_with(db_session, organization, ["lms.progress.view"])
    assert (await client.get(url(a, course), headers=headers)).status_code == 403


async def test_staff_cannot_read_a_student_of_another_organization(client, db_session, organization, rbac_seeded):
    _, _, _, _, course = await world(client, db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    stranger = Student(organization_id=other.id, student_code=f"S-{uuid.uuid4().hex[:8]}", full_name="Elsewhere", email=f"e-{uuid.uuid4().hex[:6]}@example.com", course_name="Cyber", enrollment_date=date(2026, 1, 1))
    db_session.add(stranger)
    await db_session.flush()
    headers = await user_with(db_session, organization, ["lms.progress.view", "lms.progress.manage"])
    r = await client.get(url(stranger, course), headers=headers)
    assert r.status_code == 404, r.text


async def test_a_student_of_another_organization_cannot_read_ours(client, db_session, organization, rbac_seeded):
    a, _, _, _, course = await world(client, db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other2", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, outsider_headers = await student_with_role(client, db_session, other)
    assert (await client.get(url(a, course), headers=outsider_headers)).status_code in (403, 404)


async def test_no_login_and_a_bad_token_fail_closed(client, db_session, organization, rbac_seeded):
    a, _, _, _, course = await world(client, db_session, organization)
    assert (await client.get(url(a, course))).status_code in (401, 403)
    assert (await client.get(url(a, course), headers={"Authorization": "Bearer not-a-token"})).status_code in (401, 403)


async def test_a_signed_in_user_with_no_student_record_and_no_staff_permission_is_refused(client, db_session, organization, rbac_seeded):
    a, _, _, _, course = await world(client, db_session, organization)
    headers = await user_with(db_session, organization, [])
    assert (await client.get(url(a, course), headers=headers)).status_code == 403

