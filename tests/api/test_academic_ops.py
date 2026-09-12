"""
API tests for the academic-ops modules: Trainers, Classrooms, Batches,
Timetable, and Live Classes. These build on each other (a Batch needs a
Course + optionally a Trainer; Timetable/Live Classes need a Batch), so
one shared set of fixtures creates the prerequisite chain rather than
five independent, disconnected test files.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from modules.courses.repository import CourseRepository
from modules.employees.repository import EmployeeRepository

pytestmark = pytest.mark.api


@pytest.fixture
async def employee(db_session, organization):
    repo = EmployeeRepository(db_session)
    emp = await repo.create(
        organization_id=organization.id,
        full_name="Jamie Trainer",
        date_of_joining=date(2024, 1, 1),
    )
    return emp


@pytest.fixture
async def course(db_session, organization):
    repo = CourseRepository(db_session)
    unique = uuid.uuid4().hex[:8]
    return await repo.create(
        organization_id=organization.id, title="Python Bootcamp", slug=f"python-bootcamp-{unique}"
    )


async def _create_trainer(client, auth_headers, employee_id):
    response = await client.post(
        "/api/v1/trainers", json={"employee_id": str(employee_id)}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_batch(client, auth_headers, course_id, trainer_id=None):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "course_id": str(course_id),
        "name": "Morning Batch",
        "code": f"BATCH-{unique}",
        "start_date": "2026-09-01",
    }
    if trainer_id:
        payload["trainer_id"] = str(trainer_id)
    response = await client.post("/api/v1/batches", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---- Trainers ----


async def test_create_trainer_from_employee(client, auth_headers, employee):
    trainer = await _create_trainer(client, auth_headers, employee.id)
    assert trainer["employee_id"] == str(employee.id)
    assert trainer["employee_name"] == "Jamie Trainer"
    assert trainer["is_active"] is True


async def test_creating_second_trainer_for_same_employee_is_rejected(client, auth_headers, employee):
    await _create_trainer(client, auth_headers, employee.id)
    response = await client.post(
        "/api/v1/trainers", json={"employee_id": str(employee.id)}, headers=auth_headers
    )
    assert response.status_code == 409


async def test_create_trainer_for_nonexistent_employee_fails(client, auth_headers):
    response = await client.post(
        "/api/v1/trainers",
        json={"employee_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---- Classrooms ----


async def test_create_and_list_classroom(client, auth_headers):
    unique = uuid.uuid4().hex[:8]
    response = await client.post(
        "/api/v1/classrooms",
        json={"name": "Lab 1", "code": f"LAB-{unique}", "classroom_type": "physical", "capacity": 30},
        headers=auth_headers,
    )
    assert response.status_code == 201
    classroom = response.json()
    assert classroom["capacity"] == 30

    list_response = await client.get("/api/v1/classrooms", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(c["id"] == classroom["id"] for c in list_response.json()["items"])


async def test_duplicate_classroom_code_rejected(client, auth_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {"name": "Lab A", "code": f"DUP-{unique}", "classroom_type": "virtual"}
    first = await client.post("/api/v1/classrooms", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/classrooms", json=payload, headers=auth_headers)
    assert second.status_code == 409


# ---- Batches ----


async def test_create_batch_with_trainer(client, auth_headers, employee, course):
    trainer = await _create_trainer(client, auth_headers, employee.id)
    batch = await _create_batch(client, auth_headers, course.id, trainer["id"])
    assert batch["course_id"] == str(course.id)
    assert batch["trainer_id"] == trainer["id"]
    assert batch["status"] == "upcoming"


async def test_create_batch_for_nonexistent_course_fails(client, auth_headers):
    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": "00000000-0000-0000-0000-000000000000",
            "name": "Ghost Batch",
            "code": "GHOST-01",
            "start_date": "2026-09-01",
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_update_batch_status(client, auth_headers, course):
    batch = await _create_batch(client, auth_headers, course.id)
    response = await client.patch(
        f"/api/v1/batches/{batch['id']}", json={"status": "ongoing"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ongoing"


# ---- Timetable ----


async def test_create_timetable_entry(client, auth_headers, course):
    batch = await _create_batch(client, auth_headers, course.id)
    response = await client.post(
        "/api/v1/timetable",
        json={
            "batch_id": batch["id"],
            "day_of_week": "monday",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "subject": "Intro to Python",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry["day_of_week"] == "monday"

    list_response = await client.get(
        f"/api/v1/timetable?batch_id={batch['id']}", headers=auth_headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_timetable_start_after_end_rejected(client, auth_headers, course):
    batch = await _create_batch(client, auth_headers, course.id)
    response = await client.post(
        "/api/v1/timetable",
        json={
            "batch_id": batch["id"],
            "day_of_week": "monday",
            "start_time": "14:00:00",
            "end_time": "10:00:00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_timetable_classroom_double_booking_rejected(client, auth_headers, course):
    unique = uuid.uuid4().hex[:8]
    classroom_response = await client.post(
        "/api/v1/classrooms",
        json={"name": "Room X", "code": f"ROOMX-{unique}", "classroom_type": "physical"},
        headers=auth_headers,
    )
    classroom_id = classroom_response.json()["id"]

    batch_a = await _create_batch(client, auth_headers, course.id)
    batch_b = await _create_batch(client, auth_headers, course.id)

    first = await client.post(
        "/api/v1/timetable",
        json={
            "batch_id": batch_a["id"],
            "classroom_id": classroom_id,
            "day_of_week": "tuesday",
            "start_time": "09:00:00",
            "end_time": "11:00:00",
        },
        headers=auth_headers,
    )
    assert first.status_code == 201

    # Overlaps 09:00-11:00 in the same room on the same day, different batch.
    conflicting = await client.post(
        "/api/v1/timetable",
        json={
            "batch_id": batch_b["id"],
            "classroom_id": classroom_id,
            "day_of_week": "tuesday",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        },
        headers=auth_headers,
    )
    assert conflicting.status_code == 409

    # Non-overlapping slot in the same room, same day, succeeds.
    non_conflicting = await client.post(
        "/api/v1/timetable",
        json={
            "batch_id": batch_b["id"],
            "classroom_id": classroom_id,
            "day_of_week": "tuesday",
            "start_time": "11:00:00",
            "end_time": "13:00:00",
        },
        headers=auth_headers,
    )
    assert non_conflicting.status_code == 201


# ---- Live Classes ----


async def test_create_live_class_and_transition_status(client, auth_headers, course):
    batch = await _create_batch(client, auth_headers, course.id)
    create_response = await client.post(
        "/api/v1/live-classes",
        json={
            "batch_id": batch["id"],
            "title": "Doubt Clearing Session",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": 45,
            "meeting_link": "https://meet.example.com/abc123",
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    live_class = create_response.json()
    assert live_class["status"] == "scheduled"

    go_live = await client.post(
        f"/api/v1/live-classes/{live_class['id']}/status",
        json={"status": "live"},
        headers=auth_headers,
    )
    assert go_live.status_code == 200
    assert go_live.json()["status"] == "live"

    complete = await client.post(
        f"/api/v1/live-classes/{live_class['id']}/status",
        json={"status": "completed", "recording_url": "https://storage.example.com/rec.mp4"},
        headers=auth_headers,
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"
    assert complete.json()["recording_url"] == "https://storage.example.com/rec.mp4"


async def test_live_class_invalid_status_transition_rejected(client, auth_headers, course):
    batch = await _create_batch(client, auth_headers, course.id)
    create_response = await client.post(
        "/api/v1/live-classes",
        json={
            "batch_id": batch["id"],
            "title": "Session",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "meeting_link": "https://meet.example.com/xyz",
        },
        headers=auth_headers,
    )
    live_class_id = create_response.json()["id"]

    # Cannot go straight from "scheduled" to "completed".
    response = await client.post(
        f"/api/v1/live-classes/{live_class_id}/status",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_staff_without_permission_cannot_manage_batches(client, staff_headers, course):
    response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "name": "Unauthorized Batch",
            "code": "NOAUTH-01",
            "start_date": "2026-09-01",
        },
        headers=staff_headers,
    )
    assert response.status_code == 403
