"""
Where a student sees the course linked to their internship: the onboarding page (title, description, level, duration; never a price or
content; a link only once access is granted), My Internships (the course next to the internship, its access status, withdrawn access
shown as such), My Courses (the student's own internships that gave them each course), and the welcome emails for new and existing
accounts. The internship record stays the only source: nothing is copied onto the student. Synthetic data only.
"""

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from modules.our_internships import onboarding
from modules.our_internships.models import InternshipSelection
from tests.api.test_internship_lms_integrity import course_in, grant, ready, revoke
from tests.api.test_internship_onboarding import BASE, PUBLIC, configure, link, tok, world

pytestmark = pytest.mark.api


async def student_login(db, selection):
    """The headers of the account that LMS access created for this selection."""
    await db.refresh(selection)
    return {"Authorization": f"Bearer {create_access_token(str(selection.lms_user_id))}"}


async def selection_of(db, internship, student):
    return (await db.execute(select(InternshipSelection).where(InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student.id))).scalar_one()


async def a_course(db, organization, title="DevSecOps Level-1", **over):
    course = await course_in(db, organization, title=title)
    course.short_description, course.duration_hours = "Hands-on DevSecOps", 40
    for key, value in over.items():
        setattr(course, key, value)
    await db.flush()
    return course


# ------------------------------------------------------------ the onboarding page


