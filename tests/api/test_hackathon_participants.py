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


# ---------------- restricted participant role, problem statements, reports, leaderboard ----------------

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


async def _two_member_team(client, db_session, auth_headers, sent_emails, max_team_size=4):
    hackathon = await _open_hackathon(client, auth_headers, max_team_size=max_team_size)
    await _add(client, auth_headers, hackathon, [("Asha Rao", "asha@example.com"), ("Ravi Kumar", "ravi@example.com")])
    tokens = {e: t for e, _n, t in sent_emails}
    asha = await _set_password_and_login(client, "asha@example.com", tokens["asha@example.com"])
    ravi = await _set_password_and_login(client, "ravi@example.com", tokens["ravi@example.com"])
    team = (await client.post(f"{_HACK}/{hackathon['id']}/teams/me", json={"name": "Red Team"}, headers=asha)).json()
    await client.post(f"{_HACK}/{hackathon['id']}/teams/{team['id']}/join/me", headers=ravi)
    return hackathon, team, asha, ravi


async def test_participants_get_the_restricted_role_not_the_student_role(client, db_session, auth_headers, sent_emails):
    hackathon = await _open_hackathon(client, auth_headers)
    await _add(client, auth_headers, hackathon, [("Asha Rao", "asha@example.com")])
    me = await _set_password_and_login(client, "asha@example.com", sent_emails[0][2])
    roles = (await client.get("/api/v1/authorization/me", headers=me)).json()
    assert [r["slug"] for r in roles["roles"]] == ["hackathon_participant"]
    # Only the marker permission: no course, cyber-range or LMS permission at all.
    assert roles["effective_permissions"] == ["hackathons.participate"]


async def test_problem_statements_are_managed_by_staff_and_chosen_by_the_team(
    client, db_session, auth_headers, sent_emails
):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    base = f"{_HACK}/{hackathon['id']}/problem-statements"
    a = await client.post(base, json={"title": "Secure the login", "description": "Find and fix auth bugs."}, headers=auth_headers)
    b = await client.post(base, json={"title": "Harden the API", "description": "Rate limits and validation."}, headers=auth_headers)
    assert a.status_code == 201 and b.status_code == 201

    # A participant can read them but not change them.
    listed = await client.get(f"{base}/me", headers=asha)
    assert [p["title"] for p in listed.json()] == ["Secure the login", "Harden the API"]
    assert (await client.post(base, json={"title": "Sneaky", "description": "x"}, headers=asha)).status_code in (403, 422)

    # Either team member can pick one; it shows on their team and to staff.
    chosen = await client.put(
        f"{_HACK}/{hackathon['id']}/teams/me/problem-statement",
        json={"problem_statement_id": b.json()["id"]},
        headers=ravi,
    )
    assert chosen.status_code == 200 and chosen.json()["problem_statement_title"] == "Harden the API"
    mine = (await client.get(f"{_HACK}/{hackathon['id']}/teams/me", headers=asha)).json()
    assert mine["team"]["problem_statement_title"] == "Harden the API"
    staff = (await client.get(f"{_HACK}/{hackathon['id']}/teams", headers=auth_headers)).json()
    assert staff[0]["problem_statement_title"] == "Harden the API"

    # A statement from another hackathon can't be picked.
    other = await _open_hackathon(client, auth_headers)
    foreign = await client.post(
        f"{_HACK}/{other['id']}/problem-statements", json={"title": "Elsewhere", "description": "x"}, headers=auth_headers
    )
    bad = await client.put(
        f"{_HACK}/{hackathon['id']}/teams/me/problem-statement",
        json={"problem_statement_id": foreign.json()["id"]},
        headers=asha,
    )
    assert bad.status_code == 404

    # Deleting a statement just un-picks it for teams that had it.
    assert (await client.delete(f"{base}/{b.json()['id']}", headers=auth_headers)).status_code == 200
    after = (await client.get(f"{_HACK}/{hackathon['id']}/teams/me", headers=asha)).json()
    assert after["team"]["problem_statement_title"] is None


