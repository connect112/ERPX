"""
API tests for the trainer-facing live-class endpoints added alongside
the trainer/student portal live-classes pages: a trainer should see and
be able to start/complete/cancel a live class scheduled for a batch they
actually teach (ownership via Trainer -> Batch.trainer_id, same
User -> Employee -> Trainer chain test_trainer_self_service.py's own
helper sets up), and get a clean 404 — not a raw permission error — for
one they don't.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from modules.courses.repository import CourseRepository
from modules.employees.repository import EmployeeRepository
from modules.trainers.repository import TrainerRepository

pytestmark = pytest.mark.api


async def _create_trainer_with_login(client, db_session, organization, full_name="Test Trainer"):
    """Same helper as tests/api/test_trainer_self_service.py — duplicated
    rather than imported since that module has no public re-export and
    pulling a test helper across test files is more fragile than a short
    copy."""
    unique = uuid.uuid4().hex[:8]
    email = f"trainer.{unique}@erpx.example.com"
    password = "TrainerPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    from modules.authentication.repository import AuthRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)

    from modules.users.repository import UserProfileRepository

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    employee = await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        user_id=user.id,
        full_name=full_name,
        date_of_joining=date(2024, 1, 1),
    )
    trainer = await TrainerRepository(db_session).create(
        organization_id=organization.id, employee_id=employee.id
    )
    await db_session.flush()

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return trainer, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def course(db_session, organization):
    repo = CourseRepository(db_session)
    unique = uuid.uuid4().hex[:8]
    return await repo.create(
        organization_id=organization.id, title="Cloud Security", slug=f"cloud-sec-{unique}"
    )


async def _create_batch(client, auth_headers, course, trainer_id):
    resp = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "trainer_id": str(trainer_id),
            "name": "Morning Batch",
            "code": f"BATCH-{uuid.uuid4().hex[:8]}",
            "start_date": "2026-09-01",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_live_class(client, auth_headers, batch_id, trainer_id):
    resp = await client.post(
        "/api/v1/live-classes",
        json={
            "batch_id": batch_id,
            "trainer_id": str(trainer_id),
            "title": "Doubt clearing session",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": 45,
            "meeting_link": "https://meet.example.com/abc-defg-hij",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_trainer_sees_own_live_class_and_can_change_status(
    client, db_session, organization, course, auth_headers
):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id)

    list_resp = await client.get("/api/v1/live-classes/trainer/me", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert [c["id"] for c in list_resp.json()] == [live_class["id"]]

    start_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status",
        json={"status": "live"},
        headers=headers,
    )
    assert start_resp.status_code == 200, start_resp.text
    assert start_resp.json()["status"] == "live"

    complete_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status",
        json={"status": "completed", "recording_url": "https://cdn.example.com/rec.mp4"},
        headers=headers,
    )
    assert complete_resp.status_code == 200, complete_resp.text
    assert complete_resp.json()["status"] == "completed"
    assert complete_resp.json()["recording_url"] == "https://cdn.example.com/rec.mp4"


async def test_trainer_cannot_see_or_change_another_trainers_live_class(
    client, db_session, organization, course, auth_headers
):
    trainer_a, headers_a = await _create_trainer_with_login(
        client, db_session, organization, full_name="Trainer A"
    )
    trainer_b, _headers_b = await _create_trainer_with_login(
        client, db_session, organization, full_name="Trainer B"
    )

    # Only trainer B teaches this batch.
    batch = await _create_batch(client, auth_headers, course, trainer_b.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer_b.id)

    list_resp = await client.get("/api/v1/live-classes/trainer/me", headers=headers_a)
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    status_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status",
        json={"status": "live"},
        headers=headers_a,
    )
    # 404, not 403: trainer A shouldn't be able to tell this live class
    # exists at all, same reasoning as every other ownership check.
    assert status_resp.status_code == 404, status_resp.text


async def test_student_sees_live_class_for_own_batch(client, db_session, organization, course, auth_headers):
    from datetime import date as date_cls

    from modules.batches.repository import BatchEnrollmentRepository
    from modules.students.repository import StudentRepository

    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id)

    unique = uuid.uuid4().hex[:8]
    student_email = f"student.{unique}@erpx.example.com"
    student_password = "StudentPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": student_email, "password": student_password, "full_name": "Test Student"},
    )
    assert register_response.status_code == 201

    from modules.authentication.repository import AuthRepository
    from modules.users.repository import UserProfileRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(student_email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name="Test Student",
        course_name=course.title,
        enrollment_date=date_cls(2024, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": student_email, "password": student_password}
    )
    student_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    await BatchEnrollmentRepository(db_session).create(
        organization_id=organization.id,
        batch_id=uuid.UUID(batch["id"]),
        student_id=student.id,
        enrolled_at=date_cls(2026, 9, 1),
    )
    await db_session.flush()

    resp = await client.get("/api/v1/live-classes/me", headers=student_headers)
    assert resp.status_code == 200, resp.text
    assert [c["id"] for c in resp.json()] == [live_class["id"]]
