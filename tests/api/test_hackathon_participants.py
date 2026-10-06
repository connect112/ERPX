"""
Bulk creation of hackathon participant logins, and the team-formation rules
the event leans on (unique names, team size under concurrency, visible
fullness). A participant's login is a Student + User with the `student`
role; the emailed set-password link is the only way in.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from modules.authentication.models import User
from modules.students.models import Student

# The `student` system role has to exist for accounts to be created.
pytestmark = [pytest.mark.api, pytest.mark.usefixtures("rbac_seeded")]

_HACK = "/api/v1/hackathons"


def _dates():
    today = date.today()
    return {
        "registration_deadline": (today + timedelta(days=7)).isoformat(),
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=12)).isoformat(),
    }


async def _open_hackathon(client, auth_headers, max_team_size=4):
    created = await client.post(
        _HACK,
        json={"code": f"H-{uuid.uuid4().hex[:8]}", "title": "DevSecStorm", "max_team_size": max_team_size, **_dates()},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    hackathon = created.json()
    opened = await client.post(
        f"{_HACK}/{hackathon['id']}/status", json={"status": "registration_open"}, headers=auth_headers
    )
    assert opened.status_code == 200, opened.text
    return hackathon


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture what would be emailed instead of queueing Celery tasks."""
    from modules.hackathons import routes

    captured: list[tuple[str, str, str]] = []
    monkeypatch.setattr(routes, "enqueue_welcome_emails", lambda logins, title, url: captured.extend(logins))
    return captured


async def _add(client, auth_headers, hackathon, rows, **extra):
    return await client.post(
        f"{_HACK}/{hackathon['id']}/participants",
        json={"participants": [{"name": n, "email": e} for n, e in rows], **extra},
        headers=auth_headers,
    )