async def test_report_upload_validation_download_and_replacement(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    url = f"{_HACK}/{hackathon['id']}/teams/me/report"

    def upload(headers, name, data, ctype="application/pdf"):
        return client.put(url, files={"file": (name, data, ctype)}, headers=headers)

    assert (await upload(asha, "report.exe", _PDF)).status_code == 422  # type not allowed
    assert (await upload(asha, "report.pdf", b"not really a pdf")).status_code == 422  # wrong contents
    assert (await upload(asha, "report.pdf", b"")).status_code == 422
    assert (await upload(asha, "report.pdf", _PDF + b"x" * (20 * 1024 * 1024))).status_code == 422  # > 20 MB

    ok = await upload(asha, "..\\..\\My Report.pdf", _PDF)
    assert ok.status_code == 200, ok.text
    assert ok.json()["filename"] == "My Report.pdf"  # path stripped

    # The teammate sees it and can replace it; there is still just one.
    mine = (await client.get(f"{_HACK}/{hackathon['id']}/teams/me", headers=ravi)).json()
    assert mine["report"]["filename"] == "My Report.pdf"
    assert (await upload(ravi, "final.pdf", _PDF + b" v2")).status_code == 200
    got = await client.get(f"{url}/download", headers=asha)
    assert got.status_code == 200 and got.content.endswith(b" v2") and got.headers["content-type"] == "application/pdf"
    assert got.headers["x-content-type-options"] == "nosniff"

    # Staff see and can download every team's report.
    staff = (await client.get(f"{_HACK}/{hackathon['id']}/teams", headers=auth_headers)).json()
    assert staff[0]["has_report"] is True and staff[0]["report_filename"] == "final.pdf"
    dl = await client.get(f"{_HACK}/{hackathon['id']}/teams/{team['id']}/report", headers=auth_headers)
    assert dl.status_code == 200 and dl.content.endswith(b" v2")

    # A student on no team can't upload or download anything.
    await _add(client, auth_headers, hackathon, [("Loner", "loner@example.com")])
    loner = await _set_password_and_login(client, "loner@example.com", sent_emails[-1][2])
    assert (await upload(loner, "r.pdf", _PDF)).status_code == 422
    assert (await client.get(f"{url}/download", headers=loner)).status_code == 404

    # Once the hackathon is closed to submissions, uploads stop.
    await client.post(f"{_HACK}/{hackathon['id']}/status", json={"status": "completed"}, headers=auth_headers)
    assert (await upload(asha, "late.pdf", _PDF)).status_code == 422


async def test_leaderboard_stays_hidden_until_published_and_ties_share_a_rank(
    client, db_session, auth_headers, sent_emails
):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails, max_team_size=2)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")])
    tokens = {e: t for e, _n, t in sent_emails}
    meena = await _set_password_and_login(client, "meena@example.com", tokens["meena@example.com"])
    kiran = await _set_password_and_login(client, "kiran@example.com", tokens["kiran@example.com"])
    blue = (await client.post(f"{_HACK}/{hackathon['id']}/teams/me", json={"name": "Blue Team"}, headers=meena)).json()
    await client.post(f"{_HACK}/{hackathon['id']}/teams/{blue['id']}/join/me", headers=kiran)

    for headers, tid, title in ((asha, team["id"], "Red project"), (meena, blue["id"], "Blue project")):
        r = await client.post(
            f"{_HACK}/{hackathon['id']}/teams/{tid}/submissions/me", json={"title": title}, headers=headers
        )
        assert r.status_code in (200, 201), r.text
    subs = (await client.get(f"{_HACK}/{hackathon['id']}/submissions", headers=auth_headers)).json()
    for sub in subs:
        graded = await client.post(f"{_HACK}/submissions/{sub['id']}/grade", json={"score": 80}, headers=auth_headers)
        assert graded.status_code == 200

    hidden = (await client.get(f"{_HACK}/leaderboard/me", headers=asha)).json()
    board = next(b for b in hidden if b["hackathon_id"] == hackathon["id"])
    assert board["published"] is False and board["entries"] == []
    assert not (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()[0]["code"] in ("winner",)

    shown = await client.patch(f"{_HACK}/{hackathon['id']}", json={"leaderboard_visible": True}, headers=auth_headers)
    assert shown.status_code == 200 and shown.json()["leaderboard_visible"] is True
    board = next(b for b in (await client.get(f"{_HACK}/leaderboard/me", headers=kiran)).json() if b["hackathon_id"] == hackathon["id"])
    assert board["published"] is True
    assert [(e["rank"], e["score"]) for e in board["entries"]] == [(1, 80), (1, 80)]  # a tie shares rank 1
    assert {e["team_name"] for e in board["entries"]} == {"Red Team", "Blue Team"}

    codes = {a["code"] for a in (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()}
    assert {"participant", "submitted", "winner"} <= codes


async def test_achievements_reflect_what_the_team_actually_did(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    first = {a["code"] for a in (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()}
    assert first == {"participant"}
    await client.put(
        f"{_HACK}/{hackathon['id']}/teams/me/report", files={"file": ("r.pdf", _PDF, "application/pdf")}, headers=ravi
    )
    after = {a["code"] for a in (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()}
    assert after == {"participant", "report"}  # the teammate's upload counts for the whole team
