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
    joined = await client.post(f"{_HACK}/{hackathon['id']}/teams/join/me", json={"code": team.json()["join_code"]}, headers=ravi)
    assert joined.status_code == 200, joined.text

    # Staff see who is in each team (and its code); there is no public list of teams to browse.
    staff = (await client.get(f"{_HACK}/{hackathon['id']}/teams", headers=auth_headers)).json()
    assert staff[0]["member_count"] == 2 and set(staff[0]["member_names"]) == {"Asha Rao", "Ravi Kumar"}
    assert staff[0]["join_code"] == team.json()["join_code"]
    assert (await client.get(f"{_HACK}/{hackathon['id']}/teams/browse", headers=ravi)).status_code in (404, 405)


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

    code = {"code": team.json()["join_code"]}
    assert (await client.post(f"{base}/join/me", json=code, headers=heads["p2@example.com"])).status_code == 200
    full = await client.post(f"{base}/join/me", json=code, headers=heads["p3@example.com"])
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
    await client.post(f"{_HACK}/{hackathon['id']}/teams/join/me", json={"code": team["join_code"]}, headers=ravi)
    return hackathon, team, asha, ravi


async def test_participants_get_the_restricted_role_not_the_student_role(client, db_session, auth_headers, sent_emails):
    hackathon = await _open_hackathon(client, auth_headers)
    await _add(client, auth_headers, hackathon, [("Asha Rao", "asha@example.com")])
    me = await _set_password_and_login(client, "asha@example.com", sent_emails[0][2])
    roles = (await client.get("/api/v1/authorization/me", headers=me)).json()
    assert [r["slug"] for r in roles["roles"]] == ["hackathon_participant"]
    # Only the marker permission: no course, cyber-range or LMS permission at all.
    assert roles["effective_permissions"] == ["hackathons.participate"]