async def _set_password_and_login(client, email, token, password="Hackathon#2026"):
    reset = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": password})
    assert reset.status_code == 200, reset.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_bulk_created_students_set_a_password_log_in_and_form_a_team(
    client, db_session, auth_headers, sent_emails
):
    hackathon = await _open_hackathon(client, auth_headers)
    resp = await _add(
        client,
        auth_headers,
        hackathon,
        [("  Asha   Rao ", "Asha@Example.com"), ("Ravi Kumar", "ravi@example.com"), ("Asha Again", "asha@example.com")],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created": 2, "resent": 0, "already_have_login": 0, "errors": []}  # dup in the paste ignored

    # Real accounts: email pre-verified, active, student role, linked student record.
    user = (await db_session.execute(select(User).where(User.email == "asha@example.com"))).scalar_one()
    assert user.is_email_verified and user.full_name == "Asha Rao"
    student = (await db_session.execute(select(Student).where(Student.user_id == user.id))).scalar_one()
    assert student.course_name == "DevSecStorm" and student.student_code.startswith("STU-")

    # The placeholder password can't be used; the emailed link is the way in.
    bad = await client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": "anything"})
    assert bad.status_code in (401, 400, 422)
    tokens = {email: token for email, _name, token in sent_emails}
    assert set(tokens) == {"asha@example.com", "ravi@example.com"}
    asha = await _set_password_and_login(client, "asha@example.com", tokens["asha@example.com"])
    ravi = await _set_password_and_login(client, "ravi@example.com", tokens["ravi@example.com"])

    # ...and the student side of the hackathon now works for them.
    listed = await client.get(f"{_HACK}/me", headers=asha)
    assert [h["id"] for h in listed.json()] == [hackathon["id"]]
    team = await client.post(f"{_HACK}/{hackathon['id']}/teams/me", json={"name": "Red Team"}, headers=asha)
    assert team.status_code == 201, team.text
    joined = await client.post(f"{_HACK}/{hackathon['id']}/teams/{team.json()['id']}/join/me", headers=ravi)
    assert joined.status_code == 200, joined.text

    # Staff see who is in each team; students only see how full it is.
    staff = (await client.get(f"{_HACK}/{hackathon['id']}/teams", headers=auth_headers)).json()
    assert staff[0]["member_count"] == 2 and set(staff[0]["member_names"]) == {"Asha Rao", "Ravi Kumar"}
    browse = (await client.get(f"{_HACK}/{hackathon['id']}/teams/browse", headers=ravi)).json()
    assert browse[0]["member_count"] == 2 and browse[0]["member_names"] == []


async def test_existing_accounts_are_left_alone_or_sent_a_fresh_link(client, db_session, auth_headers, sent_emails):
    hackathon = await _open_hackathon(client, auth_headers)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")])
    sent_emails.clear()

    again = await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")])
    assert again.json()["created"] == 0 and again.json()["already_have_login"] == 1
    assert sent_emails == []  # nothing re-sent unless asked

    resend = await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")], resend_to_existing=True)
    assert resend.json()["created"] == 0 and resend.json()["resent"] == 1
    assert [e for e, _n, _t in sent_emails] == ["meena@example.com"]
    # The fresh link works.
    await _set_password_and_login(client, "meena@example.com", sent_emails[0][2])


async def test_an_email_that_belongs_to_staff_is_reported_not_converted(client, auth_headers, sent_emails, superuser):
    hackathon = await _open_hackathon(client, auth_headers)
    boss_email = superuser[0].email
    resp = await _add(client, auth_headers, hackathon, [("Boss", boss_email), ("Good One", "good@example.com")])
    body = resp.json()
    assert body["created"] == 1  # the good row still went through
    assert body["errors"][0]["email"] == boss_email.lower()
    assert "isn't a student account" in body["errors"][0]["reason"]
    assert [e for e, _n, _t in sent_emails] == ["good@example.com"]


async def test_an_existing_student_record_without_a_login_is_linked_not_duplicated(
    client, db_session, auth_headers, organization, sent_emails
):
    from modules.students.repository import StudentRepository

    existing = await StudentRepository(db_session).create(
        organization.id, full_name="Kiran P", email="Kiran@Example.com", course_name="Old", enrollment_date=date(2026, 1, 1)
    )
    await db_session.flush()
    hackathon = await _open_hackathon(client, auth_headers)
    resp = await _add(client, auth_headers, hackathon, [("Kiran P", "kiran@example.com")])
    assert resp.json()["created"] == 1
    await db_session.refresh(existing)
    assert existing.user_id is not None
    count = (
        await db_session.execute(select(Student).where(Student.email.ilike("kiran@example.com")))
    ).scalars().all()
    assert len(count) == 1


async def test_participant_input_validation_and_permissions(client, db_session, auth_headers, sent_emails):
    hackathon = await _open_hackathon(client, auth_headers)
    assert (await _add(client, auth_headers, hackathon, [("No Email", "not-an-email")])).status_code == 422
    assert (await _add(client, auth_headers, hackathon, [])).status_code == 422
    too_many = [(f"S{i}", f"s{i}@example.com") for i in range(301)]
    assert (await _add(client, auth_headers, hackathon, too_many)).status_code == 422
    missing = await client.post(
        f"{_HACK}/{uuid.uuid4()}/participants",
        json={"participants": [{"name": "A", "email": "a@example.com"}]},
        headers=auth_headers,
    )
    assert missing.status_code == 404

    # A plain student cannot create other students' accounts.
    await _add(client, auth_headers, hackathon, [("Plain Student", "plain@example.com")])
    token = sent_emails[-1][2]
    plain = await _set_password_and_login(client, "plain@example.com", token)
    denied = await client.post(
        f"{_HACK}/{hackathon['id']}/participants",
        json={"participants": [{"name": "X", "email": "x@example.com"}]},
        headers=plain,
    )
    assert denied.status_code in (403, 422) and denied.status_code != 200


async def test_team_names_are_unique_and_a_full_team_cannot_be_joined(client, db_session, auth_headers, sent_emails):
    hackathon = await _open_hackathon(client, auth_headers, max_team_size=2)
    people = [("P One", "p1@example.com"), ("P Two", "p2@example.com"), ("P Three", "p3@example.com")]
    await _add(client, auth_headers, hackathon, people)
    tokens = {e: t for e, _n, t in sent_emails}
    heads = {e: await _set_password_and_login(client, e, tokens[e]) for _n, e in people}
    base = f"{_HACK}/{hackathon['id']}/teams"

    team = await client.post(f"{base}/me", json={"name": "Alpha"}, headers=heads["p1@example.com"])
    assert team.status_code == 201
    clash = await client.post(f"{base}/me", json={"name": "Alpha"}, headers=heads["p2@example.com"])
    assert clash.status_code == 409 and "already exists" in clash.text  # not a 500

    assert (await client.post(f"{base}/{team.json()['id']}/join/me", headers=heads["p2@example.com"])).status_code == 200
    full = await client.post(f"{base}/{team.json()['id']}/join/me", headers=heads["p3@example.com"])
    assert full.status_code == 422 and "maximum size" in full.text
    # The failed attempts did not leave p2/p3 in a half-registered state.
    assert (await client.get(f"{base}/me", headers=heads["p3@example.com"])).json() is None


async def test_login_and_set_password_limits_come_from_settings(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "AUTH_RESET_PASSWORD_RATE_LIMIT", "1000/minute")
    monkeypatch.setattr(settings, "AUTH_LOGIN_RATE_LIMIT", "1000/minute")
    for _ in range(12):  # well past the old 5/min and 10/min caps
        r = await client.post("/api/v1/auth/reset-password", json={"token": "x" * 32, "new_password": "Hackathon#2026"})
        assert r.status_code != 429
        r = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Whatever#1"})
        assert r.status_code != 429
