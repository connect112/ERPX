"""
API tests for the student<->trainer messaging module. Isolation has no
separate membership table -- who a student may message is derived live
from Batch.trainer_id + BatchEnrollment (modules/messaging/service.py),
so these tests exercise that derivation directly rather than a stored
pairing: a student may only reach a trainer actually teaching one of
their active batches, never another student, and a batch reassignment
cuts off new sends without erasing history. Admin gets a read-only
audit view onto the same rows via `messaging.view_all`.
"""

import uuid
from datetime import date

import pytest

from modules.batches.models import BatchStatus
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.employees.repository import EmployeeRepository
from modules.students.repository import StudentRepository
from modules.trainers.repository import TrainerRepository

pytestmark = pytest.mark.api


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
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
        course_name="Test Course",
        enrollment_date=date(2026, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, {"Authorization": f"Bearer {token}"}


async def _create_trainer_with_login(client, db_session, organization, full_name="Test Trainer"):
    unique = uuid.uuid4().hex[:8]
    email = f"trainer.{unique}@erpx.example.com"
    password = "TrainerPass1!"

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

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return trainer, {"Authorization": f"Bearer {token}"}


async def _create_course(db_session, organization):
    unique = uuid.uuid4().hex[:8]
    return await CourseRepository(db_session).create(
        organization_id=organization.id, title="Test Course", slug=f"course-{unique}", is_published=True
    )


async def _create_batch_with_trainer(db_session, organization, course, trainer_id):
    return await BatchRepository(db_session).create(
        organization_id=organization.id,
        course_id=course.id,
        trainer_id=trainer_id,
        code=f"BATCH-{uuid.uuid4().hex[:6]}",
        name="Test Batch",
        status=BatchStatus.ONGOING,
        start_date=date(2026, 1, 1),
    )


async def _enroll_student_in_batch(db_session, organization, batch_id, student_id):
    await BatchEnrollmentRepository(db_session).create(
        organization_id=organization.id, batch_id=batch_id, student_id=student_id, enrolled_at=date(2026, 1, 1)
    )


async def _paired_student_and_trainer(client, db_session, organization):
    """A student enrolled in a batch taught by a trainer -- the baseline
    pairing every isolation test starts from."""
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    trainer, trainer_headers = await _create_trainer_with_login(client, db_session, organization)
    course = await _create_course(db_session, organization)
    batch = await _create_batch_with_trainer(db_session, organization, course, trainer.id)
    await _enroll_student_in_batch(db_session, organization, batch.id, student.id)
    return student, student_headers, trainer, trainer_headers, batch


async def test_student_sees_only_their_own_batchs_trainer(client, db_session, organization):
    student, student_headers, trainer, _trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    stranger_trainer, _ = await _create_trainer_with_login(client, db_session, organization, "Stranger Trainer")

    resp = await client.get("/api/v1/messaging/me/trainers", headers=student_headers)
    assert resp.status_code == 200, resp.text
    trainer_ids = {t["trainer_id"] for t in resp.json()}
    assert str(trainer.id) in trainer_ids
    assert str(stranger_trainer.id) not in trainer_ids


async def test_student_cannot_open_a_conversation_with_an_unpaired_trainer(client, db_session, organization):
    student, student_headers, _trainer, _trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    stranger_trainer, _ = await _create_trainer_with_login(client, db_session, organization, "Stranger Trainer")

    resp = await client.post(
        f"/api/v1/messaging/me/conversations/with/{stranger_trainer.id}", headers=student_headers
    )
    assert resp.status_code == 404, resp.text


async def test_trainer_cannot_open_a_conversation_with_an_unpaired_student(client, db_session, organization):
    _student, _student_headers, trainer, trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    stranger_student, _ = await _create_student_with_login(client, db_session, organization, "Stranger Student")

    resp = await client.post(
        f"/api/v1/messaging/trainer/me/conversations/with/{stranger_student.id}", headers=trainer_headers
    )
    assert resp.status_code == 404, resp.text


async def test_a_different_student_cannot_read_someone_elses_conversation(client, db_session, organization):
    student, student_headers, trainer, _trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    open_resp = await client.post(
        f"/api/v1/messaging/me/conversations/with/{trainer.id}", headers=student_headers
    )
    assert open_resp.status_code == 200, open_resp.text
    conversation_id = open_resp.json()["id"]

    other_student, other_headers = await _create_student_with_login(client, db_session, organization, "Other Student")

    resp = await client.get(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages", headers=other_headers
    )
    assert resp.status_code == 404, resp.text


async def test_send_and_read_message_flow_updates_unread_count(client, db_session, organization):
    student, student_headers, trainer, trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    open_resp = await client.post(
        f"/api/v1/messaging/me/conversations/with/{trainer.id}", headers=student_headers
    )
    conversation_id = open_resp.json()["id"]

    send_resp = await client.post(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages",
        json={"body": "I have a doubt about lesson 3"},
        headers=student_headers,
    )
    assert send_resp.status_code == 200, send_resp.text

    unread_resp = await client.get(
        "/api/v1/messaging/trainer/me/conversations/unread-count", headers=trainer_headers
    )
    assert unread_resp.json()["unread_count"] == 1

    read_resp = await client.get(
        f"/api/v1/messaging/trainer/me/conversations/{conversation_id}/messages", headers=trainer_headers
    )
    assert read_resp.status_code == 200, read_resp.text
    assert len(read_resp.json()) == 1
    assert read_resp.json()[0]["body"] == "I have a doubt about lesson 3"

    unread_after_resp = await client.get(
        "/api/v1/messaging/trainer/me/conversations/unread-count", headers=trainer_headers
    )
    assert unread_after_resp.json()["unread_count"] == 0

    reply_resp = await client.post(
        f"/api/v1/messaging/trainer/me/conversations/{conversation_id}/messages",
        json={"body": "Sure, lesson 3 covers..."},
        headers=trainer_headers,
    )
    assert reply_resp.status_code == 200, reply_resp.text

    student_unread_resp = await client.get(
        "/api/v1/messaging/me/conversations/unread-count", headers=student_headers
    )
    assert student_unread_resp.json()["unread_count"] == 1


async def test_send_message_rejects_empty_body_and_no_attachment(client, db_session, organization):
    student, student_headers, trainer, _trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    open_resp = await client.post(
        f"/api/v1/messaging/me/conversations/with/{trainer.id}", headers=student_headers
    )
    conversation_id = open_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages", json={}, headers=student_headers
    )
    assert resp.status_code == 422, resp.text