async def _add_tasks(client, auth_headers, hackathon, titles):
    out = []
    for title in titles:
        r = await client.post(
            f"{_HACK}/{hackathon['id']}/problem-statements",
            json={"title": title, "description": f"Do: {title}"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        out.append(r.json())
    return out


def _task_url(hackathon, task):
    return f"{_HACK}/{hackathon['id']}/tasks/{task['id']}/submission/me"


async def test_tasks_are_staff_managed_and_visible_to_participants(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    a, b = await _add_tasks(client, auth_headers, hackathon, ["Fork the repository", "Provision the server"])

    mine = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()
    assert mine["team_id"] == team["id"] and mine["can_submit"] is True
    assert [t["title"] for t in mine["tasks"]] == ["Fork the repository", "Provision the server"]
    assert all(t["submission"] is None for t in mine["tasks"])

    # A participant can read tasks but not manage them.
    denied = await client.post(
        f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "Sneaky", "description": "x"}, headers=asha
    )
    assert denied.status_code in (403, 422)

    # Deleting a task removes its submissions with it.
    assert (await client.put(_task_url(hackathon, b), data={"repo_url": "https://hub.docker.com/r/x/y"}, headers=asha)).status_code == 200
    assert (await client.delete(f"{_HACK}/{hackathon['id']}/problem-statements/{b['id']}", headers=auth_headers)).status_code == 200
    after = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()
    assert [t["title"] for t in after["tasks"]] == ["Fork the repository"]
    assert (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json() == []


async def test_each_task_has_its_own_submission_and_nothing_carries_over(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    one, two = await _add_tasks(client, auth_headers, hackathon, ["Task one", "Task two"])

    first = await client.put(
        _task_url(hackathon, one),
        data={"repo_url": "https://github.com/acme/fork"},
        files={"file": ("one.pdf", _PDF, "application/pdf")},
        headers=asha,
    )
    assert first.status_code == 200, first.text
    assert first.json()["repo_url"] == "https://github.com/acme/fork" and first.json()["report"]["filename"] == "one.pdf"

    # Task two is untouched: no URL and no report from task one leaks in.
    tasks = {t["title"]: t for t in (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()["tasks"]}
    assert tasks["Task one"]["submission"]["repo_url"] == "https://github.com/acme/fork"
    assert tasks["Task two"]["submission"] is None

    second = await client.put(
        _task_url(hackathon, two), data={"repo_url": "https://hub.docker.com/r/acme/app"}, headers=ravi
    )
    assert second.status_code == 200 and second.json()["report"] is None
    assert second.json()["id"] != first.json()["id"]

    # Updating task two does not disturb task one.
    tasks = {t["title"]: t for t in (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()["tasks"]}
    assert tasks["Task one"]["submission"]["report"]["filename"] == "one.pdf"
    assert tasks["Task two"]["submission"]["repo_url"] == "https://hub.docker.com/r/acme/app"


async def test_task_submission_needs_a_report_or_a_url_and_validates_both(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    (task,) = await _add_tasks(client, auth_headers, hackathon, ["Only task"])
    url = _task_url(hackathon, task)
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"max_resubmissions": 10}, headers=auth_headers)

    assert (await client.put(url, data={}, headers=asha)).status_code == 422  # nothing to submit
    assert (await client.put(url, data={"repo_url": "   "}, headers=asha)).status_code == 422
    assert (await client.put(url, data={"repo_url": "ftp://x/y"}, headers=asha)).status_code == 422
    assert (await client.put(url, data={"repo_url": "not a url"}, headers=asha)).status_code == 422
    for name, data in (("r.exe", _PDF), ("r.pdf", b"not really a pdf"), ("r.pdf", _PDF + b"x" * (20 * 1024 * 1024))):
        bad = await client.put(url, files={"file": (name, data, "application/pdf")}, headers=asha)
        assert bad.status_code == 422, name

    ok = await client.put(url, files={"file": ("..\\..\\My Report.pdf", _PDF, "application/pdf")}, headers=asha)
    assert ok.status_code == 200, ok.text
    assert ok.json()["report"]["filename"] == "My Report.pdf" and ok.json()["repo_url"] is None

    # Sending only a URL keeps the saved report; an empty URL clears the URL; a new file replaces the report.
    both = await client.put(url, data={"repo_url": "https://ghcr.io/acme/app"}, headers=ravi)
    assert both.json()["repo_url"] == "https://ghcr.io/acme/app" and both.json()["report"]["filename"] == "My Report.pdf"
    cleared = await client.put(url, data={"repo_url": ""}, headers=ravi)
    assert cleared.json()["repo_url"] is None and cleared.json()["report"] is not None
    replaced = await client.put(url, files={"file": ("final.pdf", _PDF + b" v2", "application/pdf")}, headers=asha)
    assert replaced.json()["report"]["filename"] == "final.pdf"
    # ...and it can't end up with neither, nor does a no-change send use up a resubmission.
    unchanged = await client.put(url, data={"repo_url": ""}, files={}, headers=asha)
    assert unchanged.status_code == 422 and "Change the link" in unchanged.text

    got = await client.get(f"{url}/report", headers=ravi)
    assert got.status_code == 200 and got.content.endswith(b" v2") and got.headers["x-content-type-options"] == "nosniff"

    # Staff see it and can download it.
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert len(rows) == 1 and rows[0]["team_name"] == "Red Team" and rows[0]["report_filename"] == "final.pdf"
    dl = await client.get(f"{_HACK}/{hackathon['id']}/task-submissions/{rows[0]['id']}/report", headers=auth_headers)
    assert dl.status_code == 200 and dl.content.endswith(b" v2")

    # Not on a team = can't submit; closed hackathon = can't submit.
    await _add(client, auth_headers, hackathon, [("Loner", "loner@example.com")])
    loner = await _set_password_and_login(client, "loner@example.com", sent_emails[-1][2])
    assert (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=loner)).json()["can_submit"] is False
    assert (await client.put(url, data={"repo_url": "https://x.io/y"}, headers=loner)).status_code == 422
    assert (await client.get(f"{url}/report", headers=loner)).status_code == 404
    await client.post(f"{_HACK}/{hackathon['id']}/status", json={"status": "completed"}, headers=auth_headers)
    assert (await client.put(url, data={"repo_url": "https://x.io/late"}, headers=asha)).status_code == 422


async def test_leaderboard_is_the_sum_of_task_scores_and_updates_as_scores_are_awarded(
    client, db_session, auth_headers, sent_emails
):
    hackathon, red, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails, max_team_size=2)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")])
    tokens = {e: t for e, _n, t in sent_emails}
    meena = await _set_password_and_login(client, "meena@example.com", tokens["meena@example.com"])
    kiran = await _set_password_and_login(client, "kiran@example.com", tokens["kiran@example.com"])
    blue = (await client.post(f"{_HACK}/{hackathon['id']}/teams/me", json={"name": "Blue Team"}, headers=meena)).json()
    await client.post(f"{_HACK}/{hackathon['id']}/teams/join/me", json={"code": blue["join_code"]}, headers=kiran)
    one, two = await _add_tasks(client, auth_headers, hackathon, ["Task one", "Task two"])

    async def submit(headers, task):
        r = await client.put(_task_url(hackathon, task), data={"repo_url": "https://example.com/x"}, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    async def board(headers):
        boards = (await client.get(f"{_HACK}/leaderboard/me", headers=headers)).json()
        return next(b for b in boards if b["hackathon_id"] == hackathon["id"])

    red1, red2 = await submit(asha, one), await submit(asha, two)
    blue1 = await submit(meena, one)

    # Visible by default, but nothing is scored yet.
    first = await board(asha)
    assert first["published"] is True and first["entries"] == []

    async def grade(submission_id, score, feedback=None):
        r = await client.post(
            f"{_HACK}/{hackathon['id']}/task-submissions/{submission_id}/grade",
            json={"score": score, "feedback": feedback},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

    # Awarding one task's score puts that team on the board straight away.
    await grade(blue1, 7, "Good")
    entries = (await board(kiran))["entries"]
    assert [(e["team_name"], e["score"], e["tasks_scored"]) for e in entries] == [("Blue Team", 7, 1)]

    # Scores add up across tasks, and re-awarding changes the standing immediately.
    await grade(red1, 4)
    await grade(red2, 5)
    entries = (await board(asha))["entries"]
    assert [(e["rank"], e["team_name"], e["score"], e["tasks_scored"]) for e in entries] == [
        (1, "Red Team", 9, 2),
        (2, "Blue Team", 7, 1),
    ]
    await grade(red2, 1)  # lowered: Red is now 5
    entries = (await board(asha))["entries"]
    assert [(e["team_name"], e["score"]) for e in entries] == [("Blue Team", 7), ("Red Team", 5)]
    await grade(red2, 3)  # Red = 7 = Blue: a tie shares rank 1
    assert {(e["rank"], e["score"]) for e in (await board(asha))["entries"]} == {(1, 7)}

    # Students see their own score and feedback on the task.
    mine = {t["title"]: t for t in (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=meena)).json()["tasks"]}
    assert mine["Task one"]["submission"]["score"] == 7 and mine["Task one"]["submission"]["feedback"] == "Good"

    # Staff always see the live ranking and team totals, and can hide it from participants.
    live = (await client.get(f"{_HACK}/{hackathon['id']}/leaderboard", headers=auth_headers)).json()
    assert [e["score"] for e in live["entries"]] == [7, 7]
    teams = {t["name"]: t for t in (await client.get(f"{_HACK}/{hackathon['id']}/teams", headers=auth_headers)).json()}
    assert teams["Red Team"]["total_score"] == 7 and teams["Red Team"]["tasks_submitted"] == 2
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"leaderboard_visible": False}, headers=auth_headers)
    hidden = await board(asha)
    assert hidden["published"] is False and hidden["entries"] == []
    assert len((await client.get(f"{_HACK}/{hackathon['id']}/leaderboard", headers=auth_headers)).json()["entries"]) == 2

    # Only a valid score is accepted, and only for a submission of this hackathon.
    bad = await client.post(
        f"{_HACK}/{hackathon['id']}/task-submissions/{red1}/grade", json={"score": -1}, headers=auth_headers
    )
    assert bad.status_code == 422
    other = await _open_hackathon(client, auth_headers)
    wrong = await client.post(
        f"{_HACK}/{other['id']}/task-submissions/{red1}/grade", json={"score": 5}, headers=auth_headers
    )
    assert wrong.status_code == 404
    denied = await client.post(
        f"{_HACK}/{hackathon['id']}/task-submissions/{red1}/grade", json={"score": 50}, headers=asha
    )
    assert denied.status_code in (403, 422)


async def test_achievements_reflect_what_the_team_actually_did(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    one, two = await _add_tasks(client, auth_headers, hackathon, ["Task one", "Task two"])
    first = {a["code"] for a in (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()}
    assert first == {"participant"}

    submitted = await client.put(_task_url(hackathon, one), data={"repo_url": "https://example.com/a"}, headers=ravi)
    achievements = (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()
    tasks_award = next(a for a in achievements if a["code"] == "submitted")
    assert tasks_award["detail"] == "Your team has submitted 1 of 2 tasks."  # a teammate's submission counts for all

    await client.post(
        f"{_HACK}/{hackathon['id']}/task-submissions/{submitted.json()['id']}/grade", json={"score": 10}, headers=auth_headers
    )
    assert "winner" in {a["code"] for a in (await client.get(f"{_HACK}/achievements/me", headers=asha)).json()}


# ---------------- marks, sub-tasks, rubric ----------------


def _rubric_task(title="Provision the server", marks=20):
    return {
        "title": title,
        "marks": marks,
        "description": None,
        "sub_tasks": [{"title": "Launch the instance", "points": 10}, {"title": "Open the ports", "points": 5}],
        "rubric": [
            {"criterion": "Correct instance type and region", "points": 12},
            {"criterion": "Security group allows only what is needed", "points": 8},
        ],
    }


async def test_a_task_has_marks_optional_description_sub_tasks_and_a_rubric_that_must_fit(
    client, db_session, auth_headers
):
    hackathon = await _open_hackathon(client, auth_headers)
    url = f"{_HACK}/{hackathon['id']}/problem-statements"

    created = await client.post(url, json=_rubric_task(), headers=auth_headers)
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["marks"] == 20 and task["description"] is None  # description is optional
    assert [s["points"] for s in task["sub_tasks"]] == [10, 5]
    assert [r["points"] for r in task["rubric"]] == [12, 8]
    assert all(item["id"] for item in [*task["sub_tasks"], *task["rubric"]])

    # Sub-tasks or rubric adding up to more than the marks are refused, with the numbers in the message.
    too_many_sub = {**_rubric_task(), "sub_tasks": [{"title": "A", "points": 15}, {"title": "B", "points": 10}]}
    over = await client.post(url, json=too_many_sub, headers=auth_headers)
    assert over.status_code == 422 and "25" in over.text and "20" in over.text
    too_many_rubric = {**_rubric_task(), "rubric": [{"criterion": "Everything", "points": 21}]}
    assert (await client.post(url, json=too_many_rubric, headers=auth_headers)).status_code == 422
    no_marks = {**_rubric_task(), "marks": 0}
    assert (await client.post(url, json=no_marks, headers=auth_headers)).status_code == 422  # set the marks first
    assert (await client.post(url, json={"title": "Plain task", "marks": 5}, headers=auth_headers)).status_code == 201
    blank = {**_rubric_task(), "rubric": [{"criterion": "  ", "points": 1}]}
    assert (await client.post(url, json=blank, headers=auth_headers)).status_code == 422

    # Editing keeps the ids of rules that already existed, so marks awarded against them stay attached.
    rule_ids = [r["id"] for r in task["rubric"]]
    edited = await client.put(
        f"{url}/{task['id']}",
        json={**_rubric_task(), "rubric": [{**task["rubric"][0], "criterion": "Instance type"}, task["rubric"][1]]},
        headers=auth_headers,
    )
    assert edited.status_code == 200, edited.text
    assert [r["id"] for r in edited.json()["rubric"]] == rule_ids
    assert edited.json()["rubric"][0]["criterion"] == "Instance type"


async def test_students_see_marks_sub_tasks_and_the_rubric_skeleton(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json=_rubric_task(), headers=auth_headers)).json()

    seen = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()
    assert seen["max_total"] == 20
    row = seen["tasks"][0]
    assert row["marks"] == 20 and [s["title"] for s in row["sub_tasks"]] == ["Launch the instance", "Open the ports"]
    assert [r["points"] for r in row["rubric"]] == [12, 8]  # the rubric skeleton: criteria and their maximum
    assert row["submission"] is None

    submitted = await client.put(_task_url(hackathon, task), data={"repo_url": "https://hub.docker.com/r/o/p"}, headers=asha)
    assert submitted.status_code == 200
    assert submitted.json()["score"] is None and submitted.json()["rubric_scores"] is None  # not marked yet


async def test_rubric_grading_marks_each_rule_and_totals_them(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json=_rubric_task(), headers=auth_headers)).json()
    rule_a, rule_b = task["rubric"]
    sub = (await client.put(_task_url(hackathon, task), data={"repo_url": "https://ghcr.io/o/p"}, headers=asha)).json()
    grade_url = f"{_HACK}/{hackathon['id']}/task-submissions/{sub['id']}/grade"

    # Staff list shows the rubric and that nothing has been reviewed yet.
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert rows[0]["reviewed"] is False and rows[0]["task_marks"] == 20
    assert [r["points"] for r in rows[0]["rubric"]] == [12, 8]

    async def grade(body):
        return await client.post(grade_url, json=body, headers=auth_headers)

    assert (await grade({"score": 15})).status_code == 422  # a rubric task needs per-rule marks
    assert (await grade({"rubric_scores": {rule_a["id"]: 10}})).status_code == 422  # every rule must be marked
    assert (await grade({"rubric_scores": {rule_a["id"]: 13, rule_b["id"]: 1}})).status_code == 422  # above the rule's max
    assert (await grade({"rubric_scores": {rule_a["id"]: -1, rule_b["id"]: 1}})).status_code == 422
    assert (await grade({"rubric_scores": {rule_a["id"]: 1, rule_b["id"]: 1, "nope": 3}})).status_code == 422

    ok = await grade({"rubric_scores": {rule_a["id"]: 9, rule_b["id"]: 6}, "feedback": "Solid"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["score"] == 15 and ok.json()["rubric_scores"] == {rule_a["id"]: 9, rule_b["id"]: 6}

    # The student sees the marks per rule, the total and the feedback; staff see it as reviewed.
    mine = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()["tasks"][0]["submission"]
    assert mine["score"] == 15 and mine["rubric_scores"][rule_b["id"]] == 6 and mine["feedback"] == "Solid"
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert rows[0]["reviewed"] is True and rows[0]["score"] == 15

    # A task with no rubric takes one score, capped at the task's marks.
    plain = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "Plain", "marks": 10}, headers=auth_headers)).json()
    plain_sub = (await client.put(_task_url(hackathon, plain), data={"repo_url": "https://x.io/p"}, headers=asha)).json()
    plain_url = f"{_HACK}/{hackathon['id']}/task-submissions/{plain_sub['id']}/grade"
    assert (await client.post(plain_url, json={"score": 11}, headers=auth_headers)).status_code == 422
    assert (await client.post(plain_url, json={"score": 7}, headers=auth_headers)).json()["score"] == 7
    assert (await client.post(plain_url, json={}, headers=auth_headers)).status_code == 422


async def test_a_scored_task_keeps_its_marks_and_rubric_but_can_be_retitled(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json=_rubric_task(), headers=auth_headers)).json()
    sub = (await client.put(_task_url(hackathon, task), data={"repo_url": "https://ghcr.io/o/p"}, headers=asha)).json()
    rule_a, rule_b = task["rubric"]
    await client.post(
        f"{_HACK}/{hackathon['id']}/task-submissions/{sub['id']}/grade",
        json={"rubric_scores": {rule_a["id"]: 12, rule_b["id"]: 8}},
        headers=auth_headers,
    )
    url = f"{_HACK}/{hackathon['id']}/problem-statements/{task['id']}"
    changed_marks = await client.put(url, json={**_rubric_task(marks=30), "rubric": task["rubric"]}, headers=auth_headers)
    assert changed_marks.status_code == 422 and "already been scored" in changed_marks.text
    changed_points = await client.put(
        url, json={**_rubric_task(), "rubric": [{**rule_a, "points": 10}, rule_b]}, headers=auth_headers
    )
    assert changed_points.status_code == 422
    retitled = await client.put(
        url, json={**_rubric_task(title="Provision the EC2 server"), "rubric": task["rubric"]}, headers=auth_headers
    )
    assert retitled.status_code == 200 and retitled.json()["title"] == "Provision the EC2 server"


async def test_students_see_their_place_per_task_and_overall_only_while_the_leaderboard_is_shown(
    client, db_session, auth_headers, sent_emails
):
    hackathon, red, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails, max_team_size=2)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")])
    tokens = {e: t for e, _n, t in sent_emails}
    meena = await _set_password_and_login(client, "meena@example.com", tokens["meena@example.com"])
    blue = (await client.post(f"{_HACK}/{hackathon['id']}/teams/me", json={"name": "Blue Team"}, headers=meena)).json()
    kiran = await _set_password_and_login(client, "kiran@example.com", tokens["kiran@example.com"])
    await client.post(f"{_HACK}/{hackathon['id']}/teams/join/me", json={"code": blue["join_code"]}, headers=kiran)
    one = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 10}, headers=auth_headers)).json()
    two = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "Two", "marks": 10}, headers=auth_headers)).json()

    async def submit_and_grade(headers, task, score):
        sub = (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/a"}, headers=headers)).json()
        r = await client.post(
            f"{_HACK}/{hackathon['id']}/task-submissions/{sub['id']}/grade", json={"score": score}, headers=auth_headers
        )
        assert r.status_code == 200, r.text

    await submit_and_grade(asha, one, 9)  # red:  one=9
    await submit_and_grade(meena, one, 6)  # blue: one=6
    await submit_and_grade(asha, two, 3)  # red:  two=3 (red total 12)
    await submit_and_grade(meena, two, 8)  # blue: two=8 (blue total 14)

    red_view = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()
    assert red_view["max_total"] == 20 and red_view["leaderboard_visible"] is True
    assert (red_view["team_rank"], red_view["team_total"], red_view["teams_ranked"]) == (2, 12, 2)
    places = {t["title"]: (t["task_rank"], t["task_teams_scored"]) for t in red_view["tasks"]}
    assert places == {"One": (1, 2), "Two": (2, 2)}
    blue_view = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=kiran)).json()
    assert (blue_view["team_rank"], blue_view["team_total"]) == (1, 14)

    # The bar chart's scale: the board reports the maximum total available.
    board = next(b for b in (await client.get(f"{_HACK}/leaderboard/me", headers=asha)).json() if b["hackathon_id"] == hackathon["id"])
    assert board["max_total"] == 20

    # Hiding the leaderboard hides everyone's standing, including the team's own place.
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"leaderboard_visible": False}, headers=auth_headers)
    hidden = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()
    assert hidden["team_rank"] is None and all(t["task_rank"] is None for t in hidden["tasks"])
    assert hidden["tasks"][0]["submission"]["score"] == 9  # their own marks are still theirs to see


