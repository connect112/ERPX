"""
API tests for the trainer-facing live-class endpoints added alongside
the trainer/student portal live-classes pages: a trainer should see and
be able to start/complete/cancel a live class scheduled for a batch they
actually teach (ownership via Trainer -> Batch.trainer_id, same
User -> Employee -> Trainer chain test_trainer_self_service.py's own
helper sets up), and get a clean 404 — not a raw permission error — for
one they don't.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import date, datetime, timezone

import pytest
import jwt as pyjwt

from app.core.config import settings
from modules.courses.repository import CourseRepository
from modules.employees.repository import EmployeeRepository
from modules.trainers.repository import TrainerRepository

pytestmark = pytest.mark.api

_JITSI_SECRET = "test-jitsi-secret"
_JIBRI_SECRET = "test-jibri-webhook-secret"


@pytest.fixture
def jitsi_configured(monkeypatch):
    """Jitsi is unconfigured by default (JITSI_PUBLIC_URL unset) so every
    other test in this file — and every other test file — is unaffected;
    only tests that actually exercise the Jitsi integration opt in."""
    monkeypatch.setattr(settings, "JITSI_PUBLIC_URL", "https://meet.pentrix.test")
    monkeypatch.setattr(settings, "JITSI_APP_SECRET", _JITSI_SECRET)
    monkeypatch.setattr(settings, "JITSI_APP_ID", "erpx")


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
    payload = {
        "course_id": str(course.id),
        "name": "Morning Batch",
        "code": f"BATCH-{uuid.uuid4().hex[:8]}",
        "start_date": "2026-09-01",
    }
    if trainer_id is not None:
        payload["trainer_id"] = str(trainer_id)
    resp = await client.post("/api/v1/batches", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_live_class(
    client, auth_headers, batch_id, trainer_id, meeting_link="https://meet.example.com/abc-defg-hij"
):
    payload = {
        "batch_id": batch_id,
        "trainer_id": str(trainer_id),
        "title": "Doubt clearing session",
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "duration_minutes": 45,
    }
    if meeting_link is not None:
        payload["meeting_link"] = meeting_link
    resp = await client.post("/api/v1/live-classes", json=payload, headers=auth_headers)
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


async def test_trainer_sees_own_live_class_when_batch_has_no_trainer_assigned(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    """Found live: an admin scheduled a class and assigned a trainer to
    it directly, but the batch itself had no trainer set (a batch's own
    trainer and a live class's trainer are picked independently -- see
    modules/live_classes/repository.py's list_for_trainer docstring).
    The trainer couldn't see the class at all, because visibility used
    to only check batch.trainer_id, never live_classes.trainer_id."""
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer_id=None)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)

    list_resp = await client.get("/api/v1/live-classes/trainer/me", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert [c["id"] for c in list_resp.json()] == [live_class["id"]]

    status_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status",
        json={"status": "live"},
        headers=headers,
    )
    assert status_resp.status_code == 200, status_resp.text

    join_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/join-token", headers=headers
    )
    assert join_resp.status_code == 200, join_resp.text


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


async def _enroll_student(client, db_session, organization, course, batch_id, auth_headers):
    from datetime import date as date_cls

    from modules.batches.repository import BatchEnrollmentRepository
    from modules.students.repository import StudentRepository

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
        batch_id=uuid.UUID(batch_id),
        student_id=student.id,
        enrolled_at=date_cls(2026, 9, 1),
    )
    await db_session.flush()
    return student, student_headers


async def test_create_live_class_auto_provisions_jitsi_room_when_link_omitted(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)

    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)

    assert live_class["meeting_link"].startswith("https://meet.pentrix.test/erpx-")


async def test_create_live_class_without_link_fails_when_jitsi_not_configured(
    client, db_session, organization, course, auth_headers
):
    assert settings.JITSI_PUBLIC_URL == ""
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)

    resp = await client.post(
        "/api/v1/live-classes",
        json={
            "batch_id": batch["id"],
            "trainer_id": str(trainer.id),
            "title": "Doubt clearing session",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": 45,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_trainer_join_token_grants_moderator_access_to_own_class(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)

    resp = await client.post(f"/api/v1/live-classes/trainer/{live_class['id']}/join-token", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["domain"] == "meet.pentrix.test"
    assert body["room"] in live_class["meeting_link"]

    claims = pyjwt.decode(body["jwt"], _JITSI_SECRET, algorithms=["HS256"], audience="erpx")
    assert claims["room"] == body["room"]
    assert claims["context"]["user"]["moderator"] is True
    # The in-call display name is the literal word "Trainer", never the
    # trainer's real name -- students shouldn't be able to identify who
    # they're talking to by name either way.
    assert claims["context"]["user"]["name"] == "Trainer"


async def test_trainer_join_token_denied_for_another_trainers_class(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer_a, headers_a = await _create_trainer_with_login(
        client, db_session, organization, full_name="Trainer A"
    )
    trainer_b, _headers_b = await _create_trainer_with_login(
        client, db_session, organization, full_name="Trainer B"
    )
    batch = await _create_batch(client, auth_headers, course, trainer_b.id)
    live_class = await _create_live_class(
        client, auth_headers, batch["id"], trainer_b.id, meeting_link=None
    )

    resp = await client.post(f"/api/v1/live-classes/trainer/{live_class['id']}/join-token", headers=headers_a)
    assert resp.status_code == 404, resp.text


async def test_student_join_token_grants_non_moderator_access_to_own_class(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)
    student, student_headers = await _enroll_student(
        client, db_session, organization, course, batch["id"], auth_headers
    )
    # Students can only join once the class is live AND the trainer has
    # actually joined it themselves -- see _STUDENT_JOINABLE_STATUSES and
    # the trainer_joined_at check in routes.py.
    await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status", json={"status": "live"}, headers=_headers
    )
    await client.post(f"/api/v1/live-classes/trainer/{live_class['id']}/join-token", headers=_headers)

    resp = await client.post(f"/api/v1/live-classes/{live_class['id']}/join-token", headers=student_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    claims = pyjwt.decode(body["jwt"], _JITSI_SECRET, algorithms=["HS256"], audience="erpx")
    assert claims["context"]["user"]["moderator"] is False
    # The in-call display name is the student's code, never their real
    # name -- students share this room with other students.
    assert claims["context"]["user"]["name"] == student.student_code


async def test_student_join_token_rejected_while_trainer_hasnt_joined(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)
    _student, student_headers = await _enroll_student(
        client, db_session, organization, course, batch["id"], auth_headers
    )
    # Status is live, but the trainer has never actually minted their own
    # join-token -- a student shouldn't be able to walk into an empty
    # room just because an admin (or an automated status change) flipped
    # the status, without the trainer having shown up at all.
    await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status", json={"status": "live"}, headers=_headers
    )

    resp = await client.post(f"/api/v1/live-classes/{live_class['id']}/join-token", headers=student_headers)
    assert resp.status_code == 422, resp.text


async def test_student_join_token_rejected_again_after_trainer_leaves(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)
    _student, student_headers = await _enroll_student(
        client, db_session, organization, course, batch["id"], auth_headers
    )
    await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status", json={"status": "live"}, headers=_headers
    )
    await client.post(f"/api/v1/live-classes/trainer/{live_class['id']}/join-token", headers=_headers)

    # Trainer is in -- student can join.
    resp = await client.post(f"/api/v1/live-classes/{live_class['id']}/join-token", headers=student_headers)
    assert resp.status_code == 200, resp.text

    # Trainer leaves the call (VideoCallOverlay's videoConferenceLeft ->
    # this route) -- the room re-locks, so a student trying again
    # afterward shouldn't just walk into an empty room.
    leave_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/leave", headers=_headers
    )
    assert leave_resp.status_code == 200, leave_resp.text

    resp = await client.post(f"/api/v1/live-classes/{live_class['id']}/join-token", headers=student_headers)
    assert resp.status_code == 422, resp.text


async def test_student_join_token_rejected_while_class_still_scheduled(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)
    _student, student_headers = await _enroll_student(
        client, db_session, organization, course, batch["id"], auth_headers
    )

    # The trainer never started it -- still "scheduled" -- so a student
    # trying to join shouldn't land in an empty, unsupervised room.
    resp = await client.post(f"/api/v1/live-classes/{live_class['id']}/join-token", headers=student_headers)
    assert resp.status_code == 422, resp.text


async def test_join_token_denied_for_unenrolled_student(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)

    unique = uuid.uuid4().hex[:8]
    outsider_email = f"outsider.{unique}@erpx.example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": outsider_email, "password": "OutsiderPass1!", "full_name": "Outsider"},
    )
    from modules.authentication.repository import AuthRepository

    user = await AuthRepository(db_session).get_user_by_email(outsider_email)
    await AuthRepository(db_session).mark_email_verified(user)
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": outsider_email, "password": "OutsiderPass1!"}
    )
    outsider_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    resp = await client.post(
        f"/api/v1/live-classes/{live_class['id']}/join-token", headers=outsider_headers
    )
    # No Student record at all for this user -> get_current_student itself
    # rejects it (422), same ownership-boundary reasoning as the 404 cases
    # above, just enforced one layer earlier.
    assert resp.status_code == 422, resp.text


async def test_join_token_rejected_once_class_is_cancelled(
    client, db_session, organization, course, auth_headers, jitsi_configured
):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id, meeting_link=None)

    cancel_resp = await client.post(
        f"/api/v1/live-classes/trainer/{live_class['id']}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    resp = await client.post(f"/api/v1/live-classes/trainer/{live_class['id']}/join-token", headers=headers)
    assert resp.status_code == 422, resp.text


def _jibri_signed_request(payload: dict, secret: str, *, timestamp: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode("utf-8")
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.{body.decode('utf-8')}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Jibri-Timestamp": str(ts),
        "X-Jibri-Signature": signature,
    }
    return body, headers


@pytest.fixture
def jibri_webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "JIBRI_WEBHOOK_SECRET", _JIBRI_SECRET)
    return _JIBRI_SECRET


async def test_recording_webhook_attaches_url_to_the_correct_live_class(
    client, db_session, organization, course, auth_headers, jibri_webhook_secret
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id)

    room_name = f"erpx-{uuid.UUID(live_class['id']).hex}"
    payload = {"room_name": room_name, "recording_url": "https://recordings.example.com/rec.mp4"}
    body, headers = _jibri_signed_request(payload, jibri_webhook_secret)

    resp = await client.post("/api/v1/live-classes/recording-webhook", content=body, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["recording_url"] == "https://recordings.example.com/rec.mp4"
    assert resp.json()["id"] == live_class["id"]


async def test_recording_webhook_rejects_bad_signature(
    client, db_session, organization, course, auth_headers, jibri_webhook_secret
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    live_class = await _create_live_class(client, auth_headers, batch["id"], trainer.id)

    room_name = f"erpx-{uuid.UUID(live_class['id']).hex}"
    payload = {"room_name": room_name, "recording_url": "https://recordings.example.com/rec.mp4"}
    _body, headers = _jibri_signed_request(payload, "wrong-secret")

    resp = await client.post(
        "/api/v1/live-classes/recording-webhook", json=payload, headers=headers
    )
    assert resp.status_code == 401, resp.text


async def test_recording_webhook_404s_for_unknown_room_name(client, jibri_webhook_secret):
    payload = {"room_name": "erpx-" + uuid.uuid4().hex, "recording_url": "https://recordings.example.com/rec.mp4"}
    body, headers = _jibri_signed_request(payload, jibri_webhook_secret)

    resp = await client.post("/api/v1/live-classes/recording-webhook", content=body, headers=headers)
    assert resp.status_code == 404, resp.text


async def test_recording_webhook_404s_for_malformed_room_name(client, jibri_webhook_secret):
    payload = {"room_name": "not-an-erpx-room", "recording_url": "https://recordings.example.com/rec.mp4"}
    body, headers = _jibri_signed_request(payload, jibri_webhook_secret)

    resp = await client.post("/api/v1/live-classes/recording-webhook", content=body, headers=headers)
    assert resp.status_code == 404, resp.text


async def test_recording_webhook_fails_closed_when_secret_unconfigured(client):
    assert settings.JIBRI_WEBHOOK_SECRET == ""
    payload = {"room_name": "erpx-" + uuid.uuid4().hex, "recording_url": "https://recordings.example.com/rec.mp4"}
    body, headers = _jibri_signed_request(payload, "any-secret")

    resp = await client.post("/api/v1/live-classes/recording-webhook", content=body, headers=headers)
    assert resp.status_code == 401, resp.text
