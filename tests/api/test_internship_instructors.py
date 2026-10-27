"""
Instructors on an internship: administrators assign trainers (one or many) for a period, and a trainer then works on that
internship with their own login -- everything except delete -- until the period ends, when it disappears for them.

What must hold: access exists only on the assigned internships and only inside the window, deletes are refused whatever the
route, instructors cannot create or delete internships or manage instructors, exams of the internship (and only those) are
open to them, and an administrator's access is untouched.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.employees.repository import EmployeeRepository
from modules.trainers.repository import TrainerRepository
from tests.api.test_internship_learning import _world
from tests.api.test_internship_projects import _purl
from tests.api.test_trainer_self_service import _create_trainer_with_login

pytestmark = pytest.mark.api

_INTERN = "/api/v1/our-internships"
_EXAMS = "/api/v1/workshop-exams"
_MINE = "/api/v1/instructing-internships"


def _iso(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


async def _assign(client, headers, internship, trainer, **dates):
    r = await client.post(f"{_INTERN}/{internship['id']}/instructors", json={"trainer_id": str(trainer.id), **dates}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _instructor(client, db_session, organization, name="Ila Instructor"):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization, name)
    return trainer, headers


# ------------------------------------------------------------ assigning


async def test_trainers_are_assigned_listed_changed_and_removed(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    one, _h1 = await _instructor(client, db_session, organization, "Ila Instructor")
    two, _h2 = await _instructor(client, db_session, organization, "Ben Mentor")
    url = f"{_INTERN}/{internship['id']}/instructors"
    options = (await client.get(f"{url}/options", headers=auth_headers)).json()
    assert {o["name"] for o in options} == {"Ila Instructor", "Ben Mentor"}
    first = await _assign(client, auth_headers, internship, one, access_from=_iso(-1), access_until=_iso(10), note="Guest mentor")
    await _assign(client, auth_headers, internship, two)  # many instructors; no dates means no limit
    listed = (await client.get(url, headers=auth_headers)).json()
    assert [(i["name"], i["status"]) for i in listed] == [("Ben Mentor", "active"), ("Ila Instructor", "active")]
    assert first["note"] == "Guest mentor"
    assert {o["name"] for o in (await client.get(f"{url}/options", headers=auth_headers)).json()} == set()  # both are assigned
    assert (await client.post(url, json={"trainer_id": str(one.id)}, headers=auth_headers)).status_code == 409
    extended = await client.patch(f"{url}/{first['id']}", json={"access_until": _iso(30)}, headers=auth_headers)
    assert extended.status_code == 200 and extended.json()["status"] == "active"
    gone = await client.delete(f"{url}/{first['id']}", headers=auth_headers)
    assert gone.status_code == 200
    assert [i["name"] for i in (await client.get(url, headers=auth_headers)).json()] == ["Ben Mentor"]
    assert (await client.delete(f"{url}/{first['id']}", headers=auth_headers)).status_code == 404


async def test_the_access_period_must_make_sense_and_the_trainer_must_be_usable(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, _h = await _instructor(client, db_session, organization)
    url = f"{_INTERN}/{internship['id']}/instructors"
    backwards = await client.post(url, json={"trainer_id": str(trainer.id), "access_from": _iso(5), "access_until": _iso(2)}, headers=auth_headers)
    assert backwards.status_code in (400, 422) and "end after" in backwards.text
    # a trainer with no login cannot be given access, and is not offered
    employee = await EmployeeRepository(db_session).create(organization_id=organization.id, full_name="No Login", date_of_joining=date(2024, 1, 1))
    nologin = await TrainerRepository(db_session).create(organization_id=organization.id, employee_id=employee.id)
    await db_session.flush()
    assert "No Login" not in {o["name"] for o in (await client.get(f"{url}/options", headers=auth_headers)).json()}
    refused = await client.post(url, json={"trainer_id": str(nologin.id)}, headers=auth_headers)
    assert refused.status_code in (400, 422) and "no login" in refused.text
    assert (await client.post(url, json={"trainer_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404
    inactive = await TrainerRepository(db_session).create(organization_id=organization.id, employee_id=(await EmployeeRepository(db_session).create(organization_id=organization.id, full_name="Gone", date_of_joining=date(2024, 1, 1))).id)
    inactive.is_active = False
    await db_session.flush()
    assert (await client.post(url, json={"trainer_id": str(inactive.id)}, headers=auth_headers)).status_code == 404
    good = await _assign(client, auth_headers, internship, trainer)
    bad_update = await client.patch(f"{url}/{good['id']}", json={"access_from": _iso(9), "access_until": _iso(3)}, headers=auth_headers)
    assert bad_update.status_code in (400, 422)


# ------------------------------------------------------------ the time window


async def test_access_exists_only_inside_the_window_and_follows_changes_at_once(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    url = f"{_INTERN}/{internship['id']}"
    row = await _assign(client, auth_headers, internship, trainer, access_from=_iso(2), access_until=_iso(9))
    assert row["status"] == "upcoming"
    assert (await client.get(f"{url}/performance", headers=mine)).status_code == 403  # not started
    assert (await client.get(_MINE, headers=mine)).json() == []
    started = await client.patch(f"{url}/instructors/{row['id']}", json={"access_from": _iso(-1)}, headers=auth_headers)
    assert started.json()["status"] == "active"
    assert (await client.get(f"{url}/performance", headers=mine)).status_code == 200
    assert [i["title"] for i in (await client.get(_MINE, headers=mine)).json()] == ["Pentrix Cyber Internship"]
    ended = await client.patch(f"{url}/instructors/{row['id']}", json={"access_until": _iso(-0.01)}, headers=auth_headers)
    assert ended.json()["status"] == "expired"
    assert (await client.get(f"{url}/performance", headers=mine)).status_code == 403  # gone the moment the period ends
    assert (await client.get(_INTERN, headers=mine)).status_code == 403  # and it is not theirs to list any more
    assert (await client.get(_MINE, headers=mine)).json() == []
    reopened = await client.patch(f"{url}/instructors/{row['id']}", json={"access_until": None}, headers=auth_headers)
    assert reopened.json()["status"] == "active" and (await client.get(f"{url}/performance", headers=mine)).status_code == 200
    await client.delete(f"{url}/instructors/{row['id']}", headers=auth_headers)
    assert (await client.get(f"{url}/performance", headers=mine)).status_code == 403  # removing takes it away immediately


async def test_an_instructor_sees_only_their_own_internships(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    other = (await client.post(_INTERN, json={"title": "Other programme", "scope": "all"}, headers=auth_headers)).json()
    trainer, mine = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer)
    listed = (await client.get(_INTERN, headers=mine)).json()
    assert [i["title"] for i in listed] == ["Pentrix Cyber Internship"]
    assert {i["title"] for i in (await client.get(_INTERN, headers=auth_headers)).json()} == {"Pentrix Cyber Internship", "Other programme"}  # administrators see all
    assert (await client.get(f"{_INTERN}/{other['id']}", headers=mine)).status_code == 403
    assert (await client.get(f"{_INTERN}/{other['id']}/performance", headers=mine)).status_code == 403
    assert (await client.get(f"{_INTERN}/{internship['id']}", headers=mine)).status_code == 200


async def test_what_an_instructor_may_do_is_told_to_the_screens(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer, access_from=_iso(-1), access_until=_iso(4))
    admin = (await client.get(f"{_INTERN}/{internship['id']}/my-access", headers=auth_headers)).json()
    assert (admin["role"], admin["can_delete"]) == ("admin", True)
    inst = (await client.get(f"{_INTERN}/{internship['id']}/my-access", headers=mine)).json()
    assert (inst["role"], inst["can_delete"], inst["status"]) == ("instructor", False, "active") and inst["access_until"]
    me = (await client.get("/api/v1/authorization/me", headers=mine)).json()
    assert "our_internships.view" in me["effective_permissions"]  # the menu item appears


async def test_the_menu_item_appears_only_for_a_trainer_who_instructs_something_now(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    assert "our_internships.view" not in (await client.get("/api/v1/authorization/me", headers=mine)).json()["effective_permissions"]
    row = await _assign(client, auth_headers, internship, trainer)
    assert "our_internships.view" in (await client.get("/api/v1/authorization/me", headers=mine)).json()["effective_permissions"]
    await client.patch(f"{_INTERN}/{internship['id']}/instructors/{row['id']}", json={"access_until": _iso(-1)}, headers=auth_headers)
    assert "our_internships.view" not in (await client.get("/api/v1/authorization/me", headers=mine)).json()["effective_permissions"]


# ------------------------------------------------------------ what an instructor can and cannot do


async def test_an_instructor_can_do_the_work_of_the_internship(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer)
    url = f"{_INTERN}/{internship['id']}"
    # assignments
    a = await client.post(f"{url}/assignments", json={"title": "Recon report", "max_marks": 50}, headers=mine)
    assert a.status_code == 201, a.text
    assert (await client.patch(f"{url}/assignments/{a.json()['id']}", json={"status": "published"}, headers=mine)).status_code == 200
    # projects and reviews
    p = await client.post(f"{url}/projects", json={"title": "Scanner", "allow_file": True}, headers=mine)
    assert p.status_code == 201 and (await client.patch(_purl(internship, p.json()), json={"status": "published"}, headers=mine)).status_code == 200
    # awards
    award = await client.post(f"{url}/awards", json={"name": "Best Project"}, headers=mine)
    assert award.status_code == 201
    given = await client.put(f"{url}/awards/{award.json()['id']}/grants", json={"selection_id": people["asha@example.com"][0]}, headers=mine)
    assert given.status_code == 200
    # students: add, import preview, validate
    inst = (await client.get(f"{url}/students/destinations", headers=mine)).json()
    assert inst and (await client.get(f"{url}/performance", headers=mine)).status_code == 200
    # certificates: open, choose, preview
    assert (await client.post(f"{url}/certificates/open", headers=mine)).status_code == 200
    chosen = await client.put(f"{url}/certificates/eligibility", json={"selection_ids": [people["asha@example.com"][0]], "kind": "completion"}, headers=mine)
    assert chosen.status_code == 200
    assert (await client.post(f"{url}/certificates/issue", json={"confirm": False}, headers=mine)).status_code == 200
    # onboarding views
    assert (await client.get(f"{url}/selected", headers=mine)).status_code == 200


async def test_an_instructor_can_never_delete_anything(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer)
    url = f"{_INTERN}/{internship['id']}"
    a = (await client.post(f"{url}/assignments", json={"title": "Recon", "max_marks": 10}, headers=auth_headers)).json()
    p = (await client.post(f"{url}/projects", json={"title": "Scanner", "allow_file": True}, headers=auth_headers)).json()
    award = (await client.post(f"{url}/awards", json={"name": "Best"}, headers=auth_headers)).json()
    await client.put(f"{url}/awards/{award['id']}/grants", json={"selection_id": people["asha@example.com"][0]}, headers=auth_headers)
    exam = (await client.post(_EXAMS, json={"title": "Quiz", "internship_id": internship["id"]}, headers=auth_headers)).json()
    q = (await client.post(f"{_EXAMS}/{exam['id']}/questions", json={"questions": [{"text": "2+2?", "options": ["3", "4"], "correct_indices": [1]}]}, headers=auth_headers)).json()
    attempts = [
        ("DELETE", url),
        ("DELETE", f"{url}/assignments/{a['id']}"),
        ("DELETE", f"{url}/projects/{p['id']}"),
        ("DELETE", f"{url}/awards/{award['id']}"),
        ("DELETE", f"{url}/awards/{award['id']}/grants/{people['asha@example.com'][0]}"),
        ("DELETE", f"{url}/exams/{exam['id']}/link"),
        ("DELETE", f"{_EXAMS}/{exam['id']}"),
        ("DELETE", f"{_EXAMS}/{exam['id']}/questions/{q[0]['id']}"),
    ]
    for method, path in attempts:
        r = await client.request(method, path, headers=mine)
        assert r.status_code == 403 and "cannot delete" in r.text, (method, path, r.status_code, r.text[:120])
    # nothing was removed: everything is still there for the administrator
    assert (await client.get(f"{url}/assignments/{a['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{url}/projects/{p['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(_EXAMS + f"/{exam['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(url, headers=auth_headers)).status_code == 200
    # while the administrator still can
    assert (await client.delete(f"{url}/assignments/{a['id']}", headers=auth_headers)).status_code == 200


async def test_an_instructor_cannot_create_internships_or_manage_instructors(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    other_trainer, _h = await _instructor(client, db_session, organization, "Another Trainer")
    await _assign(client, auth_headers, internship, trainer)
    assert (await client.post(_INTERN, json={"title": "Mine now", "scope": "all"}, headers=mine)).status_code == 403
    url = f"{_INTERN}/{internship['id']}/instructors"
    assert (await client.get(url, headers=mine)).status_code == 403
    assert (await client.get(f"{url}/options", headers=mine)).status_code == 403
    assert (await client.post(url, json={"trainer_id": str(other_trainer.id)}, headers=mine)).status_code == 403
    assert (await client.patch(f"{_INTERN}/{internship['id']}", json={"title": "Renamed"}, headers=mine)).status_code == 200  # editing is allowed


async def test_exams_of_the_internship_are_open_to_the_instructor_and_no_others(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    other = (await client.post(_INTERN, json={"title": "Other programme", "scope": "all"}, headers=auth_headers)).json()
    trainer, mine = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer)
    own = await client.post(_EXAMS, json={"title": "Week 1 quiz", "internship_id": internship["id"]}, headers=mine)
    assert own.status_code == 201, own.text
    exam_id = own.json()["id"]
    added = await client.post(f"{_EXAMS}/{exam_id}/questions", json={"questions": [{"text": "2+2?", "options": ["3", "4"], "correct_indices": [1]}]}, headers=mine)
    assert added.status_code == 201
    assert (await client.post(f"{_EXAMS}/{exam_id}/status", json={"status": "open"}, headers=mine)).status_code == 200
    assert (await client.get(f"{_EXAMS}/{exam_id}", headers=mine)).status_code == 200
    assigned = await client.post(f"{_INTERN}/{internship['id']}/exams/{exam_id}/assign", json={"send_invites": False}, headers=mine)
    assert assigned.status_code == 200
    # an exam for another internship, an exam of nobody's, and the workshop exam list are not theirs
    assert (await client.post(_EXAMS, json={"title": "Sneaky", "internship_id": other["id"]}, headers=mine)).status_code == 403
    assert (await client.post(_EXAMS, json={"title": "Loose exam"}, headers=mine)).status_code == 403
    loose = (await client.post(_EXAMS, json={"title": "Loose exam"}, headers=auth_headers)).json()
    assert (await client.get(f"{_EXAMS}/{loose['id']}", headers=mine)).status_code == 403
    theirs = (await client.post(_EXAMS, json={"title": "Other quiz", "internship_id": other["id"]}, headers=auth_headers)).json()
    assert (await client.post(f"{_EXAMS}/{theirs['id']}/questions", json={"questions": [{"text": "q", "options": ["a", "b"], "correct_indices": [0]}]}, headers=mine)).status_code == 403
    assert (await client.get(_EXAMS, headers=mine)).status_code == 403
    # once the access ends the exam is closed to them too
    row = (await client.get(f"{_INTERN}/{internship['id']}/instructors", headers=auth_headers)).json()[0]
    await client.patch(f"{_INTERN}/{internship['id']}/instructors/{row['id']}", json={"access_until": _iso(-1)}, headers=auth_headers)
    assert (await client.get(f"{_EXAMS}/{exam_id}", headers=mine)).status_code == 403


async def test_a_certificate_exam_is_open_to_the_instructor_for_designing_and_review(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer)
    overview = (await client.post(f"{_INTERN}/{internship['id']}/certificates/open", headers=mine)).json()
    exam_id = overview["certificates"][0]["exam_id"]
    assert (await client.get(f"{_EXAMS}/{exam_id}", headers=mine)).status_code == 200
    assert (await client.patch(f"{_EXAMS}/{exam_id}", json={"certificate_heading": "Certificate of Completion"}, headers=mine)).status_code == 200
    assert (await client.delete(f"{_EXAMS}/{exam_id}/certificate/template", headers=mine)).status_code == 403


async def test_an_ordinary_trainer_and_an_administrator_are_unaffected(client, auth_headers, staff_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, mine = await _instructor(client, db_session, organization)  # a trainer who is not assigned
    assert (await client.get(_INTERN, headers=mine)).status_code == 403
    assert (await client.get(f"{_INTERN}/{internship['id']}", headers=mine)).status_code == 403
    assert (await client.get(_MINE, headers=mine)).json() == []
    assert (await client.get(_INTERN, headers=staff_headers)).status_code == 403
    assert (await client.get(f"{_INTERN}/{internship['id']}", headers=auth_headers)).status_code == 200
    assert (await client.delete(f"{_INTERN}/{internship['id']}", headers=auth_headers)).status_code == 200


async def test_one_organization_cannot_assign_anothers_trainer(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    internship, _ = await _world(client, auth_headers, db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    foreign, _h = await _create_trainer_with_login(client, db_session, other, "Foreign Trainer")
    r = await client.post(f"{_INTERN}/{internship['id']}/instructors", json={"trainer_id": str(foreign.id)}, headers=auth_headers)
    assert r.status_code == 404
    assert "Foreign Trainer" not in {o["name"] for o in (await client.get(f"{_INTERN}/{internship['id']}/instructors/options", headers=auth_headers)).json()}