# ---------------- resubmission limits, re-review and deleting a submission ----------------


async def _graded(client, auth_headers, hackathon, task, sub, score):
    r = await client.post(
        f"{_HACK}/{hackathon['id']}/task-submissions/{sub['id']}/grade", json={"score": score}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_resubmission_is_limited_by_the_organiser_setting(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    assert hackathon["resubmission_enabled"] is True and hackathon["max_resubmissions"] == 2
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 10}, headers=auth_headers)).json()

    first = await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/1"}, headers=asha)
    assert first.status_code == 200 and first.json()["resubmission_count"] == 0

    view = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()
    assert view["resubmission_enabled"] is True and view["max_resubmissions"] == 2
    assert view["tasks"][0]["can_resubmit"] is True and view["tasks"][0]["resubmissions_left"] == 2

    # Sending the same thing again is not a resubmission and does not use one up.
    same = await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/1"}, headers=asha)
    assert same.status_code == 422 and "Change the link" in same.text

    assert (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/2"}, headers=ravi)).json()["resubmission_count"] == 1
    assert (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/3"}, headers=asha)).json()["resubmission_count"] == 2

    over = await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/4"}, headers=asha)
    assert over.status_code == 422 and "used all 2 resubmissions" in over.text
    view = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()
    assert view["tasks"][0]["can_resubmit"] is False and view["tasks"][0]["resubmissions_left"] == 0
    assert view["tasks"][0]["submission"]["repo_url"] == "https://x.io/3"

    # Raising the limit lets them carry on; the count is kept.
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"max_resubmissions": 3}, headers=auth_headers)
    assert (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/4"}, headers=asha)).json()["resubmission_count"] == 3

    # Turning resubmission off stops changes (a task not yet submitted can still be submitted).
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"resubmission_enabled": False, "max_resubmissions": 9}, headers=auth_headers)
    off = await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/5"}, headers=asha)
    assert off.status_code == 422 and "turned off" in off.text
    other = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "Two", "marks": 10}, headers=auth_headers)).json()
    assert (await client.put(_task_url(hackathon, other), data={"repo_url": "https://x.io/a"}, headers=asha)).status_code == 200
    view = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()
    assert view["resubmission_enabled"] is False and all(t["can_resubmit"] is False for t in view["tasks"])

    # A zero limit means "no resubmissions", and the setting is validated.
    bad = await client.patch(f"{_HACK}/{hackathon['id']}", json={"max_resubmissions": -1}, headers=auth_headers)
    assert bad.status_code == 422