async def test_the_onboarding_page_shows_the_course_without_a_price_or_a_way_in_before_access(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await a_course(db_session, organization)
    internship.lms_course_id = course.id
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    page = (await client.get(PUBLIC, headers=tok(token))).json()
    shown = page["learning_course"]
    assert (shown["title"], shown["description"], shown["level"], shown["duration_hours"]) == ("DevSecOps Level-1", "Hands-on DevSecOps", "beginner", 40)
    assert (shown["accessible"], shown["lms_url"]) == (False, None)  # no way into the course before access is granted
    assert set(shown) == {"title", "description", "level", "duration_hours", "accessible", "lms_url"}  # no price, no content, no ids
    assert page["internship"]["title"] == internship.title
    # after the grant the page says so and points at the LMS; revoking takes it away again
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    granted = (await client.get(PUBLIC, headers=tok(token))).json()["learning_course"]
    assert granted["accessible"] is True and granted["lms_url"].endswith(f"/courses/{course.id}")
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert (await client.get(PUBLIC, headers=tok(token))).json()["learning_course"]["lms_url"] is None


async def test_with_no_course_linked_the_onboarding_page_has_no_course_section(client, auth_headers, db_session, organization):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    assert (await client.get(PUBLIC, headers=tok(token))).json()["learning_course"] is None


async def test_the_course_follows_a_rename_on_the_page_because_it_is_read_not_copied(client, auth_headers, db_session, organization):
    internship, (s0, _) = await world(db_session, organization)
    course = await a_course(db_session, organization)
    internship.lms_course_id = course.id
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    course.title = "DevSecOps Level-1 (2027)"
    await db_session.flush()
    assert (await client.get(PUBLIC, headers=tok(token))).json()["learning_course"]["title"] == "DevSecOps Level-1 (2027)"


# ------------------------------------------------------------ My Internships


async def test_my_internships_shows_the_course_its_status_and_the_way_in_and_hides_everything_once_access_is_withdrawn(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    course = await a_course(db_session, organization)
    internship.lms_course_id = course.id
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    mine = await student_login(db_session, await selection_of(db_session, internship, s0))
    listed = (await client.get("/api/v1/my-internships", headers=mine)).json()
    assert len(listed) == 1 and listed[0]["title"] == internship.title and listed[0]["lms_status"] == "granted"
    assert listed[0]["course"] == {"id": str(course.id), "title": "DevSecOps Level-1", "level": "beginner", "duration_hours": 40, "accessible": True}
    detail = (await client.get(f"/api/v1/my-internships/{internship.id}", headers=mine)).json()
    assert detail["course"]["title"] == "DevSecOps Level-1" and detail["course"]["accessible"] is True
    assert (await client.get(f"/api/v1/courses/{course.id}/me", headers=mine)).status_code == 200  # the navigation target really opens

    # the link is read from what they were given: relinking later (old data could) does not change their course
    other = await a_course(db_session, organization, title="Another course")
    internship.lms_course_id = other.id
    await db_session.flush()
    assert (await client.get("/api/v1/my-internships", headers=mine)).json()[0]["course"]["title"] == "DevSecOps Level-1"
    internship.lms_course_id = course.id
    await db_session.flush()

    # withdrawn: nothing of the internship or the course opens, and it is no longer listed (as before this feature)
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert (await client.get("/api/v1/my-internships", headers=mine)).json() == []
    assert (await client.get(f"/api/v1/my-internships/{internship.id}", headers=mine)).status_code in (403, 404)
    assert (await client.get(f"/api/v1/courses/{course.id}/me", headers=mine)).status_code == 403
    # another student on the same internship never sees this student's data
    await ready(db_session, internship, s1)
    assert (await grant(client, auth_headers, internship, s1)).status_code == 200
    theirs = await student_login(db_session, await selection_of(db_session, internship, s1))
    assert [i["lms_status"] for i in (await client.get("/api/v1/my-internships", headers=theirs)).json()] == ["granted"]


# ------------------------------------------------------------ My Courses


async def test_my_courses_names_the_students_own_internships_and_leaves_ordinary_courses_alone(client, auth_headers, db_session, organization, rbac_seeded):
    from datetime import date

    from modules.lms.enrollment.repository import EnrollmentRepository

    first, (a0, a1) = await world(db_session, organization)
    second, (b0, _) = await world(db_session, organization)
    shared = await a_course(db_session, organization)
    first.lms_course_id = second.lms_course_id = shared.id
    b0.email = a0.email  # the same person on both internships
    await db_session.flush()
    for internship, student in ((first, a0), (second, b0), (first, a1)):
        await ready(db_session, internship, student)
        assert (await grant(client, auth_headers, internship, student)).status_code == 200
    mine = await student_login(db_session, await selection_of(db_session, first, a0))
    ordinary = await course_in(db_session, organization, title="An ordinary course")
    erpx_student = (await db_session.execute(select(InternshipSelection.lms_student_id).where(InternshipSelection.student_id == a0.id))).scalar_one()
    await EnrollmentRepository(db_session).create(student_id=erpx_student, course_id=ordinary.id, enrolled_on=date.today())
    await db_session.flush()
    rows = {r["course_id"]: r for r in (await client.get("/api/v1/lms/enrollment/me", headers=mine)).json()}
    assert sorted(i["title"] for i in rows[str(shared.id)]["internships"]) == sorted([first.title, second.title])  # one course, two internships
    assert rows[str(ordinary.id)]["internships"] == []
    other_person = await student_login(db_session, await selection_of(db_session, first, a1))
    seen = (await client.get("/api/v1/lms/enrollment/me", headers=other_person)).json()
    assert [i["title"] for i in seen[0]["internships"]] == [first.title]  # only their own association, not the other person's


# ------------------------------------------------------------ the welcome emails


def test_a_new_account_gets_one_welcome_with_the_secure_link_the_internship_and_the_course(monkeypatch):
    import asyncio

    import modules.authentication.tasks as tasks
    from modules.email_templates.render import render_default

    sent: list = []
    queued: list = []
    monkeypatch.setattr(onboarding.send_password_reset_email_task, "delay", lambda *args: queued.append(args))
    outcome = onboarding.GrantOutcome(created_account=True, email="new@example.com", full_name="Asha Rao", reset_token="tok123", course_title="DevSecOps Level-1", internship_title="DevSecOps Internship")
    asyncio.run(onboarding.notify_access(outcome))
    assert len(queued) == 1  # one email, not an invite plus a welcome
    to, name, link, kind, extra = queued[0]
    assert kind == "internship_access" and link.endswith("/reset-password?token=tok123") and extra["link_valid_hours"] == onboarding.SET_PASSWORD_TOKEN_TTL_HOURS

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append((to, subject, text, html))
        return True

    monkeypatch.setattr(tasks.email_service, "send", fake_send)
    monkeypatch.setattr(tasks, "render_email_sync", lambda key, values, **kw: render_default(key, values))  # the built-in wording
    tasks.send_password_reset_email_task(to, name, link, kind, extra)
    ((_, subject, text, html),) = sent
    assert "DevSecOps Internship" in subject
    for needle in ("DevSecOps Internship", "DevSecOps Level-1", "tok123", "72 hours", "My Courses", "/login"):
        assert needle in text, needle  # who it is for, what they are enrolled in, how to activate, where to go
    assert "tok123" in html


async def test_an_existing_account_gets_the_welcome_naming_the_internship_and_the_course(db_session, organization, monkeypatch):
    from contextlib import asynccontextmanager

    from tests.api.test_email_studio import _make_user

    mailed: list = []

    async def send(to, subject, text, html=None, attachments=None):
        mailed.append((to, subject, text))
        return True

    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr("app.db.session.get_db_context", same_session)
    monkeypatch.setattr(onboarding.email_service, "send", send)
    await _make_user(db_session, organization, is_superuser=False, email="known@example.com")
    await onboarding.notify_access(onboarding.GrantOutcome(created_account=False, email="known@example.com", full_name="Ravi", reset_token=None, course_title="DevSecOps Level-1", internship_title="DevSecOps Internship"))
    assert len(mailed) == 1 and "DevSecOps Internship" in mailed[0][2] and "DevSecOps Level-1" in mailed[0][2] and "My Courses" in mailed[0][2]


async def test_each_grant_sends_exactly_one_welcome_and_a_refused_grant_sends_none(client, auth_headers, db_session, organization, rbac_seeded, monkeypatch):
    internship, (s0, s1) = await world(db_session, organization)
    course = await a_course(db_session, organization)
    internship.lms_course_id = course.id
    for s in (s0, s1):
        await ready(db_session, internship, s)
    calls: list = []

    async def record(outcome):
        calls.append(outcome.email)

    monkeypatch.setattr("modules.our_internships.routes.notify_access", record)
    done = (await client.post(f"{BASE}/{internship.id}/lms/grant", json={"student_ids": [str(s0.id), str(s1.id)]}, headers=auth_headers)).json()
    assert done["granted"] == 2 and sorted(calls) == sorted([s0.email.lower(), s1.email.lower()])
    again = await client.post(f"{BASE}/{internship.id}/lms/grant", json={"student_ids": [str(s0.id)]}, headers=auth_headers)
    assert again.json()["granted"] == 0 and len(calls) == 2  # already granted: nothing is sent a second time
