"""
API tests for the `student` system role (RBAC) — the account type Pentrix
provisioning (see `modules/provisioning`, added in a later change) grants a
newly-created student. Two things matter here, and this file keeps them
distinct:

  1. The role's permission surface is exactly what it should be: enough to
     self-serve courses/LMS/Pentrix, nothing administrative, no org-wide
     roster/listing endpoint on any module (`test_rbac.py`'s 403/200
     convention, applied to this role).
  2. Every pentrix `{student_id}`-scoped endpoint enforces ownership, not
     just permission possession — a student holding `pentrix.instances.view`
     (etc.) can only ever reach their *own* student_id through it, even
     though staff/admin holds the exact same permission code to reach any
     student's. This is the gap closed by
     `modules/pentrix/common/dependencies.py::enforce_own_student_or_staff`
     / `assert_can_access_student`.
"""

import uuid
from datetime import date, datetime, time, timezone

import pytest

from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.batches.models import BatchStatus
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.live_classes.repository import LiveClassRepository
from modules.pentrix.labs.models import LabDifficulty
from modules.pentrix.labs.repository import LabRepository
from modules.students.repository import StudentRepository
from modules.timetable.models import DayOfWeek
from modules.timetable.repository import TimetableRepository

pytestmark = [pytest.mark.api, pytest.mark.security]


async def _create_student_with_role(client, db_session, organization, rbac_seeded, full_name="Test Student"):
    """Registers a real user, links a Student record, and assigns exactly
    the `student` system role — mirrors `test_student_self_service.py`'s
    `_create_student_with_login`, plus the role assignment this file needs."""
    unique = uuid.uuid4().hex[:8]
    email = f"student.{unique}@erpx.example.com"
    password = "StudentPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201

    from modules.authentication.repository import AuthRepository
    from modules.users.repository import UserProfileRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name=full_name,
        course_name="Pentrix Program",
        enrollment_date=date(2026, 1, 1),
    )

    student_role = await AuthorizationRepository(db_session).get_role_by_slug("student")
    assert student_role is not None, "seed_default_rbac should have created the system 'student' role"
    await AuthorizationService(db_session).assign_role(user.id, student_role.id, assigned_by_user_id=None)
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, user, {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Permission surface: excluded org-roster/admin endpoints must stay 403.
# ---------------------------------------------------------------------------

EXCLUDED_ENDPOINTS = [
    "/api/v1/employees",
    "/api/v1/crm/leads",
    "/api/v1/leave/applications",
    "/api/v1/hr/departments",
    "/api/v1/payroll/components",
    "/api/v1/accounting/accounts",
    "/api/v1/classrooms",
    "/api/v1/students",
    "/api/v1/batches",
    "/api/v1/attendance",
]


@pytest.mark.parametrize("path", EXCLUDED_ENDPOINTS)
async def test_student_role_forbidden_on_admin_and_roster_endpoints(
    path, client, db_session, organization, rbac_seeded
):
    _student, _user, headers = await _create_student_with_role(client, db_session, organization, rbac_seeded)
    response = await client.get(path, headers=headers)
    assert response.status_code == 403, f"{path} should be 403 for the student role, got {response.status_code}"


# ---------------------------------------------------------------------------
# Permission surface: own-domain browse/self endpoints must be reachable.
# ---------------------------------------------------------------------------

SELF_SERVICE_ENDPOINTS = [
    "/api/v1/pentrix/labs",
    "/api/v1/pentrix/challenges",
    "/api/v1/pentrix/leaderboard",
    "/api/v1/courses/",
    "/api/v1/batches/student/me",
    "/api/v1/timetable/me",
    "/api/v1/live-classes/me",
    "/api/v1/lms/enrollment/me",
    "/api/v1/workshops/me",
    "/api/v1/hackathons/me",
    "/api/v1/internships/postings/me",
    "/api/v1/placements/postings/me",
    "/api/v1/alumni/events/me",
]


@pytest.mark.parametrize("path", SELF_SERVICE_ENDPOINTS)
async def test_student_role_allowed_on_own_domain_endpoints(
    path, client, db_session, organization, rbac_seeded
):
    _student, _user, headers = await _create_student_with_role(client, db_session, organization, rbac_seeded)
    response = await client.get(path, headers=headers)
    assert response.status_code == 200, f"{path} should be 200 for the student role, got {response.status_code}: {response.text}"


# ---------------------------------------------------------------------------
# batches/timetable/live_classes self-view: correctness, not just status code.
# ---------------------------------------------------------------------------

async def test_batch_timetable_live_class_self_views_reflect_actual_membership(
    client, db_session, organization, rbac_seeded
):
    student, _user, headers = await _create_student_with_role(client, db_session, organization, rbac_seeded)

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Pentrix Bootcamp", slug=f"pentrix-{uuid.uuid4().hex[:8]}"
    )
    batch = await BatchRepository(db_session).create(
        organization_id=organization.id,
        course_id=course.id,
        code=f"BATCH-{uuid.uuid4().hex[:6]}",
        name="Evening Batch",
        status=BatchStatus.ONGOING,
        start_date=date(2026, 1, 1),
    )
    await BatchEnrollmentRepository(db_session).create(
        organization_id=organization.id, batch_id=batch.id, student_id=student.id, enrolled_at=date(2026, 1, 1)
    )
    await TimetableRepository(db_session).create(
        organization_id=organization.id,
        batch_id=batch.id,
        classroom_id=None,
        trainer_id=None,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(18, 0),
        end_time=time(20, 0),
        subject="Recon",
    )
    await LiveClassRepository(db_session).create(
        organization_id=organization.id,
        batch_id=batch.id,
        trainer_id=None,
        title="Kickoff call",
        scheduled_at=datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc),
        meeting_link="https://meet.example.com/kickoff",
    )
    await db_session.flush()

    batches_response = await client.get("/api/v1/batches/student/me", headers=headers)
    assert batches_response.status_code == 200
    assert len(batches_response.json()) == 1
    assert batches_response.json()[0]["batch"]["id"] == str(batch.id)

    timetable_response = await client.get("/api/v1/timetable/me", headers=headers)
    assert timetable_response.status_code == 200
    assert len(timetable_response.json()) == 1
    assert timetable_response.json()[0]["subject"] == "Recon"

    live_classes_response = await client.get("/api/v1/live-classes/me", headers=headers)
    assert live_classes_response.status_code == 200
    assert len(live_classes_response.json()) == 1
    assert live_classes_response.json()[0]["title"] == "Kickoff call"