async def test_a_resubmitted_task_needs_reviewing_again_but_keeps_its_old_score(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 10}, headers=auth_headers)).json()
    sub = (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/1"}, headers=asha)).json()
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert rows[0]["reviewed"] is False and rows[0]["resubmission_count"] == 0

    await _graded(client, auth_headers, hackathon, task, sub, 6)
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert rows[0]["reviewed"] is True

    await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/2"}, headers=asha)
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert rows[0]["reviewed"] is False and rows[0]["resubmission_count"] == 1 and rows[0]["score"] == 6
    mine = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()["tasks"][0]["submission"]
    assert mine["reviewed"] is False and mine["score"] == 6  # the earlier marks stay until it is re-scored
    board = (await client.get(f"{_HACK}/{hackathon['id']}/leaderboard", headers=auth_headers)).json()
    assert board["entries"][0]["score"] == 6

    await _graded(client, auth_headers, hackathon, task, sub, 9)
    rows = (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json()
    assert rows[0]["reviewed"] is True and rows[0]["score"] == 9


async def test_staff_can_delete_a_submission_and_the_team_can_submit_that_task_again(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 10}, headers=auth_headers)).json()
    await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/1"}, headers=asha)
    sub = (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/2"}, headers=asha)).json()
    await _graded(client, auth_headers, hackathon, task, sub, 8)

    url = f"{_HACK}/{hackathon['id']}/task-submissions/{sub['id']}"
    # Only staff who can manage the hackathon may delete; a participant cannot.
    assert (await client.delete(url, headers=asha)).status_code == 403
    assert (await client.delete(url, headers=auth_headers)).status_code == 204
    assert (await client.delete(url, headers=auth_headers)).status_code == 404
    assert (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json() == []
    board = (await client.get(f"{_HACK}/{hackathon['id']}/leaderboard", headers=auth_headers)).json()
    assert all(entry["score"] == 0 for entry in board["entries"])

    view = (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()["tasks"][0]
    assert view["submission"] is None
    fresh = await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/3"}, headers=asha)
    assert fresh.status_code == 200 and fresh.json()["resubmission_count"] == 0  # a clean slate
    assert fresh.json()["score"] is None


# ---------------- organiser team and member controls ----------------


def _members_of(roster, team_name):
    team = next(t for t in roster if t["name"] == team_name)
    return {m["email"]: m for m in team["members"]}


async def _roster(client, auth_headers, hackathon):
    r = await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_roster_shows_every_member_with_contact_details(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")])  # a login, never signed in, no team
    roster = await _roster(client, auth_headers, hackathon)
    assert [t["name"] for t in roster] == ["Red Team"]
    members = _members_of(roster, "Red Team")
    assert set(members) == {"asha@example.com", "ravi@example.com"}
    assert members["asha@example.com"]["is_creator"] is True and members["ravi@example.com"]["is_creator"] is False
    assert members["asha@example.com"]["has_logged_in"] is True

    # People who aren't in a team yet are offered when adding members (searchable), those in a team are not.
    found = (await client.get(f"{_HACK}/{hackathon['id']}/candidates", params={"q": "meena"}, headers=auth_headers)).json()
    assert [c["email"] for c in found] == ["meena@example.com"]
    everyone = (await client.get(f"{_HACK}/{hackathon['id']}/candidates", headers=auth_headers)).json()
    assert "asha@example.com" not in [c["email"] for c in everyone]
    # A participant can't use any of this.
    assert (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=asha)).status_code == 403
    assert (await client.delete(f"{_HACK}/{hackathon['id']}/teams/{team['id']}", headers=asha)).status_code == 403


async def test_staff_can_rename_create_and_delete_teams(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    base = f"{_HACK}/{hackathon['id']}/teams"

    assert (await client.patch(f"{base}/{team['id']}", json={"name": "  Crimson   Team "}, headers=auth_headers)).status_code == 200
    assert [t["name"] for t in await _roster(client, auth_headers, hackathon)] == ["Crimson Team"]
    assert (await client.patch(f"{base}/{team['id']}", json={"name": "   "}, headers=auth_headers)).status_code == 422

    # A new team made by staff, led by a brand-new person (they get a login and a welcome email).
    sent_emails.clear()
    made = await client.post(
        base, json={"name": "Blue Team", "member": {"name": "Kiran P", "email": "Kiran@Example.com"}}, headers=auth_headers
    )
    assert made.status_code == 201, made.text
    assert [e for e, *_ in sent_emails] == ["kiran@example.com"]
    dup = await client.post(
        base, json={"name": "Blue Team", "member": {"name": "Z Z", "email": "zz@example.com"}}, headers=auth_headers
    )
    assert dup.status_code == 409 and "already exists" in dup.text
    # ...and the failed attempt did not leave a login behind.
    ghost = await client.get(f"{_HACK}/{hackathon['id']}/candidates", params={"q": "zz@example.com"}, headers=auth_headers)
    assert ghost.json() == []
    blue = next(t for t in await _roster(client, auth_headers, hackathon) if t["name"] == "Blue Team")
    rename_clash = await client.patch(f"{base}/{blue['id']}", json={"name": "Crimson Team"}, headers=auth_headers)
    assert rename_clash.status_code == 409

    # Deleting a team removes its members' places and its submissions, but not their logins.
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 10}, headers=auth_headers)).json()
    await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/1"}, headers=asha)
    assert (await client.delete(f"{base}/{team['id']}", headers=auth_headers)).status_code == 200
    assert (await client.delete(f"{base}/{team['id']}", headers=auth_headers)).status_code == 404
    assert (await client.get(f"{_HACK}/{hackathon['id']}/task-submissions", headers=auth_headers)).json() == []
    assert (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=asha)).json()["team_id"] is None
    back = await client.post(f"{base}/me", json={"name": "Red Again"}, headers=asha)
    assert back.status_code == 201  # their login still works and they can start over


