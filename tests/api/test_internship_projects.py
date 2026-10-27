"""
Internship projects: staff create projects, enrolled students choose one and hand it in by file, email or repository link.

What must hold: one project per student (switchable only until something is handed in), capacity is respected, a student
can only submit the way the project allows and only for the project they chose, deadlines apply, emailed work is confirmed
by staff, and uploaded files are validated and cleaned up.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.internship_learning import files as files_module
from modules.internship_learning.models import InternshipFile
from tests.api.test_internship_learning import FakeStorage, _world

pytestmark = pytest.mark.api

_INTERN = "/api/v1/our-internships"
_MINE = "/api/v1/my-internships"


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(files_module, "get_storage_client", lambda: fake)
    return fake


async def _project(client, headers, internship, publish=True, **over):
    body = {"title": "Network scanner", "description": "Build one.", "allow_file": True, **over}
    r = await client.post(f"{_INTERN}/{internship['id']}/projects", json=body, headers=headers)
    assert r.status_code == 201, r.text
    project = r.json()
    if publish:
        p = await client.patch(_purl(internship, project), json={"status": "published"}, headers=headers)
        assert p.status_code == 200, p.text
        project = p.json()
    return project


def _purl(internship, project, tail=""):
    return f"{_INTERN}/{internship['id']}/projects/{project['id']}{tail}"


def _murl(internship, project, tail=""):
    return f"{_MINE}/{internship['id']}/projects/{project['id']}{tail}"


async def _choose(client, student, internship, project):
    return await client.post(_murl(internship, project, "/choose"), headers=student)


async def _submit(client, student, internship, project, method="file", files=(("code.zip", b"PK zip"),), **data):
    return await client.post(
        _murl(internship, project, "/submission"),
        data={"method": method, **data},
        files=[("files", (name, content, "application/zip")) for name, content in files],
        headers=student,
    )


# ------------------------------------------------------------ staff: projects


async def test_a_project_is_created_as_a_draft_edited_published_and_deleted(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    p = await _project(client, auth_headers, internship, publish=False, objectives="Learn scanning", rules="No cheating")
    assert p["status"] == "draft" and p["rules"] == "No cheating" and p["chosen_count"] == 0
    edited = await client.patch(_purl(internship, p), json={"title": "Port scanner", "capacity": 5}, headers=auth_headers)
    assert edited.json()["title"] == "Port scanner" and edited.json()["capacity"] == 5
    assert (await client.patch(_purl(internship, p), json={"status": "published"}, headers=auth_headers)).json()["status"] == "published"
    assert len((await client.get(f"{_INTERN}/{internship['id']}/projects", headers=auth_headers)).json()) == 1
    assert (await client.delete(_purl(internship, p), headers=auth_headers)).status_code == 200
    assert (await client.get(_purl(internship, p), headers=auth_headers)).status_code == 404


async def test_a_project_needs_a_way_to_submit_and_valid_details(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    base = f"{_INTERN}/{internship['id']}/projects"
    none = await client.post(base, json={"title": "x", "allow_file": False}, headers=auth_headers)
    assert none.status_code in (400, 422) and "at least one way" in none.text
    no_address = await client.post(base, json={"title": "x", "allow_email": True}, headers=auth_headers)
    assert no_address.status_code in (400, 422) and "email address" in no_address.text
    bad_email = await client.post(base, json={"title": "x", "allow_email": True, "submission_email": "nope"}, headers=auth_headers)
    assert bad_email.status_code in (400, 422)
    bad_link = await client.post(base, json={"title": "x", "reference_links": [{"id": "l1", "title": "Docs", "url": "javascript:alert(1)"}]}, headers=auth_headers)
    assert bad_link.status_code in (400, 422)
    good = await client.post(base, json={"title": "x", "reference_links": [{"id": "l1", "title": "Docs", "url": "https://example.com/docs"}]}, headers=auth_headers)
    assert good.status_code == 201 and good.json()["reference_links"][0]["url"] == "https://example.com/docs"
    dates = await client.post(base, json={"title": "x", "starts_at": "2026-12-02T00:00:00Z", "deadline_at": "2026-12-01T00:00:00Z"}, headers=auth_headers)
    assert dates.status_code in (400, 422)


async def test_documents_and_templates_are_kept_separately_and_removed(client, auth_headers, db_session, organization, storage):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    p = await _project(client, auth_headers, internship)
    doc = await client.post(_purl(internship, p, "/files"), files={"file": ("spec.pdf", b"%PDF", "application/pdf")}, headers=auth_headers)
    tpl = await client.post(_purl(internship, p, "/files?kind=template"), files={"file": ("report.docx", b"docx", "application/octet-stream")}, headers=auth_headers)
    assert doc.status_code == 201 and tpl.status_code == 201
    got = (await client.get(_purl(internship, p), headers=auth_headers)).json()
    assert [f["filename"] for f in got["documents"]] == ["spec.pdf"] and [f["filename"] for f in got["templates"]] == ["report.docx"]
    assert (await client.post(_purl(internship, p, "/files?kind=bogus"), files={"file": ("a.txt", b"a", "text/plain")}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.post(_purl(internship, p, "/files"), files={"file": ("virus.exe", b"MZ", "application/octet-stream")}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.delete(_purl(internship, p, f"/files/{tpl.json()['id']}"), headers=auth_headers)).status_code == 200
    assert len(storage.objects) == 1
    assert (await client.delete(_purl(internship, p, f"/files/{uuid.uuid4()}"), headers=auth_headers)).status_code == 404


# ------------------------------------------------------------ the student: choosing


async def test_students_see_published_projects_with_their_documents_and_choose_one(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    draft = await _project(client, auth_headers, internship, publish=False, title="Draft")
    live = await _project(client, auth_headers, internship, title="Live")
    await client.post(_purl(internship, live, "/files"), files={"file": ("spec.pdf", b"%PDF", "application/pdf")}, headers=auth_headers)
    listed = (await client.get(f"{_MINE}/{internship['id']}/projects", headers=asha)).json()
    assert [p["title"] for p in listed] == ["Live"] and listed[0]["can_choose"] is True and listed[0]["documents"][0]["filename"] == "spec.pdf"
    assert (await _choose(client, asha, internship, draft)).status_code == 404
    chosen = await _choose(client, asha, internship, live)
    assert chosen.status_code == 200 and chosen.json()["chosen_by_me"] is True and chosen.json()["can_submit"] is True
    again = await _choose(client, asha, internship, live)
    assert again.status_code == 200  # choosing the same project twice changes nothing
    assert (await client.get(_purl(internship, live), headers=auth_headers)).json()["chosen_count"] == 1


async def test_a_student_holds_one_project_and_can_switch_until_they_hand_something_in(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    a = await _project(client, auth_headers, internship, title="A")
    b = await _project(client, auth_headers, internship, title="B")
    await _choose(client, asha, internship, a)
    assert (await _choose(client, asha, internship, b)).status_code == 200  # switched
    assert (await client.get(_purl(internship, a), headers=auth_headers)).json()["chosen_count"] == 0
    assert (await client.get(_purl(internship, b), headers=auth_headers)).json()["chosen_count"] == 1
    assert (await _submit(client, asha, internship, b)).status_code == 200
    locked = await _choose(client, asha, internship, a)
    assert locked.status_code in (400, 422) and "already handed in" in locked.text
    drop = await client.delete(f"{_MINE}/{internship['id']}/projects/choice", headers=asha)
    assert drop.status_code in (400, 422)
    listed = {p["title"]: p for p in (await client.get(f"{_MINE}/{internship['id']}/projects", headers=asha)).json()}
    assert listed["A"]["can_choose"] is False and listed["B"]["chosen_by_me"] is True


async def test_a_student_can_drop_a_project_before_handing_anything_in(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    p = await _project(client, auth_headers, internship)
    await _choose(client, asha, internship, p)
    assert (await client.delete(f"{_MINE}/{internship['id']}/projects/choice", headers=asha)).status_code == 200
    assert (await client.get(_purl(internship, p), headers=auth_headers)).json()["chosen_count"] == 0
    assert (await client.delete(f"{_MINE}/{internship['id']}/projects/choice", headers=asha)).status_code == 200  # nothing to drop is fine


async def test_a_project_can_only_be_chosen_up_to_its_capacity(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    p = await _project(client, auth_headers, internship, capacity=1)
    assert (await _choose(client, asha, internship, p)).status_code == 200
    full = await _choose(client, meera, internship, p)
    assert full.status_code in (400, 422) and "full" in full.text
    seen = (await client.get(f"{_MINE}/{internship['id']}/projects", headers=meera)).json()[0]
    assert seen["spots_left"] == 0 and seen["can_choose"] is False


async def test_the_capacity_cannot_go_below_the_students_already_on_the_project(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    p = await _project(client, auth_headers, internship)
    await _choose(client, people["asha@example.com"][1], internship, p)
    await _choose(client, people["meera@example.com"][1], internship, p)
    refused = await client.patch(_purl(internship, p), json={"capacity": 1}, headers=auth_headers)
    assert refused.status_code == 409
    assert (await client.patch(_purl(internship, p), json={"capacity": 2}, headers=auth_headers)).status_code == 200


# ------------------------------------------------------------ submitting


async def test_work_can_only_be_handed_in_for_the_chosen_project(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    p = await _project(client, auth_headers, internship)
    refused = await _submit(client, asha, internship, p)
    assert refused.status_code in (400, 422) and "Choose this project" in refused.text


async def test_a_file_submission_is_stored_replaced_and_limited(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    p = await _project(client, auth_headers, internship, max_files=2)
    await _choose(client, asha, internship, p)
    r = await _submit(client, asha, internship, p, files=(("a.zip", b"1"), ("b.zip", b"2")), note="first")
    assert r.status_code == 200, r.text
    sub = r.json()["submission"]
    assert sub["method"] == "file" and [f["filename"] for f in sub["files"]] == ["a.zip", "b.zip"] and len(storage.objects) == 2
    second = await _submit(client, asha, internship, p, files=(("c.zip", b"3"),))
    assert [f["filename"] for f in second.json()["submission"]["files"]] == ["c.zip"] and len(storage.objects) == 1
    too_many = await _submit(client, asha, internship, p, files=(("1", b"1"), ("2", b"2"), ("3", b"3")))
    assert too_many.status_code in (400, 422) and "at most 2" in too_many.text
    none = await _submit(client, people["meera@example.com"][1], internship, p, files=())
    assert none.status_code in (400, 422)


async def test_a_way_of_submitting_the_project_does_not_allow_is_refused(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    p = await _project(client, auth_headers, internship)  # files only
    await _choose(client, asha, internship, p)
    for method, extra in (("repository", {"repository_url": "https://github.com/a/b"}), ("email", {"note": "sent"})):
        r = await _submit(client, asha, internship, p, method=method, files=(), **extra)
        assert r.status_code in (400, 422) and "does not accept" in r.text


async def test_a_repository_link_must_be_a_real_web_address(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    p = await _project(client, auth_headers, internship, allow_file=False, allow_repository=True)
    await _choose(client, asha, internship, p)
    for bad in ("", "github.com/a/b", "javascript:alert(1)", "ftp://x.com/a", "https://exa mple.com"):
        r = await _submit(client, asha, internship, p, method="repository", files=(), repository_url=bad)
        assert r.status_code in (400, 422), bad
    ok = await _submit(client, asha, internship, p, method="repository", files=(), repository_url="https://github.com/asha/scanner", note="main branch")
    assert ok.status_code == 200 and ok.json()["submission"]["repository_url"] == "https://github.com/asha/scanner"


async def test_an_emailed_submission_is_confirmed_by_staff_and_reset_when_changed(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    asha_sel = people["asha@example.com"][0]
    p = await _project(client, auth_headers, internship, allow_email=True, submission_email="Projects@Pentrix.in")
    assert p["submission_email"] == "projects@pentrix.in"
    await _choose(client, asha, internship, p)
    assert (await _submit(client, asha, internship, p, method="email", files=())).status_code in (400, 422)  # needs a note
    sent = await _submit(client, asha, internship, p, method="email", files=(), note="Sent from asha@example.com at 10:00")
    assert sent.status_code == 200 and sent.json()["submission"]["received_at"] is None
    url = _purl(internship, p, f"/submissions/{asha_sel}/received")
    got = await client.put(url, json={"received": True}, headers=auth_headers)
    assert got.status_code == 200 and got.json()["received_at"]
    mine = (await client.get(f"{_MINE}/{internship['id']}/projects", headers=asha)).json()[0]
    assert mine["submission"]["received_at"]
    undone = await client.put(url, json={"received": False}, headers=auth_headers)
    assert undone.json()["received_at"] is None
    await client.put(url, json={"received": True}, headers=auth_headers)
    again = await _submit(client, asha, internship, p, method="email", files=(), note="Resent")
    assert again.json()["submission"]["received_at"] is None  # a changed submission needs confirming again
    # confirmation applies to emailed work only, and only to a real submission
    meera_sel = people["meera@example.com"][0]
    assert (await client.put(_purl(internship, p, f"/submissions/{meera_sel}/received"), json={"received": True}, headers=auth_headers)).status_code == 404


async def test_switching_method_removes_the_old_files(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    p = await _project(client, auth_headers, internship, allow_repository=True)
    await _choose(client, asha, internship, p)
    await _submit(client, asha, internship, p)
    assert len(storage.objects) == 1
    r = await _submit(client, asha, internship, p, method="repository", files=(), repository_url="https://github.com/a/b")
    assert r.status_code == 200 and r.json()["submission"]["files"] == [] and storage.objects == {}


async def test_deadlines_and_status_decide_whether_work_is_accepted(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    strict = await _project(client, auth_headers, internship, title="Strict", deadline_at=past)
    await _choose(client, asha, internship, strict)
    refused = await _submit(client, asha, internship, strict)
    assert refused.status_code in (400, 422) and "deadline" in refused.text.lower()
    assert (await client.get(f"{_MINE}/{internship['id']}/projects", headers=asha)).json()[0]["can_submit"] is False
    lenient = await _project(client, auth_headers, internship, title="Lenient", deadline_at=past, allow_late=True)
    await _choose(client, meera, internship, lenient)
    late = await _submit(client, meera, internship, lenient)
    assert late.status_code == 200 and late.json()["submission"]["is_late"] is True
    closed = await _project(client, auth_headers, internship, title="Closed")
    await client.patch(_purl(internship, closed), json={"status": "closed"}, headers=auth_headers)
    assert (await _choose(client, asha, internship, closed)).status_code in (400, 422)


# ------------------------------------------------------------ staff: who chose what


async def test_staff_see_every_enrolled_students_choice_and_submission(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    a = await _project(client, auth_headers, internship, title="A")
    b = await _project(client, auth_headers, internship, title="B")
    await _choose(client, asha, internship, a)
    await _choose(client, meera, internship, b)
    await _submit(client, asha, internship, a, note="done")
    rows = {r["student_email"]: r for r in (await client.get(f"{_INTERN}/{internship['id']}/project-selections", headers=auth_headers)).json()}
    assert set(rows) == {"asha@example.com", "meera@example.com"}  # ravi has no LMS access
    assert rows["asha@example.com"]["project_title"] == "A" and rows["asha@example.com"]["submitted"] is True and rows["asha@example.com"]["method"] == "file"
    assert len(rows["asha@example.com"]["files"]) == 1 and rows["asha@example.com"]["note"] == "done"
    assert rows["meera@example.com"]["project_title"] == "B" and rows["meera@example.com"]["submitted"] is False
    only_a = (await client.get(f"{_INTERN}/{internship['id']}/project-selections?project_id={a['id']}", headers=auth_headers)).json()
    assert [r["student_email"] for r in only_a] == ["asha@example.com"]
    listing = {p["title"]: p for p in (await client.get(f"{_INTERN}/{internship['id']}/projects", headers=auth_headers)).json()}
    assert (listing["A"]["chosen_count"], listing["A"]["submitted_count"]) == (1, 1) and (listing["B"]["chosen_count"], listing["B"]["submitted_count"]) == (1, 0)


async def test_a_student_with_no_choice_shows_with_no_project(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    rows = (await client.get(f"{_INTERN}/{internship['id']}/project-selections", headers=auth_headers)).json()
    assert len(rows) == 2 and all(r["project_id"] is None and r["submitted"] is False for r in rows)


async def test_deleting_a_project_removes_choices_submissions_and_every_file(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    p = await _project(client, auth_headers, internship)
    await client.post(_purl(internship, p, "/files"), files={"file": ("spec.pdf", b"%PDF", "application/pdf")}, headers=auth_headers)
    await client.post(_purl(internship, p, "/files?kind=template"), files={"file": ("t.docx", b"t", "application/octet-stream")}, headers=auth_headers)
    for email in ("asha@example.com", "meera@example.com"):
        await _choose(client, people[email][1], internship, p)
        await _submit(client, people[email][1], internship, p)
    assert len(storage.objects) == 4
    assert (await client.delete(_purl(internship, p), headers=auth_headers)).status_code == 200
    assert storage.objects == {} and (await db_session.execute(select(InternshipFile))).scalars().all() == []
    rows = (await client.get(f"{_INTERN}/{internship['id']}/project-selections", headers=auth_headers)).json()
    assert all(r["project_id"] is None for r in rows)
    # the students are free to choose again
    again = await _project(client, auth_headers, internship, title="New")
    assert (await _choose(client, people["asha@example.com"][1], internship, again)).status_code == 200


# ------------------------------------------------------------ access


async def test_students_outside_the_internship_and_staff_without_permission_are_refused(client, auth_headers, staff_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization, enrolled=("asha@example.com",))
    p = await _project(client, auth_headers, internship)
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    asha = people["asha@example.com"][1]
    assert (await client.get(f"{_MINE}/{other['id']}/projects", headers=asha)).status_code == 404
    assert (await client.get(f"{_INTERN}/{internship['id']}/projects", headers=staff_headers)).status_code == 403
    assert (await client.post(f"{_INTERN}/{internship['id']}/projects", json={"title": "x"}, headers=staff_headers)).status_code == 403
    assert (await client.get(f"{_INTERN}/{internship['id']}/project-selections", headers=staff_headers)).status_code == 403
    assert (await client.delete(_purl(internship, p), headers=staff_headers)).status_code == 403


async def test_a_student_cannot_see_anothers_submission(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    p = await _project(client, auth_headers, internship)
    await _choose(client, asha, internship, p)
    await _submit(client, asha, internship, p, note="mine")
    seen = (await client.get(f"{_MINE}/{internship['id']}/projects", headers=meera)).json()[0]
    assert seen["submission"] is None and seen["chosen_by_me"] is False and seen["can_submit"] is False
    assert (await _submit(client, meera, internship, p)).status_code in (400, 422)
