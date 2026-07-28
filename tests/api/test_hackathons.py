"""
API tests for the Hackathons module: staff CRUD/grading plus the student
self-service surface (browse open hackathons, create/join a team, submit
a project). Team membership is the ownership boundary for submissions,
so tests cover capacity limits, double-registration, and cross-hackathon
isolation alongside the happy path.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.authentication.repository import AuthRepository
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


def _dates():
    today = date.today()
    return {
        "registration_deadline": (today + timedelta(days=7)).isoformat(),
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=12)).isoformat(),
    }


async def _create_hackathon(client, auth_headers, **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "code": f"HACK-{unique}",
        "title": "Build for Good",
        "max_team_size": 2,
        **_dates(),
    }
    payload.update(overrides)
    response = await client.post("/api/v1/hackathons", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
    unique = uuid.uuid4().hex[:8]
    email = f"hack.{unique}@erpx.example.com"
    password = "StudentPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name=full_name,
        course_name="Python Bootcamp",
        enrollment_date=date(2026, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, {"Authorization": f"Bearer {token}"}


async def test_create_and_get_hackathon(client, auth_headers):
    hackathon = await _create_hackathon(client, auth_headers)
    assert hackathon["status"] == "draft"
    assert hackathon["max_team_size"] == 2

    get_response = await client.get(f"/api/v1/hackathons/{hackathon['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Build for Good"


async def test_duplicate_hackathon_code_rejected(client, auth_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {"code": f"DUP-{unique}", "title": "Dup", **_dates()}
    first = await client.post("/api/v1/hackathons", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/hackathons", json=payload, headers=auth_headers)
    assert second.status_code == 409


async def test_staff_without_permission_cannot_manage_hackathons(client, staff_headers):
    response = await client.post(
        "/api/v1/hackathons", json={"code": "NOAUTH-01", "title": "Unauthorized", **_dates()}, headers=staff_headers
    )
    assert response.status_code == 403


async def test_student_can_create_team_and_submit_project(client, db_session, organization, auth_headers):
    hackathon = await _create_hackathon(client, auth_headers)
    await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/status", json={"status": "registration_open"}, headers=auth_headers
    )

    _student, headers = await _create_student_with_login(client, db_session, organization)

    list_response = await client.get("/api/v1/hackathons/me", headers=headers)
    assert list_response.status_code == 200
    assert any(h["id"] == hackathon["id"] for h in list_response.json())

    create_team_response = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "The Innovators"}, headers=headers
    )
    assert create_team_response.status_code == 201, create_team_response.text
    team = create_team_response.json()

    my_team_response = await client.get(f"/api/v1/hackathons/{hackathon['id']}/teams/me", headers=headers)
    assert my_team_response.status_code == 200
    assert my_team_response.json()["team"]["id"] == team["id"]
    assert len(my_team_response.json()["members"]) == 1

    submit_response = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/{team['id']}/submissions/me",
        json={"title": "AI Recycling Sorter", "repo_url": "https://github.com/example/repo"},
        headers=headers,
    )
    assert submit_response.status_code == 201, submit_response.text
    assert submit_response.json()["title"] == "AI Recycling Sorter"

    # Resubmitting updates the same row rather than creating a new one.
    resubmit_response = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/{team['id']}/submissions/me",
        json={"title": "AI Recycling Sorter v2", "repo_url": "https://github.com/example/repo"},
        headers=headers,
    )
    assert resubmit_response.status_code == 201
    assert resubmit_response.json()["id"] == submit_response.json()["id"]
    assert resubmit_response.json()["title"] == "AI Recycling Sorter v2"


async def test_student_cannot_join_two_teams_in_same_hackathon(client, db_session, organization, auth_headers):
    hackathon = await _create_hackathon(client, auth_headers)
    await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/status", json={"status": "registration_open"}, headers=auth_headers
    )

    _student_a, headers_a = await _create_student_with_login(client, db_session, organization, "Student A")
    _student_b, headers_b = await _create_student_with_login(client, db_session, organization, "Student B")

    team_a = (
        await client.post(
            f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "Team A"}, headers=headers_a
        )
    ).json()
    await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "Team B"}, headers=headers_b
    )

    duplicate_response = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "Team C"}, headers=headers_a
    )
    assert duplicate_response.status_code == 409

    join_own_hackathon_twice = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/{team_a['id']}/join/me", headers=headers_a
    )
    assert join_own_hackathon_twice.status_code == 409


async def test_team_join_respects_max_team_size(client, db_session, organization, auth_headers):
    hackathon = await _create_hackathon(client, auth_headers, max_team_size=1)
    await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/status", json={"status": "registration_open"}, headers=auth_headers
    )

    _student_a, headers_a = await _create_student_with_login(client, db_session, organization, "Student A")
    _student_b, headers_b = await _create_student_with_login(client, db_session, organization, "Student B")

    team = (
        await client.post(
            f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "Solo Team"}, headers=headers_a
        )
    ).json()

    join_response = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/{team['id']}/join/me", headers=headers_b
    )
    assert join_response.status_code == 422


async def test_team_registration_rejected_before_status_open(client, db_session, organization, auth_headers):
    hackathon = await _create_hackathon(client, auth_headers)  # still "draft"
    _student, headers = await _create_student_with_login(client, db_session, organization)

    response = await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "Too Early"}, headers=headers
    )
    assert response.status_code == 422


async def test_staff_can_list_teams_and_grade_submission(client, db_session, organization, auth_headers):
    hackathon = await _create_hackathon(client, auth_headers)
    await client.post(
        f"/api/v1/hackathons/{hackathon['id']}/status", json={"status": "registration_open"}, headers=auth_headers
    )
    _student, headers = await _create_student_with_login(client, db_session, organization)

    team = (
        await client.post(
            f"/api/v1/hackathons/{hackathon['id']}/teams/me", json={"name": "Graded Team"}, headers=headers
        )
    ).json()
    submission = (
        await client.post(
            f"/api/v1/hackathons/{hackathon['id']}/teams/{team['id']}/submissions/me",
            json={"title": "Project X"},
            headers=headers,
        )
    ).json()

    teams_response = await client.get(f"/api/v1/hackathons/{hackathon['id']}/teams", headers=auth_headers)
    assert teams_response.status_code == 200
    assert len(teams_response.json()) == 1

    submissions_response = await client.get(
        f"/api/v1/hackathons/{hackathon['id']}/submissions", headers=auth_headers
    )
    assert submissions_response.status_code == 200
    assert len(submissions_response.json()) == 1

    grade_response = await client.post(
        f"/api/v1/hackathons/submissions/{submission['id']}/grade",
        json={"score": 88, "feedback": "Great execution."},
        headers=auth_headers,
    )
    assert grade_response.status_code == 200
    assert grade_response.json()["score"] == 88