async def test_staff_can_add_remove_and_move_members_within_the_team_size(client, db_session, auth_headers, sent_emails):
    hackathon, red, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails, max_team_size=2)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")])
    tokens = {e: t for e, _n, t in sent_emails}
    meena = await _set_password_and_login(client, "meena@example.com", tokens["meena@example.com"])
    blue = (await client.post(f"{_HACK}/{hackathon['id']}/teams/me", json={"name": "Blue Team"}, headers=meena)).json()
    candidates = (await client.get(f"{_HACK}/{hackathon['id']}/candidates", params={"q": "kiran"}, headers=auth_headers)).json()
    kiran_id = candidates[0]["student_id"]
    roster = await _roster(client, auth_headers, hackathon)
    ids = {m["email"]: m["student_id"] for t in roster for m in t["members"]}

    # Red is full (2 of 2): adding is refused, and the message says how to get a bigger team.
    full = await client.post(f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members", json={"student_id": kiran_id}, headers=auth_headers)
    assert full.status_code == 422 and "maximum team size" in full.text
    # Blue has room.
    ok = await client.post(f"{_HACK}/{hackathon['id']}/teams/{blue['id']}/members", json={"student_id": kiran_id}, headers=auth_headers)
    assert ok.status_code == 201, ok.text
    again = await client.post(f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members", json={"student_id": kiran_id}, headers=auth_headers)
    assert again.status_code == 409 and "already in team" in again.text

    # Moving needs room in the target team, and then the member really changes team.
    move_full = await client.post(f"{_HACK}/{hackathon['id']}/members/{ids['ravi@example.com']}/move", json={"team_id": blue["id"]}, headers=auth_headers)
    assert move_full.status_code == 422
    same = await client.post(f"{_HACK}/{hackathon['id']}/members/{ids['ravi@example.com']}/move", json={"team_id": red["id"]}, headers=auth_headers)
    assert same.status_code == 422
    assert (await client.delete(f"{_HACK}/{hackathon['id']}/teams/{blue['id']}/members/{kiran_id}", headers=auth_headers)).status_code == 200
    moved = await client.post(f"{_HACK}/{hackathon['id']}/members/{ids['ravi@example.com']}/move", json={"team_id": blue["id"]}, headers=auth_headers)
    assert moved.status_code == 200, moved.text
    roster = await _roster(client, auth_headers, hackathon)
    assert set(_members_of(roster, "Red Team")) == {"asha@example.com"}
    assert set(_members_of(roster, "Blue Team")) == {"meena@example.com", "ravi@example.com"}
    # Ravi's student view follows the move; removing a member that isn't in the team is a 404.
    assert (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()["team_id"] == blue["id"]
    assert (await client.delete(f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members/{kiran_id}", headers=auth_headers)).status_code == 404

    # Staff can add a brand-new person straight into a team (login + welcome email), or someone who already has a login.
    sent_emails.clear()
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"max_team_size": 4}, headers=auth_headers)
    fresh = await client.post(
        f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members", json={"name": "Dev Patel", "email": "dev@example.com"}, headers=auth_headers
    )
    assert fresh.status_code == 201 and [e for e, *_ in sent_emails] == ["dev@example.com"]
    reuse = await client.post(
        f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members", json={"name": "Kiran P", "email": "kiran@example.com"}, headers=auth_headers
    )
    assert reuse.status_code == 201 and len(sent_emails) == 1  # no second login, no second email
    assert set(_members_of(await _roster(client, auth_headers, hackathon), "Red Team")) == {
        "asha@example.com",
        "dev@example.com",
        "kiran@example.com",
    }
    assert (await client.post(f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members", json={}, headers=auth_headers)).status_code == 422


async def test_staff_can_correct_a_members_name_phone_and_login_email(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    ids = {m["email"]: m["student_id"] for t in await _roster(client, auth_headers, hackathon) for m in t["members"]}
    url = f"{_HACK}/{hackathon['id']}/members/{ids['asha@example.com']}"
    old_token = next(t for e, _n, t in sent_emails if e == "asha@example.com")

    # Name and phone only: no email goes out, the login is untouched.
    sent_emails.clear()
    r = await client.patch(url, json={"full_name": "  Asha  Rao-Iyer ", "phone": "+91 99999 11111"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    member = _members_of(await _roster(client, auth_headers, hackathon), "Red Team")["asha@example.com"]
    assert member["full_name"] == "Asha Rao-Iyer" and member["phone"] == "+91 99999 11111"
    assert sent_emails == []
    assert (await client.get("/api/v1/auth/me", headers=asha)).status_code == 200  # still signed in

    # Changing the email: the login moves to the new address, old sessions end, a new link goes to the new address.
    assert (await client.patch(url, json={"email": "ravi@example.com"}, headers=auth_headers)).status_code == 409  # taken
    changed = await client.patch(url, json={"email": "Asha.New@Example.com"}, headers=auth_headers)
    assert changed.status_code == 200 and "new email" in changed.json()["message"]
    assert [e for e, *_ in sent_emails] == ["asha.new@example.com"]
    assert (await client.post("/api/v1/auth/login", json={"email": "asha@example.com", "password": "Hackathon#2026"})).status_code == 401
    new_token = sent_emails[0][2]
    relogin = await _set_password_and_login(client, "asha.new@example.com", new_token, password="Another#Pass2026")
    assert (await client.get("/api/v1/auth/me", headers=relogin)).status_code == 200
    assert "asha.new@example.com" in _members_of(await _roster(client, auth_headers, hackathon), "Red Team")
    # The earlier set-password link (sent to the old address) no longer works.
    dead = await client.post("/api/v1/auth/reset-password", json={"token": old_token, "new_password": "Whatever#Pass2026"})
    assert dead.status_code in (400, 401, 422)

    # Optionally skip the email; clearing the phone works; a bad address is rejected.
    sent_emails.clear()
    ravi_url = f"{_HACK}/{hackathon['id']}/members/{ids['ravi@example.com']}"
    quiet = await client.patch(ravi_url, json={"email": "ravi.k@example.com", "send_login_link": False, "phone": ""}, headers=auth_headers)
    assert quiet.status_code == 200 and sent_emails == []
    assert (await client.patch(ravi_url, json={"email": "not-an-email"}, headers=auth_headers)).status_code == 422
    assert (await client.patch(ravi_url, json={"full_name": "   "}, headers=auth_headers)).status_code == 422

    # Re-sending a login link works for a team member.
    link = await client.post(f"{ravi_url}/login-link", headers=auth_headers)
    assert link.status_code == 200 and "ravi.k@example.com" in link.json()["message"]
    assert [e for e, *_ in sent_emails] == ["ravi.k@example.com"]
    # ...but not for someone outside this hackathon's teams.
    assert (await client.patch(f"{_HACK}/{hackathon['id']}/members/{uuid.uuid4()}", json={"full_name": "X"}, headers=auth_headers)).status_code == 404


async def test_an_account_with_staff_access_cannot_be_edited_through_a_team(client, db_session, auth_headers, sent_emails):
    from sqlalchemy import select

    from modules.authorization.repository import AuthorizationRepository
    from modules.students.models import Student

    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    ids = {m["email"]: m["student_id"] for t in await _roster(client, auth_headers, hackathon) for m in t["members"]}
    student = (await db_session.execute(select(Student).where(Student.id == uuid.UUID(ids["ravi@example.com"])))).scalar_one()
    repo = AuthorizationRepository(db_session)
    role = await repo.get_role_by_slug("administrator")
    await repo.assign_role(student.user_id, role.id, None)
    await db_session.commit()

    r = await client.patch(f"{_HACK}/{hackathon['id']}/members/{ids['ravi@example.com']}", json={"email": "boss@example.com"}, headers=auth_headers)
    assert r.status_code == 422 and "Users" in r.text
    # Their own team membership can still be managed (that is not changing the login).
    assert (await client.delete(f"{_HACK}/{hackathon['id']}/teams/{team['id']}/members/{ids['ravi@example.com']}", headers=auth_headers)).status_code == 200


# ---------------- everyone invited: list, login links, remove, delete ----------------


async def _participants(client, auth_headers, hackathon):
    r = await client.get(f"{_HACK}/{hackathon['id']}/participants", headers=auth_headers)
    assert r.status_code == 200, r.text
    return {p["email"]: p for p in r.json()}


async def test_invited_participants_are_listed_with_team_and_sign_in_status(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")])  # invited, not signed in, no team
    again = await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")])
    assert again.json()["already_have_login"] == 1  # inviting twice does not duplicate her

    people = await _participants(client, auth_headers, hackathon)
    assert set(people) == {"asha@example.com", "ravi@example.com", "meena@example.com"}
    asha_row, meena_row = people["asha@example.com"], people["meena@example.com"]
    assert asha_row["team_name"] == "Red Team" and asha_row["is_creator"] is True and asha_row["has_logged_in"] is True
    assert asha_row["last_login_at"] is not None and asha_row["invited_at"] is not None
    assert meena_row["team_name"] is None and meena_row["has_logged_in"] is False and meena_row["last_login_at"] is None
    assert meena_row["student_code"] and meena_row["can_delete_account"] is True

    # People invited to another hackathon don't show up here, and participants can't read the list.
    other = await _open_hackathon(client, auth_headers)
    await _add(client, auth_headers, other, [("Kiran P", "kiran@example.com")])
    assert set(await _participants(client, auth_headers, hackathon)) == set(people)
    assert set(await _participants(client, auth_headers, other)) == {"kiran@example.com"}
    assert (await client.get(f"{_HACK}/{hackathon['id']}/participants", headers=asha)).status_code == 403

    # A new person added straight into a team is on the list too, and teamless invitees are the "add member" candidates.
    await client.post(
        f"{_HACK}/{hackathon['id']}/teams/{team['id']}/members", json={"name": "Dev Patel", "email": "dev@example.com"}, headers=auth_headers
    )
    assert "dev@example.com" in await _participants(client, auth_headers, hackathon)
    found = (await client.get(f"{_HACK}/{hackathon['id']}/candidates", headers=auth_headers)).json()
    assert [c["email"] for c in found] == ["meena@example.com"]

    # Someone with other access (a course student) can be edited or removed but not deleted from here.
    from sqlalchemy import select

    from modules.authorization.repository import AuthorizationRepository
    from modules.students.models import Student

    ravi_student = (await db_session.execute(select(Student).where(Student.email == "ravi@example.com"))).scalars().first()
    repo = AuthorizationRepository(db_session)
    await repo.assign_role(ravi_student.user_id, (await repo.get_role_by_slug("student")).id, None)
    await db_session.commit()
    assert (await _participants(client, auth_headers, hackathon))["ravi@example.com"]["can_delete_account"] is False


async def test_login_links_go_to_those_who_have_not_signed_in(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")])
    sent_emails.clear()
    url = f"{_HACK}/{hackathon['id']}/participants/login-links"

    r = await client.post(url, json={}, headers=auth_headers)
    assert r.status_code == 200 and "Sent 2 set-password links" in r.json()["message"]
    assert sorted(e for e, *_ in sent_emails) == ["kiran@example.com", "meena@example.com"]  # not Asha or Ravi: they've signed in

    people = await _participants(client, auth_headers, hackathon)
    sent_emails.clear()
    picked = await client.post(url, json={"student_ids": [people["asha@example.com"]["student_id"]]}, headers=auth_headers)
    assert picked.status_code == 200 and [e for e, *_ in sent_emails] == ["asha@example.com"]  # chosen people always get one
    # The link works.
    assert (await _set_password_and_login(client, "asha@example.com", sent_emails[0][2], password="Fresh#Pass2026"))
    assert (await client.post(url, json={}, headers=asha)).status_code == 403


async def test_staff_can_remove_participants_from_the_hackathon_or_delete_their_accounts(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")])
    people = await _participants(client, auth_headers, hackathon)
    ids = {e: p["student_id"] for e, p in people.items()}
    url = f"{_HACK}/{hackathon['id']}/participants/remove"

    # Remove from the hackathon: out of the team and off the list, but the login still works.
    r = await client.post(url, json={"student_ids": [ids["ravi@example.com"]]}, headers=auth_headers)
    assert r.status_code == 200 and r.json() == {"done": 1, "skipped": []}
    assert "ravi@example.com" not in await _participants(client, auth_headers, hackathon)
    assert (await client.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "Hackathon#2026"})).status_code == 200
    assert (await client.get(f"{_HACK}/{hackathon['id']}/tasks/me", headers=ravi)).json()["team_id"] is None
    assert [m["email"] for m in (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)).json()[0]["members"]] == ["asha@example.com"]
    # Removing someone who isn't on the list is reported, not an error.
    again = await client.post(url, json={"student_ids": [ids["ravi@example.com"]]}, headers=auth_headers)
    assert again.json()["done"] == 0 and again.json()["skipped"][0]["name"] == "Ravi Kumar"

    # Delete accounts, in bulk. The team's creator can go too: the team stays.
    deleted = await client.post(url, json={"student_ids": [ids["meena@example.com"], ids["asha@example.com"]], "delete_account": True}, headers=auth_headers)
    assert deleted.status_code == 200 and deleted.json()["done"] == 2, deleted.text
    gone = await client.post("/api/v1/auth/login", json={"email": "meena@example.com", "password": "anything"})
    assert gone.status_code == 401
    assert (await client.get("/api/v1/authorization/me", headers=asha)).status_code in (401, 403)  # their session is over
    assert set(await _participants(client, auth_headers, hackathon)) == {"kiran@example.com"}
    roster = (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)).json()
    assert [t["name"] for t in roster] == ["Red Team"] and roster[0]["members"] == []

    # The email address is free again: inviting it makes a fresh account.
    sent_emails.clear()
    reinvite = await _add(client, auth_headers, hackathon, [("Meena Again", "meena@example.com")])
    assert reinvite.json()["created"] == 1 and [e for e, *_ in sent_emails] == ["meena@example.com"]

    # Accounts with other access, and people not on this hackathon's list, are skipped with a reason.
    from sqlalchemy import select

    from modules.authorization.repository import AuthorizationRepository
    from modules.students.models import Student

    kiran = (await db_session.execute(select(Student).where(Student.email == "kiran@example.com"))).scalars().first()
    repo = AuthorizationRepository(db_session)
    await repo.assign_role(kiran.user_id, (await repo.get_role_by_slug("administrator")).id, None)
    await db_session.commit()
    refused = await client.post(url, json={"student_ids": [ids["kiran@example.com"], str(uuid.uuid4())], "delete_account": True}, headers=auth_headers)
    assert refused.json()["done"] == 0 and len(refused.json()["skipped"]) == 2
    assert "other access" in refused.json()["skipped"][0]["reason"]
    assert "kiran@example.com" in await _participants(client, auth_headers, hackathon)  # untouched
    # A participant can't do any of this.
    assert (await client.post(url, json={"student_ids": [ids["kiran@example.com"]]}, headers=ravi)).status_code == 403


# ---------------- joining a team by its code ----------------


async def test_a_team_is_joined_only_with_its_code_which_only_its_members_and_staff_can_see(client, db_session, auth_headers, sent_emails):
    hackathon = await _open_hackathon(client, auth_headers)
    await _add(client, auth_headers, hackathon, [("Asha Rao", "asha@example.com"), ("Ravi Kumar", "ravi@example.com"), ("Meena S", "meena@example.com")])
    tokens = {e: t for e, _n, t in sent_emails}
    asha = await _set_password_and_login(client, "asha@example.com", tokens["asha@example.com"])
    ravi = await _set_password_and_login(client, "ravi@example.com", tokens["ravi@example.com"])
    meena = await _set_password_and_login(client, "meena@example.com", tokens["meena@example.com"])
    base = f"{_HACK}/{hackathon['id']}/teams"

    red = (await client.post(f"{base}/me", json={"name": "Red Team"}, headers=asha)).json()
    code = red["join_code"]
    import re as _re

    assert _re.fullmatch(r"[A-HJ-KM-NP-Z2-9]{6}", code)  # six characters, no look-alikes
    blue = (await client.post(f"{base}/me", json={"name": "Blue Team"}, headers=meena)).json()
    assert blue["join_code"] != code

    # The code reaches the team's own members and staff; nobody else gets it.
    assert (await client.get(f"{base}/me", headers=asha)).json()["team"]["join_code"] == code
    assert [t["join_code"] for t in (await client.get(base, headers=auth_headers)).json()] == [code, blue["join_code"]]
    assert (await client.get(f"{base}/browse", headers=ravi)).status_code in (404, 405)
    # The old join-by-id door is closed.
    assert (await client.post(f"{base}/{red['id']}/join/me", headers=ravi)).status_code in (404, 405)

    # A wrong, empty or other-hackathon code gets the same plain answer and joins nothing.
    other = await _open_hackathon(client, auth_headers)
    await _add(client, auth_headers, other, [("Kiran P", "kiran@example.com")])
    kiran = await _set_password_and_login(client, "kiran@example.com", sent_emails[-1][2])
    other_team = (await client.post(f"{_HACK}/{other['id']}/teams/me", json={"name": "Elsewhere"}, headers=kiran)).json()
    for bad in ("ZZZZZZ", "   ", other_team["join_code"][:-1], other_team["join_code"]):
        r = await client.post(f"{base}/join/me", json={"code": bad}, headers=ravi)
        assert r.status_code == 422 and "isn't right" in r.text, bad
    assert (await client.get(f"{base}/me", headers=ravi)).json() is None

    # The right code works however it is typed.
    typed = f" {code[:3].lower()}-{code[3:].lower()} "
    joined = await client.post(f"{base}/join/me", json={"code": typed}, headers=ravi)
    assert joined.status_code == 200, joined.text
    assert (await client.get(f"{base}/me", headers=ravi)).json()["team"]["name"] == "Red Team"
    # Already in a team: a second join is refused.
    assert (await client.post(f"{base}/join/me", json={"code": blue["join_code"]}, headers=ravi)).status_code == 409


async def test_staff_can_replace_a_team_code_and_teams_made_by_staff_get_one(client, db_session, auth_headers, sent_emails):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    base = f"{_HACK}/{hackathon['id']}/teams"
    old = team["join_code"]
    assert [t["join_code"] for t in (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)).json()] == [old]

    r = await client.post(f"{base}/{team['id']}/code", headers=auth_headers)
    assert r.status_code == 200, r.text
    new = (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)).json()[0]["join_code"]
    assert new != old and new in r.json()["message"]
    assert (await client.post(f"{base}/{team['id']}/code", headers=asha)).status_code == 403  # participants can't

    # The replaced code no longer works; the new one does.
    await _add(client, auth_headers, hackathon, [("Meena S", "meena@example.com")])
    meena = await _set_password_and_login(client, "meena@example.com", sent_emails[-1][2])
    assert (await client.post(f"{base}/join/me", json={"code": old}, headers=meena)).status_code == 422
    assert (await client.post(f"{base}/join/me", json={"code": new}, headers=meena)).status_code == 200

    # A team made by staff has a code too, distinct from the others.
    made = await client.post(base, json={"name": "Green Team", "member": {"name": "Dev Patel", "email": "dev@example.com"}}, headers=auth_headers)
    assert made.status_code == 201
    codes = [t["join_code"] for t in (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)).json()]
    assert len(codes) == 2 and len(set(codes)) == 2


# ---------------- public live leaderboard link ----------------


@pytest.fixture
def no_public_cache(monkeypatch):
    from modules.hackathons import routes

    monkeypatch.setattr(routes, "_PUBLIC_CACHE_SECONDS", 0)
    routes._public_cache.clear()


async def _public(client, slug):
    return await client.get(f"{_HACK}/public/leaderboard/{slug}")  # deliberately no auth headers


async def test_the_public_leaderboard_link_is_off_until_shared_and_needs_no_login(client, db_session, auth_headers, sent_emails, no_public_cache):
    hackathon, team, asha, ravi = await _two_member_team(client, db_session, auth_headers, sent_emails)
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 50}, headers=auth_headers)).json()
    sub = (await client.put(_task_url(hackathon, task), data={"repo_url": "https://x.io/1"}, headers=asha)).json()
    await client.post(f"{_HACK}/{hackathon['id']}/task-submissions/{sub['id']}/grade", json={"score": 42}, headers=auth_headers)

    # Nothing is shared by default.
    assert hackathon["leaderboard_share_enabled"] is False and hackathon["leaderboard_slug"] is None
    assert hackathon["leaderboard_share_url"] is None
    assert (await _public(client, "devsecstorm")).status_code == 404

    # Turning sharing on picks a link name from the title; the page then works without any login.
    on = await client.patch(f"{_HACK}/{hackathon['id']}", json={"leaderboard_share_enabled": True}, headers=auth_headers)
    assert on.status_code == 200, on.text
    slug = on.json()["leaderboard_slug"]
    assert slug.startswith("devsecstorm") and on.json()["leaderboard_share_url"].endswith(f"/live/{slug}")
    page = await _public(client, slug)
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["title"] == "DevSecStorm" and body["max_total"] == 50
    assert [(e["rank"], e["team_name"], e["score"]) for e in body["entries"]] == [(1, "Red Team", 42)]
    assert body["entries"][0]["members"] == [] and body["show_members"] is False  # names stay private by default
    assert page.headers["x-robots-tag"] == "noindex" and "max-age" in page.headers["cache-control"]
    assert (await _public(client, slug.upper())).status_code == 200  # case doesn't matter

    # Showing member names is the organiser's choice.
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"leaderboard_show_members": True}, headers=auth_headers)
    shown = (await _public(client, slug)).json()
    assert set(shown["entries"][0]["members"]) == {"Asha Rao", "Ravi Kumar"} and shown["show_members"] is True

    # The page follows the scores live (no stale copy), and turning sharing off closes it at once.
    sub2 = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "Two", "marks": 50}, headers=auth_headers)).json()
    s2 = (await client.put(_task_url(hackathon, sub2), data={"repo_url": "https://x.io/2"}, headers=asha)).json()
    await client.post(f"{_HACK}/{hackathon['id']}/task-submissions/{s2['id']}/grade", json={"score": 8}, headers=auth_headers)
    assert (await _public(client, slug)).json()["entries"][0]["score"] == 50
    await client.patch(f"{_HACK}/{hackathon['id']}", json={"leaderboard_share_enabled": False}, headers=auth_headers)
    assert (await _public(client, slug)).status_code == 404
    # The link name is kept for next time.
    assert (await client.get(f"{_HACK}/{hackathon['id']}", headers=auth_headers)).json()["leaderboard_slug"] == slug