async def test_batch_reassignment_cuts_off_new_sends_but_not_history(client, db_session, organization):
    student, student_headers, trainer, _trainer_headers, batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    open_resp = await client.post(
        f"/api/v1/messaging/me/conversations/with/{trainer.id}", headers=student_headers
    )
    conversation_id = open_resp.json()["id"]
    send_resp = await client.post(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages",
        json={"body": "Before reassignment"},
        headers=student_headers,
    )
    assert send_resp.status_code == 200, send_resp.text

    new_trainer, _ = await _create_trainer_with_login(client, db_session, organization, "New Trainer")
    batch.trainer_id = new_trainer.id
    await db_session.flush()

    blocked_resp = await client.post(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages",
        json={"body": "After reassignment"},
        headers=student_headers,
    )
    assert blocked_resp.status_code == 422, blocked_resp.text

    history_resp = await client.get(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages", headers=student_headers
    )
    assert history_resp.status_code == 200, history_resp.text
    assert len(history_resp.json()) == 1
    assert history_resp.json()[0]["body"] == "Before reassignment"


async def test_admin_can_read_any_conversation_but_has_no_send_route(
    client, auth_headers, db_session, organization, rbac_seeded
):
    student, student_headers, trainer, _trainer_headers, _batch = await _paired_student_and_trainer(
        client, db_session, organization
    )
    open_resp = await client.post(
        f"/api/v1/messaging/me/conversations/with/{trainer.id}", headers=student_headers
    )
    conversation_id = open_resp.json()["id"]
    await client.post(
        f"/api/v1/messaging/me/conversations/{conversation_id}/messages",
        json={"body": "Admin should be able to see this"},
        headers=student_headers,
    )

    list_resp = await client.get("/api/v1/messaging/conversations", headers=auth_headers)
    assert list_resp.status_code == 200, list_resp.text
    conversation_ids = {c["id"] for c in list_resp.json()["items"]}
    assert conversation_id in conversation_ids

    messages_resp = await client.get(
        f"/api/v1/messaging/conversations/{conversation_id}/messages", headers=auth_headers
    )
    assert messages_resp.status_code == 200, messages_resp.text
    assert messages_resp.json()[0]["body"] == "Admin should be able to see this"


async def test_admin_without_permission_cannot_read_conversations(
    client, db_session, organization, staff_headers
):
    resp = await client.get("/api/v1/messaging/conversations", headers=staff_headers)
    assert resp.status_code == 403, resp.text
