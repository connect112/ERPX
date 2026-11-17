"""
Publishing a course (both types), what unpublishing does to an internship that uses it, and what a student browsing the course catalog
can and cannot learn about internship courses (their links and fees). Synthetic data only.
"""

import uuid

import pytest
from sqlalchemy import select

from modules.courses.chapters.repository import ChapterRepository
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from tests.api.test_course_content_access import student_with_role
from tests.api.test_course_types import COURSES, link, make, ready as publish_ready
from tests.api.test_email_studio import user_with
from tests.api.test_internship_lms_integrity import grant, ready as selection_ready
from tests.api.test_internship_onboarding import configure, world

pytestmark = pytest.mark.api


@pytest.mark.parametrize("course_type", ["regular", "internship"])
async def test_a_course_of_either_type_needs_a_chapter_to_be_published_and_can_be_unpublished_again(client, auth_headers, db_session, course_type):
    course = await make(client, auth_headers, course_type=course_type)
    assert course["is_published"] is False and course["course_type"] == course_type

    refused = await client.post(f"{COURSES}/{course['id']}/publish", headers=auth_headers)
    assert refused.status_code == 422 and "no chapters" in refused.json()["error"]["message"]
    assert (await client.get(f"{COURSES}/{course['id']}", headers=auth_headers)).json()["is_published"] is False

    await ChapterRepository(db_session).create(course_id=uuid.UUID(course["id"]), title="One", order_index=1)
    await db_session.flush()
    published = await client.post(f"{COURSES}/{course['id']}/publish", headers=auth_headers)
    assert published.status_code == 200
    body = published.json()
    assert body["is_published"] is True and body["course_type"] == course_type  # publishing changes nothing else
    assert body["linked_internships"] == [] and "price" in body

    unpublished = await client.post(f"{COURSES}/{course['id']}/unpublish", headers=auth_headers)
    assert unpublished.status_code == 200 and unpublished.json()["is_published"] is False
    listed = (await client.get(f"{COURSES}/?is_published=true", headers=auth_headers)).json()["items"]
    assert course["id"] not in [c["id"] for c in listed]


async def test_publishing_and_unpublishing_need_the_manage_permission(client, auth_headers, db_session, organization, rbac_seeded):
    course = await make(client, auth_headers, course_type="internship")
    await publish_ready(client, auth_headers, db_session, course["id"])
    viewer = await user_with(db_session, organization, ["courses.view"])
    assert (await client.post(f"{COURSES}/{course['id']}/unpublish", headers=viewer)).status_code == 403
    assert (await client.post(f"{COURSES}/{course['id']}/publish", headers=viewer)).status_code == 403
    assert (await client.get(f"{COURSES}/{course['id']}", headers=auth_headers)).json()["is_published"] is True


async def test_unpublishing_a_linked_course_stops_new_grants_and_leaves_enrolled_students_where_they_are(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    course = await make(client, auth_headers, course_type="internship")
    await publish_ready(client, auth_headers, db_session, course["id"])
    assert (await link(client, auth_headers, internship, course["id"])).status_code == 200
    await selection_ready(db_session, internship, s0)
    await selection_ready(db_session, internship, s1)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200

    assert (await client.post(f"{COURSES}/{course['id']}/unpublish", headers=auth_headers)).status_code == 200
    refused = await grant(client, auth_headers, internship, s1)
    assert refused.status_code == 422 and "not published" in refused.json()["error"]["message"]  # nobody new is enrolled in a draft
    rows = (await db_session.execute(select(Enrollment).where(Enrollment.course_id == uuid.UUID(course["id"])))).scalars().all()
    assert [e.status for e in rows] == [EnrollmentStatus.ACTIVE]  # the student already in keeps their enrolment

    assert (await client.post(f"{COURSES}/{course['id']}/publish", headers=auth_headers)).status_code == 200
    assert (await grant(client, auth_headers, internship, s1)).status_code == 200  # and publishing again lets the next grant through


async def test_a_student_browsing_the_catalog_learns_nothing_about_internship_links_or_fees(client, auth_headers, db_session, organization, rbac_seeded):
    internship, _ = await world(db_session, organization)
    course = await make(client, auth_headers, course_type="internship", show_internship_fee=True, title="Internship Course")
    await publish_ready(client, auth_headers, db_session, course["id"])
    assert (await link(client, auth_headers, internship, course["id"])).status_code == 200
    await configure(client, auth_headers, internship, fees={"base_amount": "5000", "tax_mode": "exclusive", "tax_rate_percent": "18"})
    staff = (await client.get(f"{COURSES}/{course['id']}", headers=auth_headers)).json()
    assert staff["linked_internships"][0]["fee"]["total"] == "5900.00"  # staff with finance access see it (the control)

    _, headers = await student_with_role(client, db_session, organization)
    detail = await client.get(f"{COURSES}/{course['id']}", headers=headers)
    listing = await client.get(f"{COURSES}/", headers=headers)
    for response in (detail, listing):
        assert response.status_code == 200
        assert "5900" not in response.text and "tax" not in response.text and internship.title not in response.text
    assert detail.json()["linked_internships"] == []
    assert all(item["linked_internships"] == [] for item in listing.json()["items"])
    # browsing the catalog shows what a course is, never what is in it: the content stays behind an enrolment
    assert (await client.get(f"{COURSES}/{course['id']}/chapters", headers=headers)).status_code == 403