async def test_the_link_name_can_be_edited_but_not_duplicated_or_malformed(client, db_session, auth_headers, sent_emails, no_public_cache):
    first = await _open_hackathon(client, auth_headers)
    second = await _open_hackathon(client, auth_headers)
    url = f"{_HACK}/{first['id']}"
    await client.patch(url, json={"leaderboard_share_enabled": True}, headers=auth_headers)
    old = (await client.get(url, headers=auth_headers)).json()["leaderboard_slug"]

    # Edited to whatever the organiser likes; it is tidied (lower case, spaces and underscores to hyphens).
    edited = await client.patch(url, json={"leaderboard_slug": "  Pentrix Live_Finals 2026 "}, headers=auth_headers)
    assert edited.status_code == 200 and edited.json()["leaderboard_slug"] == "pentrix-live-finals-2026"
    assert edited.json()["leaderboard_share_url"].endswith("/live/pentrix-live-finals-2026")
    assert (await _public(client, "pentrix-live-finals-2026")).status_code == 200
    assert (await _public(client, old)).status_code == 404  # the old link stops working

    # Another hackathon can't take the same link name (the same hackathon re-saving it is fine).
    await client.patch(f"{_HACK}/{second['id']}", json={"leaderboard_share_enabled": True}, headers=auth_headers)
    clash = await client.patch(f"{_HACK}/{second['id']}", json={"leaderboard_slug": "Pentrix-Live-Finals-2026"}, headers=auth_headers)
    assert clash.status_code == 409 and "already used" in clash.text
    assert (await client.patch(url, json={"leaderboard_slug": "pentrix-live-finals-2026"}, headers=auth_headers)).status_code == 200

    # Too short / odd characters only / cleared: refused; sharing off + the same slug on a third hackathon still clashes.
    for bad in ("ab", "!!!", "-"):
        assert (await client.patch(url, json={"leaderboard_slug": bad}, headers=auth_headers)).status_code == 422, bad
    kept = await client.patch(url, json={"leaderboard_slug": None}, headers=auth_headers)
    assert kept.status_code == 200 and kept.json()["leaderboard_slug"] == "pentrix-live-finals-2026"  # can't be cleared

    # Only organisers who manage hackathons can change any of it.
    await _add(client, auth_headers, first, [("Asha Rao", "asha@example.com")])
    asha = await _set_password_and_login(client, "asha@example.com", sent_emails[-1][2])
    assert (await client.patch(url, json={"leaderboard_share_enabled": False}, headers=asha)).status_code == 403
    assert (await _public(client, "pentrix-live-finals-2026")).status_code == 200
