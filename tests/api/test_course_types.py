"""
Regular and internship courses: the type is stored and returned, an internship course has no price of its own, the fee shown for one comes
only from the linked internship's saved onboarding settings and only to people who may see finance, linking and unlinking follow the
rules, and existing courses stay exactly what they were. Synthetic data only.
"""

import uuid

import pytest
from sqlalchemy import select

from modules.courses.models import Course, CourseType
from modules.organizations.repository import OrganizationRepository
from tests.api.test_email_studio import user_with
from tests.api.test_internship_onboarding import BASE, configure, world

pytestmark = pytest.mark.api

COURSES = "/api/v1/courses"


def body(title="DevSecOps Level-1", **over):
    return {"title": title, "slug": f"c-{uuid.uuid4().hex[:8]}", "level": "beginner", **over}


async def make(client, headers, **over):
    r = await client.post(f"{COURSES}/", json=body(**over), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def ready(client, headers, db, course_id):
    from modules.courses.chapters.repository import ChapterRepository

    await ChapterRepository(db).create(course_id=uuid.UUID(course_id), title="One", order_index=1)
    await db.flush()
    assert (await client.post(f"{COURSES}/{course_id}/publish", headers=headers)).status_code == 200


async def link(client, headers, internship, course_id, **extra):
    return await client.patch(f"{BASE}/{internship.id}", json={"lms_course_id": course_id, **extra}, headers=headers)


# ------------------------------------------------------------ creating


async def test_a_regular_course_is_created_and_priced_as_before(client, auth_headers):
    c = await make(client, auth_headers, price=4999, short_description="Intro")
    assert (c["course_type"], c["price"], c["show_internship_fee"], c["linked_internships"]) == ("regular", 4999.0, False, [])
    assert (await client.patch(f"{COURSES}/{c['id']}", json={"price": 5500}, headers=auth_headers)).json()["price"] == 5500.0


async def test_an_internship_course_has_no_price_and_hides_the_fee_unless_asked(client, auth_headers):
    hidden = await make(client, auth_headers, course_type="internship")
    assert (hidden["course_type"], hidden["price"], hidden["show_internship_fee"]) == ("internship", 0.0, False)  # Hide Fee is the default
    shown = await make(client, auth_headers, course_type="internship", show_internship_fee=True)
    assert shown["show_internship_fee"] is True
    priced = await client.post(f"{COURSES}/", json=body(course_type="internship", price=999), headers=auth_headers)
    assert priced.status_code == 422 and "no price of its own" in priced.text
    regular_fee = await client.post(f"{COURSES}/", json=body(show_internship_fee=True), headers=auth_headers)
    assert regular_fee.status_code == 422  # fee visibility is an internship-course setting
    assert (await client.patch(f"{COURSES}/{shown['id']}", json={"show_internship_fee": False}, headers=auth_headers)).json()["show_internship_fee"] is False


async def test_existing_courses_are_regular_and_the_list_filters_by_type(client, auth_headers, db_session, organization):
    old = Course(organization_id=organization.id, title="Created before types", slug=f"old-{uuid.uuid4().hex[:6]}", price=1200)
    db_session.add(old)
    await db_session.flush()
    await db_session.refresh(old)
    assert (old.course_type, old.show_internship_fee) == (CourseType.REGULAR, False)
    intern = await make(client, auth_headers, course_type="internship", title="An internship course")
    everything = (await client.get(f"{COURSES}/", headers=auth_headers)).json()["items"]
    assert {c["title"] for c in everything} >= {"Created before types", "An internship course"}
    only = (await client.get(f"{COURSES}/?course_type=internship", headers=auth_headers)).json()
    assert [c["id"] for c in only["items"]] == [intern["id"]] and only["total"] == 1
    assert "Created before types" in {c["title"] for c in (await client.get(f"{COURSES}/?course_type=regular", headers=auth_headers)).json()["items"]}


async def test_a_course_of_another_organization_is_invisible(client, auth_headers, db_session):
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    foreign = Course(organization_id=other.id, title="Foreign", slug=f"f-{uuid.uuid4().hex[:6]}", course_type=CourseType.INTERNSHIP)
    db_session.add(foreign)
    await db_session.flush()
    assert (await client.get(f"{COURSES}/{foreign.id}", headers=auth_headers)).status_code == 404
    assert "Foreign" not in {c["title"] for c in (await client.get(f"{COURSES}/?course_type=internship", headers=auth_headers)).json()["items"]}


# ------------------------------------------------------------ linking


async def test_only_an_internship_course_can_be_linked_and_the_link_shows_on_the_course(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    regular = await make(client, auth_headers)
    refused = await link(client, auth_headers, internship, regular["id"])
    assert refused.status_code == 422 and "regular course" in refused.json()["error"]["message"]
    course = await make(client, auth_headers, course_type="internship")
    assert (await link(client, auth_headers, internship, course["id"])).status_code == 200
    shown = (await client.get(f"{COURSES}/{course['id']}", headers=auth_headers)).json()
    assert [(i["id"], i["title"], i["fee"]) for i in shown["linked_internships"]] == [(str(internship.id), internship.title, None)]
    listed = [c for c in (await client.get(f"{COURSES}/", headers=auth_headers)).json()["items"] if c["id"] == course["id"]][0]
    assert listed["linked_internships"][0]["title"] == internship.title
    unlinked = await make(client, auth_headers, course_type="internship", title="Unlinked")
    assert unlinked["linked_internships"] == []


async def test_one_course_serves_several_internships_and_cannot_change_type_or_vanish_while_linked(client, auth_headers, db_session, organization):
    first, _ = await world(db_session, organization)
    second, _ = await world(db_session, organization)
    course = await make(client, auth_headers, course_type="internship")
    for internship in (first, second):
        assert (await link(client, auth_headers, internship, course["id"])).status_code == 200
    assert len((await client.get(f"{COURSES}/{course['id']}", headers=auth_headers)).json()["linked_internships"]) == 2
    back = await client.patch(f"{COURSES}/{course['id']}", json={"course_type": "regular"}, headers=auth_headers)
    assert back.status_code == 409 and "Unlink" in back.json()["error"]["message"]
    gone = await client.delete(f"{COURSES}/{course['id']}", headers=auth_headers)
    assert gone.status_code == 409 and "linked" in gone.json()["error"]["message"]
    free = await make(client, auth_headers, course_type="internship", title="Never linked")
    assert (await client.delete(f"{COURSES}/{free['id']}", headers=auth_headers)).status_code == 200


async def test_a_regular_course_becomes_an_internship_course_only_without_a_price_and_an_unused_one_can_go_back(client, auth_headers):
    c = await make(client, auth_headers, price=3000)
    priced = await client.patch(f"{COURSES}/{c['id']}", json={"course_type": "internship"}, headers=auth_headers)
    assert priced.status_code == 422 and "price" in priced.json()["error"]["message"]
    converted = await client.patch(f"{COURSES}/{c['id']}", json={"course_type": "internship", "price": 0, "show_internship_fee": True}, headers=auth_headers)
    assert converted.status_code == 200 and (converted.json()["course_type"], converted.json()["price"]) == ("internship", 0.0)
    back = await client.patch(f"{COURSES}/{c['id']}", json={"course_type": "regular", "price": 800}, headers=auth_headers)
    assert (back.json()["course_type"], back.json()["show_internship_fee"], back.json()["price"]) == ("regular", False, 800.0)


async def test_a_regular_course_linked_before_types_existed_keeps_working(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    legacy = Course(organization_id=organization.id, title="Legacy linked", slug=f"l-{uuid.uuid4().hex[:6]}", is_published=True)
    db_session.add(legacy)
    await db_session.flush()
    internship.lms_course_id = legacy.id
    await db_session.flush()
    options = (await client.get(f"{BASE}/{internship.id}/lms/courses", headers=auth_headers)).json()
    assert [(o["title"], o["course_type"], o["is_current"]) for o in options] == [("Legacy linked", "regular", True)]
    assert (await link(client, auth_headers, internship, str(legacy.id))).status_code == 200  # choosing the same one is a no-op
    assert (await client.get(f"{BASE}/{internship.id}", headers=auth_headers)).json()["lms_course_title"] == "Legacy linked"


async def test_the_picker_offers_internship_courses_with_readiness_and_who_else_uses_them(client, auth_headers, db_session, organization):
    mine, _ = await world(db_session, organization)
    other, _ = await world(db_session, organization)
    draft = await make(client, auth_headers, course_type="internship", title="Draft one")
    done = await make(client, auth_headers, course_type="internship", title="Finished one")
    await ready(client, auth_headers, db_session, done["id"])
    await make(client, auth_headers, title="A regular course")  # not offered
    assert (await link(client, auth_headers, other, done["id"])).status_code == 200
    options = {o["title"]: o for o in (await client.get(f"{BASE}/{mine.id}/lms/courses", headers=auth_headers)).json()}
    assert set(options) == {"Draft one", "Finished one"}
    assert (options["Draft one"]["ready"], options["Draft one"]["problem"]) == (False, "Not published yet.")
    assert (options["Finished one"]["ready"], options["Finished one"]["also_used_by"]) == (True, [other.title])
    assert draft["id"] in {str(o["id"]) for o in options.values()}


# ------------------------------------------------------------ the fee, from the internship's own settings, for the right people


async def test_the_fee_is_the_internships_own_and_shown_only_when_asked_and_to_finance(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    shown = await make(client, auth_headers, course_type="internship", show_internship_fee=True, title="Shows")
    hidden = await make(client, auth_headers, course_type="internship", title="Hides")
    assert (await link(client, auth_headers, internship, shown["id"])).status_code == 200

    def fee(view):
        return view["linked_internships"][0]["fee"]

    # no saved onboarding settings yet: a default amount is not a fee, so nothing is shown
    assert fee((await client.get(f"{COURSES}/{shown['id']}", headers=auth_headers)).json()) is None
    await configure(client, auth_headers, internship, fees={"base_amount": "5000", "tax_mode": "exclusive", "tax_rate_percent": "18"})
    got = fee((await client.get(f"{COURSES}/{shown['id']}", headers=auth_headers)).json())
    assert (got["total"], got["tax"], got["currency"], got["tax_mode"]) == ("5900.00", "900.00", "INR", "exclusive")
    # the amount follows the internship's settings, never a stored copy
    await configure(client, auth_headers, internship, fees={"base_amount": "6000", "tax_mode": "exclusive", "tax_rate_percent": "18"})
    assert fee((await client.get(f"{COURSES}/{shown['id']}", headers=auth_headers)).json())["total"] == "7080.00"
    # a course set to Hide Fee shows no fee even when linked to the same internship
    assert (await client.patch(f"{COURSES}/{shown['id']}", json={"show_internship_fee": False}, headers=auth_headers)).status_code == 200
    assert fee((await client.get(f"{COURSES}/{shown['id']}", headers=auth_headers)).json()) is None
    assert (await client.patch(f"{COURSES}/{shown['id']}", json={"show_internship_fee": True}, headers=auth_headers)).status_code == 200

    reader = await user_with(db_session, organization, ["courses.view", "our_internships.view"])
    assert fee((await client.get(f"{COURSES}/{shown['id']}", headers=reader)).json()) is None  # may see the link, not the money
    finance = await user_with(db_session, organization, ["courses.view", "our_internships.view", "our_internships.finance.view"])
    assert fee((await client.get(f"{COURSES}/{shown['id']}", headers=finance)).json())["total"] == "7080.00"
    plain = await user_with(db_session, organization, ["courses.view"])
    assert (await client.get(f"{COURSES}/{shown['id']}", headers=plain)).json()["linked_internships"] == []  # nor which internships
    assert hidden["linked_internships"] == []