async def test_student_not_in_any_batch_sees_empty_self_views(client, db_session, organization, rbac_seeded):
    _student, _user, headers = await _create_student_with_role(client, db_session, organization, rbac_seeded)

    assert (await client.get("/api/v1/batches/student/me", headers=headers)).json() == []
    assert (await client.get("/api/v1/timetable/me", headers=headers)).json() == []
    assert (await client.get("/api/v1/live-classes/me", headers=headers)).json() == []


# ---------------------------------------------------------------------------
# Pentrix ownership: a student may only ever reach their own student_id,
# even though the permission code is shared with every other student.
# ---------------------------------------------------------------------------

async def _make_lab(db_session, organization):
    return await LabRepository(db_session).create(
        organization_id=organization.id,
        title="Recon 101",
        slug=f"recon-{uuid.uuid4().hex[:8]}",
        category="recon",
        difficulty=LabDifficulty.EASY,
        environment_image="pentrix/recon101:latest",
    )


async def test_student_cannot_view_another_students_lab_instances(
    client, db_session, organization, rbac_seeded
):
    student_a, _user_a, headers_a = await _create_student_with_role(
        client, db_session, organization, rbac_seeded, full_name="Student A"
    )
    student_b, _user_b, headers_b = await _create_student_with_role(
        client, db_session, organization, rbac_seeded, full_name="Student B"
    )
    lab = await _make_lab(db_session, organization)
    await db_session.flush()

    launch_response = await client.post(
        f"/api/v1/pentrix/labs/{lab.id}/launch",
        headers=headers_a,
        json={"student_id": str(student_a.id)},
    )
    assert launch_response.status_code == 201
    instance_id = launch_response.json()["id"]

    # Student A can see/stop their own instance.
    assert (await client.get(f"/api/v1/pentrix/instances/{instance_id}", headers=headers_a)).status_code == 200

    # Student B cannot: not via the instance directly, not via student A's
    # student_id, and cannot launch/stop on student A's behalf either.
    assert (await client.get(f"/api/v1/pentrix/instances/{instance_id}", headers=headers_b)).status_code == 403
    assert (
        await client.get(f"/api/v1/pentrix/students/{student_a.id}/instances", headers=headers_b)
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/pentrix/instances/{instance_id}/stop", headers=headers_b)
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/pentrix/labs/{lab.id}/launch", headers=headers_b, json={"student_id": str(student_a.id)}
        )
    ).status_code == 403

    # Student B's own (empty) view of their own student_id still works.
    assert (
        await client.get(f"/api/v1/pentrix/students/{student_b.id}/instances", headers=headers_b)
    ).status_code == 200


async def test_student_cannot_view_or_submit_another_students_flags(
    client, db_session, organization, rbac_seeded
):
    student_a, _user_a, headers_a = await _create_student_with_role(
        client, db_session, organization, rbac_seeded, full_name="Student A"
    )
    student_b, _user_b, headers_b = await _create_student_with_role(
        client, db_session, organization, rbac_seeded, full_name="Student B"
    )
    await db_session.flush()

    assert (
        await client.get(f"/api/v1/pentrix/students/{student_a.id}/solves", headers=headers_b)
    ).status_code == 403
    # B cannot submit "on behalf of" A either, even with a well-formed request.
    fake_challenge_id = uuid.uuid4()
    assert (
        await client.post(
            f"/api/v1/pentrix/challenges/{fake_challenge_id}/submit",
            headers=headers_b,
            json={"student_id": str(student_a.id), "flag_value": "PENTRIX{guess}"},
        )
    ).status_code == 403


async def test_student_cannot_view_another_students_achievements_or_certifications(
    client, db_session, organization, rbac_seeded
):
    student_a, _user_a, headers_a = await _create_student_with_role(
        client, db_session, organization, rbac_seeded, full_name="Student A"
    )
    student_b, _user_b, headers_b = await _create_student_with_role(
        client, db_session, organization, rbac_seeded, full_name="Student B"
    )
    await db_session.flush()

    assert (
        await client.get(f"/api/v1/pentrix/achievements/students/{student_a.id}", headers=headers_b)
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/pentrix/certifications/students/{student_a.id}", headers=headers_b)
    ).status_code == 403
    # Each can still reach their own.
    assert (
        await client.get(f"/api/v1/pentrix/achievements/students/{student_a.id}", headers=headers_a)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/pentrix/certifications/students/{student_a.id}", headers=headers_a)
    ).status_code == 200
