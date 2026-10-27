"""
Project reviews, final marks and awards.

What must hold: reviews are marked on the project's factors within their limits, a submission can have several, the final
result defaults to their average and stays hidden from the student until published, publishing locks the submission and the
reviews, awards go only to enrolled students, and a student sees only their own results and awards.
"""

import uuid

import pytest

from modules.internship_learning import files as files_module
from tests.api.test_internship_learning import FakeStorage, _world
from tests.api.test_internship_projects import _choose, _murl, _project, _purl, _submit

pytestmark = pytest.mark.api

_INTERN = "/api/v1/our-internships"
_MINE = "/api/v1/my-internships"
_FACTORS = [{"id": "f1", "name": "Correctness", "max_marks": 40}, {"id": "f2", "name": "Code quality", "max_marks": 30}, {"id": "f3", "name": "Report", "max_marks": 30}]


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(files_module, "get_storage_client", lambda: fake)
    return fake


async def _setup(client, headers, db_session, organization, **project_over):
    """A published project that Asha has chosen and handed in."""
    internship, people = await _world(client, headers, db_session, organization)
    project = await _project(client, headers, internship, **project_over)
    asha = people["asha@example.com"][1]
    await _choose(client, asha, internship, project)
    assert (await _submit(client, asha, internship, project)).status_code == 200
    return internship, people, project, people["asha@example.com"][0]


def _rurl(internship, project, tail=""):
    return f"{_INTERN}/{internship['id']}/projects/{project['id']}{tail}"


async def _review(client, headers, internship, project, selection, label="Final review", **body):
    return await client.post(_rurl(internship, project, f"/submissions/{selection}/reviews"), json={"label": label, **body}, headers=headers)


async def _my_project(client, student, internship):
    return (await client.get(f"{_MINE}/{internship['id']}/projects", headers=student)).json()[0]


# ------------------------------------------------------------ factors


async def test_review_factors_set_the_total_and_must_be_consistent(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    p = await _project(client, auth_headers, internship, review_factors=_FACTORS, max_marks=5)
    assert p["max_marks"] == 100 and [f["name"] for f in p["review_factors"]] == ["Correctness", "Code quality", "Report"]
    dup = await client.post(f"{_INTERN}/{internship['id']}/projects", json={"title": "x", "review_factors": [{"id": "a", "name": "A", "max_marks": 5}, {"id": "a", "name": "B", "max_marks": 5}]}, headers=auth_headers)
    assert dup.status_code in (400, 422)
    plain = await _project(client, auth_headers, internship, title="Plain", max_marks=50)
    assert plain["max_marks"] == 50 and plain["review_factors"] == []


async def test_factors_cannot_change_once_a_review_exists(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, review_factors=_FACTORS)
    assert (await _review(client, auth_headers, internship, project, sel, factor_scores={"f1": 30, "f2": 20, "f3": 25})).status_code == 201
    refused = await client.patch(_purl(internship, project), json={"review_factors": [{"id": "f1", "name": "Only", "max_marks": 10}]}, headers=auth_headers)
    assert refused.status_code == 409
    assert (await client.patch(_purl(internship, project), json={"title": "Renamed"}, headers=auth_headers)).status_code == 200  # other edits are fine


# ------------------------------------------------------------ reviews


async def test_a_review_is_marked_on_the_factors_and_a_submission_can_have_several(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, review_factors=_FACTORS)
    first = await _review(client, auth_headers, internship, project, sel, label="Mid-way review", factor_scores={"f1": 30, "f2": 20, "f3": 10}, feedback="Good start")
    assert first.status_code == 201, first.text
    second = await _review(client, auth_headers, internship, project, sel, label="Final review", factor_scores={"f1": 40, "f2": 30, "f3": 30})
    row = second.json()
    # (reviews are listed in the order they were written; within one test transaction they share a timestamp, so compare unordered)
    by_label = {r["label"]: r for r in row["reviews"]}
    assert set(by_label) == {"Mid-way review", "Final review"}
    assert (by_label["Mid-way review"]["total"], by_label["Final review"]["total"]) == (60, 100)
    assert row["average"] == 80 and row["max_marks"] == 100
    assert by_label["Mid-way review"]["feedback"] == "Good start" and by_label["Mid-way review"]["reviewer_name"]
    listed = (await client.get(_rurl(internship, project, "/reviews"), headers=auth_headers)).json()
    assert [r["student_email"] for r in listed] == ["asha@example.com"]  # only students who handed in


async def test_marks_must_stay_within_each_factors_limit(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, review_factors=_FACTORS)
    assert (await _review(client, auth_headers, internship, project, sel, factor_scores={"f1": 41})).status_code in (400, 422)
    assert (await _review(client, auth_headers, internship, project, sel, factor_scores={"f1": -1})).status_code in (400, 422)
    assert (await _review(client, auth_headers, internship, project, sel, factor_scores={"zz": 1})).status_code in (400, 422)
    partial = await _review(client, auth_headers, internship, project, sel, factor_scores={"f1": 25})
    assert partial.status_code == 201 and partial.json()["reviews"][0]["total"] == 25  # blank factors count as zero
    assert (await _review(client, auth_headers, internship, project, sel, label="  ", factor_scores={"f1": 1})).status_code in (400, 422)


async def test_a_project_without_factors_takes_one_score_out_of_its_total(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    assert (await _review(client, auth_headers, internship, project, sel)).status_code in (400, 422)
    assert (await _review(client, auth_headers, internship, project, sel, score=51)).status_code in (400, 422)
    ok = await _review(client, auth_headers, internship, project, sel, score=42.5)
    assert ok.status_code == 201 and ok.json()["reviews"][0]["total"] == 42.5 and ok.json()["reviews"][0]["factor_scores"] is None


async def test_only_a_submitted_project_can_be_reviewed(client, auth_headers, db_session, organization):
    internship, people, project, _ = await _setup(client, auth_headers, db_session, organization, max_marks=10)
    meera = people["meera@example.com"][0]
    assert (await _review(client, auth_headers, internship, project, meera, score=5)).status_code == 404


async def test_a_review_can_be_corrected_or_removed(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, review_factors=_FACTORS)
    row = (await _review(client, auth_headers, internship, project, sel, factor_scores={"f1": 10})).json()
    rid = row["reviews"][0]["id"]
    fixed = await client.put(_rurl(internship, project, f"/reviews/{rid}"), json={"label": "Corrected", "factor_scores": {"f1": 35, "f2": 25, "f3": 20}}, headers=auth_headers)
    assert fixed.status_code == 200 and fixed.json()["reviews"][0]["total"] == 80 and fixed.json()["reviews"][0]["label"] == "Corrected"
    gone = await client.delete(_rurl(internship, project, f"/reviews/{rid}"), headers=auth_headers)
    assert gone.status_code == 200 and gone.json()["reviews"] == [] and gone.json()["average"] is None
    assert (await client.delete(_rurl(internship, project, f"/reviews/{uuid.uuid4()}"), headers=auth_headers)).status_code == 404


# ------------------------------------------------------------ final marks


async def test_the_final_result_defaults_to_the_average_and_is_hidden_until_published(client, auth_headers, db_session, organization):
    internship, people, project, sel = await _setup(client, auth_headers, db_session, organization, review_factors=_FACTORS)
    asha = people["asha@example.com"][1]
    await _review(client, auth_headers, internship, project, sel, label="One", factor_scores={"f1": 30, "f2": 20, "f3": 10}, feedback="Private to staff? no")
    await _review(client, auth_headers, internship, project, sel, label="Two", factor_scores={"f1": 40, "f2": 30, "f3": 30})
    assert (await _my_project(client, asha, internship))["submission"]["result"] is None  # reviews alone reveal nothing
    done = await client.put(_rurl(internship, project, f"/submissions/{sel}/final"), json={"feedback": "Well done"}, headers=auth_headers)
    assert done.status_code == 200 and done.json()["final_marks"] == 80 and done.json()["final_published_at"]
    result = (await _my_project(client, asha, internship))["submission"]["result"]
    assert result["final_marks"] == 80 and result["max_marks"] == 100 and result["feedback"] == "Well done"
    assert [r["label"] for r in result["reviews"]] == ["One", "Two"] and result["reviews"][0]["factor_scores"] == {"f1": 30, "f2": 20, "f3": 10}


async def test_staff_can_override_the_final_marks_within_the_total(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    url = _rurl(internship, project, f"/submissions/{sel}/final")
    assert (await client.put(url, json={}, headers=auth_headers)).status_code in (400, 422)  # no reviews, no marks
    assert (await client.put(url, json={"final_marks": 51}, headers=auth_headers)).status_code in (400, 422)
    ok = await client.put(url, json={"final_marks": 47.5}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["final_marks"] == 47.5
    again = await client.put(url, json={"final_marks": 48}, headers=auth_headers)  # marks can be corrected
    assert again.json()["final_marks"] == 48


async def test_publishing_locks_the_submission_and_the_reviews_until_it_is_withdrawn(client, auth_headers, db_session, organization):
    internship, people, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    asha = people["asha@example.com"][1]
    row = (await _review(client, auth_headers, internship, project, sel, score=40)).json()
    rid = row["reviews"][0]["id"]
    await client.put(_rurl(internship, project, f"/submissions/{sel}/final"), json={}, headers=auth_headers)
    locked = await _submit(client, asha, internship, project)
    assert locked.status_code in (400, 422) and "published" in locked.text
    assert (await _my_project(client, asha, internship))["can_submit"] is False
    assert (await _review(client, auth_headers, internship, project, sel, label="Late", score=10)).status_code == 409
    assert (await client.put(_rurl(internship, project, f"/reviews/{rid}"), json={"label": "x", "score": 1}, headers=auth_headers)).status_code == 409
    assert (await client.delete(_rurl(internship, project, f"/reviews/{rid}"), headers=auth_headers)).status_code == 409
    withdrawn = await client.delete(_rurl(internship, project, f"/submissions/{sel}/final"), headers=auth_headers)
    assert withdrawn.status_code == 200 and withdrawn.json()["final_marks"] is None and withdrawn.json()["final_published_at"] is None
    assert (await _my_project(client, asha, internship))["submission"]["result"] is None
    assert (await _review(client, auth_headers, internship, project, sel, label="Again", score=10)).status_code == 201
    assert (await _submit(client, asha, internship, project)).status_code == 200


async def test_a_student_sees_only_their_own_result(client, auth_headers, db_session, organization):
    internship, people, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    meera = people["meera@example.com"][1]
    await _review(client, auth_headers, internship, project, sel, score=40)
    await client.put(_rurl(internship, project, f"/submissions/{sel}/final"), json={}, headers=auth_headers)
    seen = (await _my_project(client, meera, internship))
    assert seen["submission"] is None and seen["chosen_by_me"] is False


async def test_deleting_a_project_removes_its_reviews(client, auth_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    await _review(client, auth_headers, internship, project, sel, score=40)
    assert (await client.delete(_purl(internship, project), headers=auth_headers)).status_code == 200
    assert (await client.get(_rurl(internship, project, "/reviews"), headers=auth_headers)).status_code == 404


# ------------------------------------------------------------ awards


async def test_awards_are_created_renamed_given_and_taken_back(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    base = f"{_INTERN}/{internship['id']}/awards"
    made = await client.post(base, json={"name": "Best Project", "description": "The strongest project"}, headers=auth_headers)
    assert made.status_code == 201 and made.json()["grants"] == []
    aid = made.json()["id"]
    assert (await client.post(base, json={"name": "best project"}, headers=auth_headers)).status_code == 409  # names are unique
    renamed = await client.patch(f"{base}/{aid}", json={"name": "Best Project 2026"}, headers=auth_headers)
    assert renamed.json()["name"] == "Best Project 2026"
    sel = people["asha@example.com"][0]
    given = await client.put(f"{base}/{aid}/grants", json={"selection_id": sel, "note": "Top marks"}, headers=auth_headers)
    assert given.status_code == 200 and [(g["student_email"], g["note"]) for g in given.json()["grants"]] == [("asha@example.com", "Top marks")]
    again = await client.put(f"{base}/{aid}/grants", json={"selection_id": sel, "note": "Updated"}, headers=auth_headers)
    assert [g["note"] for g in again.json()["grants"]] == ["Updated"]  # one grant per student
    taken = await client.delete(f"{base}/{aid}/grants/{sel}", headers=auth_headers)
    assert taken.status_code == 200 and taken.json()["grants"] == []
    assert (await client.delete(f"{base}/{aid}/grants/{sel}", headers=auth_headers)).status_code == 404


async def test_an_award_can_only_go_to_a_student_with_access_to_this_internship(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    base = f"{_INTERN}/{internship['id']}/awards"
    aid = (await client.post(base, json={"name": "Top Performer"}, headers=auth_headers)).json()["id"]
    ravi = people["ravi@example.com"][0]  # selected but without LMS access
    assert (await client.put(f"{base}/{aid}/grants", json={"selection_id": ravi}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.put(f"{base}/{aid}/grants", json={"selection_id": str(uuid.uuid4())}, headers=auth_headers)).status_code in (400, 422)


async def test_students_see_their_awards_in_the_internship_and_on_their_profile(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    base = f"{_INTERN}/{internship['id']}/awards"
    best = (await client.post(base, json={"name": "Best Project", "description": "Strongest"}, headers=auth_headers)).json()["id"]
    top = (await client.post(base, json={"name": "Top Performer"}, headers=auth_headers)).json()["id"]
    await client.put(f"{base}/{best}/grants", json={"selection_id": people["asha@example.com"][0], "note": "Great scanner"}, headers=auth_headers)
    await client.put(f"{base}/{top}/grants", json={"selection_id": people["meera@example.com"][0]}, headers=auth_headers)
    mine = (await client.get(f"{_MINE}/{internship['id']}/awards", headers=asha)).json()
    assert [(a["name"], a["note"], a["internship_title"]) for a in mine] == [("Best Project", "Great scanner", "Pentrix Cyber Internship")]
    everywhere = (await client.get("/api/v1/my-internship-awards", headers=asha)).json()
    assert [a["name"] for a in everywhere] == ["Best Project"]
    assert [a["name"] for a in (await client.get("/api/v1/my-internship-awards", headers=meera)).json()] == ["Top Performer"]
    assert (await client.delete(f"{base}/{best}", headers=auth_headers)).status_code == 200
    assert (await client.get("/api/v1/my-internship-awards", headers=asha)).json() == []


async def test_a_student_with_access_taken_away_loses_the_awards_from_view(client, auth_headers, db_session, organization):
    from sqlalchemy import select

    from modules.our_internships.models import InternshipSelection, LmsStatus

    internship, people = await _world(client, auth_headers, db_session, organization)
    base = f"{_INTERN}/{internship['id']}/awards"
    aid = (await client.post(base, json={"name": "Best Project"}, headers=auth_headers)).json()["id"]
    sel = people["asha@example.com"][0]
    await client.put(f"{base}/{aid}/grants", json={"selection_id": sel}, headers=auth_headers)
    row = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(sel)))).scalar_one()
    row.lms_status = LmsStatus.REVOKED
    await db_session.flush()
    assert (await client.get(base, headers=auth_headers)).json()[0]["grants"] == []
    assert (await client.get("/api/v1/my-internship-awards", headers=people["asha@example.com"][1])).json() == []


# ------------------------------------------------------------ access


async def test_without_the_permission_nothing_can_be_reviewed_or_awarded(client, auth_headers, staff_headers, db_session, organization):
    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    aid = (await client.post(f"{_INTERN}/{internship['id']}/awards", json={"name": "A"}, headers=auth_headers)).json()["id"]
    assert (await client.get(_rurl(internship, project, "/reviews"), headers=staff_headers)).status_code == 403
    assert (await _review(client, staff_headers, internship, project, sel, score=1)).status_code == 403
    assert (await client.put(_rurl(internship, project, f"/submissions/{sel}/final"), json={"final_marks": 1}, headers=staff_headers)).status_code == 403
    assert (await client.get(f"{_INTERN}/{internship['id']}/awards", headers=staff_headers)).status_code == 403
    assert (await client.delete(f"{_INTERN}/{internship['id']}/awards/{aid}", headers=staff_headers)).status_code == 403
    assert (await client.get("/api/v1/my-internship-awards", headers=staff_headers)).status_code in (400, 422)  # not a student


async def test_one_organization_cannot_reach_anothers_reviews_or_awards(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    internship, _, project, sel = await _setup(client, auth_headers, db_session, organization, max_marks=50)
    aid = (await client.post(f"{_INTERN}/{internship['id']}/awards", json={"name": "A"}, headers=auth_headers)).json()["id"]
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    assert (await client.get(_rurl(internship, project, "/reviews"), headers=outsider)).status_code == 404
    assert (await _review(client, outsider, internship, project, sel, score=1)).status_code == 404
    assert (await client.get(f"{_INTERN}/{internship['id']}/awards", headers=outsider)).status_code == 404
    assert (await client.put(f"{_INTERN}/{internship['id']}/awards/{aid}/grants", json={"selection_id": sel}, headers=outsider)).status_code == 404
