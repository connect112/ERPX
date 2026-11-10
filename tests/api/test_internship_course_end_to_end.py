"""
The whole internship-course workflow, as an administrator and a student go through it, on synthetic data and a fake mailbox (no real
message is ever sent): create DevSecOps Level-1 as an internship course with the fee hidden, link it to an existing internship, see the
course name in the offer letter preview, the generated PDFs and the Email Studio preview while the internship name stays its own, release
letters, leave what was generated or released before untouched, onboard a student, give and withdraw LMS access, and check that regular
courses, payments, receipts and invoices are not affected.
"""

import io
import json
import uuid
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select

from modules.courses.chapters.repository import ChapterRepository
from modules.institutions.models import InstitutionStudent
from modules.internship_onboarding.models import FinancialDocument, PaymentTransaction
from modules.our_internships import letter_tasks
from modules.our_internships.models import InternshipSelection, OurInternship
from tests.api.test_internship_lms_integrity import grant, ready, revoke
from tests.api.test_internship_offers import _setup
from tests.api.test_internship_onboarding import BASE, PUBLIC, configure as configure_onboarding, link as onboarding_link, storage, tok  # noqa: F401
from tests.api.test_internship_onboarding import world as onboarding_world
from tests.api.test_internship_student_course_views import student_login
from tests.api.test_offer_letters import approved, by_name, generate, students, text_of, url, world  # noqa: F401  (the fixture)
from tests.api.test_receipt_designer import TAX, paid_by_bank

pytestmark = pytest.mark.api

COURSE = "DevSecOps Level-1"
ABOUT = {"description": "You will study {{lms_course_name}} during {{internship_name}}."}
EMAIL = {"subject": "Your offer: {{internship_name}}", "body": "Dear {{student_name}},\n\nProgramme: {{internship_name}}. Learning course: {{lms_course_name}}.\n\nRegards"}


async def pdf_of(client, headers, internship, letter_id) -> bytes:
    return (await client.get(url(internship, f"/letters/{letter_id}/pdf"), headers=headers)).content


async def release_and_send(client, headers, internship, letter_id):
    assert (await client.post(url(internship, "/approve"), json={"letter_ids": [letter_id]}, headers=headers)).status_code == 200
    out = (await client.post(url(internship, "/release"), json={"letter_ids": [letter_id]}, headers=headers)).json()
    assert out["queued"] == 1, out
    await letter_tasks._send_letter(uuid.UUID(letter_id))


async def test_creating_linking_and_using_an_internship_course_end_to_end(client, auth_headers, db_session, organization, world, rbac_seeded):  # noqa: F811
    internship, ids = await _setup(client, auth_headers)
    internship_id = uuid.UUID(internship["id"])
    orm = await db_session.get(OurInternship, internship_id)

    # ---- before any course: a letter is generated and released with the original wording (7: this must stay exactly as it is)
    await approved(client, auth_headers, internship)
    await generate(client, auth_headers, internship, world)
    rows = by_name(await students(client, auth_headers, internship))
    asha = rows["Asha Rao"]["letter"]
    await release_and_send(client, auth_headers, internship, asha["id"])
    released_pdf = await pdf_of(client, auth_headers, internship, asha["id"])
    released_row = (await students(client, auth_headers, internship))["students"]
    released_before = {s["name"]: s["letter"] for s in released_row}["Asha Rao"]
    assert COURSE not in text_of(released_pdf)
    assert len(world.mail.sent) == 1

    # ---- 1-2: create DevSecOps Level-1 as an internship course, Hide Fee (the default), and look for any price in course screens
    made = await client.post("/api/v1/courses/", json={"title": COURSE, "slug": "devsecops-level-1", "level": "beginner", "course_type": "internship", "duration_hours": 40, "short_description": "Hands-on DevSecOps"}, headers=auth_headers)
    assert made.status_code == 201, made.text
    course = made.json()
    assert (course["course_type"], course["price"], course["show_internship_fee"]) == ("internship", 0.0, False)
    # an internship course cannot be given a price of its own
    assert (await client.post("/api/v1/courses/", json={"title": "Priced", "slug": "priced", "course_type": "internship", "price": 100}, headers=auth_headers)).status_code == 422

    # ---- 3: link it to the existing internship (the internship's own setting is the only link)
    await configure_onboarding(client, auth_headers, orm, **TAX)  # the internship has a real fee, which must not leak into course screens
    assert (await client.patch(f"{BASE}/{internship['id']}", json={"lms_course_id": course["id"]}, headers=auth_headers)).status_code == 200
    detail = (await client.get(f"/api/v1/courses/{course['id']}", headers=auth_headers)).json()
    listing = (await client.get("/api/v1/courses/?course_type=internship", headers=auth_headers)).json()
    assert [i["title"] for i in detail["linked_internships"]] == [internship["title"]]
    for view in (detail, listing):  # Hide Fee: no price, no fee, in any course interface
        text = json.dumps(view)
        assert '"fee": {' not in text and "5900" not in text and "5,900" not in text and "5000" not in text
    assert detail["linked_internships"][0]["fee"] is None and detail["price"] == 0.0

    # ---- 4-5: the course name in the preview, the generated PDFs and the Email Studio preview, apart from the internship's name
    await approved(client, auth_headers, internship, programme=ABOUT, email=EMAIL)
    settings = (await client.get(url(internship), headers=auth_headers)).json()
    assert settings["config"]["programme"]["name"] == ""  # the programme name is NOT replaced by the course name
    preview = text_of((await client.post(url(internship, "/preview"), json={}, headers=auth_headers)).content)
    assert f"You will study {COURSE} during {internship['title']}." in preview
    # the wording changed, so every letter is outdated, the released one included; only the unreleased ones are redone
    assert all(r["letter"]["outdated"] for r in by_name(await students(client, auth_headers, internship)).values())
    redo = await generate(client, auth_headers, internship, world, student_ids=[ids["meera@example.com"], ids["ravi@example.com"]], regenerate=True)
    assert redo["queued"] == 2
    rows = by_name(await students(client, auth_headers, internship))
    meera = rows["Meera Iyer"]["letter"]
    generated = text_of(await pdf_of(client, auth_headers, internship, meera["id"]))
    assert f"You will study {COURSE} during {internship['title']}." in generated and generated.count(COURSE) >= 1
    from tests.api.test_email_studio import assign, create, page, publish

    template = await create(client, auth_headers, name="Offer with course", html=page("<p>Programme: <b>{{internship_name}}</b>. Course: <b>{{lms_course_name}}</b></p>"), subject="Offer: {{internship_name}}")
    await publish(client, auth_headers, template)
    await assign(client, auth_headers, "internship_offer_letter", template["id"])
    studio = (await client.post(url(internship, "/email-preview"), json={}, headers=auth_headers)).json()
    assert studio["source"] == "studio" and COURSE in studio["html"] and internship["title"] in studio["html"]

    # ---- 6: approve and release a letter; the email is rendered from the same values and goes only to the fake mailbox
    await release_and_send(client, auth_headers, internship, meera["id"])
    mail = world.mail.sent[-1]
    assert mail["to"] == "meera@example.com" and COURSE in mail["html"] and internship["title"] in mail["html"]
    assert all(m["to"].endswith("@example.com") for m in world.mail.sent)  # nothing could reach a real person

    # ---- 7: what was released before this feature is exactly as it was (flagged outdated, never rewritten, never resent)
    assert await pdf_of(client, auth_headers, internship, asha["id"]) == released_pdf
    now_asha = {s["name"]: s["letter"] for s in (await students(client, auth_headers, internship))["students"]}["Asha Rao"]
    assert (now_asha["id"], now_asha["version"], now_asha["status"]) == (released_before["id"], released_before["version"], released_before["status"])
    assert now_asha["outdated"] is True  # flagged, so nobody releases it again by accident
    assert len([m for m in world.mail.sent if m["to"] == "asha@example.com"]) == 1

    # ---- 8: a student onboards; the portal shows the course; access waits for a ready course and follows the usual gates
    s_meera = await db_session.get(InstitutionStudent, uuid.UUID(ids["meera@example.com"]))
    await configure_onboarding(client, auth_headers, orm)
    token = await onboarding_link(client, auth_headers, SimpleNamespace(id=internship_id), s_meera)
    shown = (await client.get(PUBLIC, headers=tok(token))).json()
    assert shown["internship"]["title"] == internship["title"] and shown["learning_course"]["title"] == COURSE
    assert (shown["learning_course"]["accessible"], shown["learning_course"]["lms_url"]) == (False, None)
    await ready(db_session, orm, s_meera)
    refused = await grant(client, auth_headers, orm, s_meera)
    assert refused.status_code == 422 and "not published" in refused.json()["error"]["message"]  # a draft course is never granted
    await ChapterRepository(db_session).create(course_id=uuid.UUID(course["id"]), title="Pipelines", order_index=1)
    await db_session.flush()
    assert (await client.post(f"/api/v1/courses/{course['id']}/publish", headers=auth_headers)).status_code == 200
    assert (await grant(client, auth_headers, orm, s_meera)).status_code == 200
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s_meera.id))).scalar_one()
    mine = await student_login(db_session, selection)
    internships = (await client.get("/api/v1/my-internships", headers=mine)).json()
    assert internships[0]["title"] == internship["title"] and internships[0]["course"]["title"] == COURSE and internships[0]["course"]["accessible"]
    courses = (await client.get("/api/v1/lms/enrollment/me", headers=mine)).json()
    assert [i["title"] for i in courses[0]["internships"]] == [internship["title"]]
    assert (await client.get(f"/api/v1/courses/{course['id']}/chapters/me", headers=mine)).status_code == 200
    assert (await client.get(PUBLIC, headers=tok(token))).json()["learning_course"]["accessible"] is True
    # ordinary students without access see nothing of it, and withdrawn access shuts the course
    assert (await revoke(client, auth_headers, orm, s_meera)).status_code == 200
    assert (await client.get(f"/api/v1/courses/{course['id']}/chapters/me", headers=mine)).status_code == 403
    assert (await client.get("/api/v1/my-internships", headers=mine)).json() == []  # nothing of it remains visible


async def test_regular_courses_and_the_internship_fee_receipts_and_invoices_are_unaffected(client, auth_headers, db_session, organization, rbac_seeded, storage):  # noqa: F811
    # an ordinary course keeps its price and its screens exactly
    regular = (await client.post("/api/v1/courses/", json={"title": "Python Basics", "slug": "python-basics", "level": "beginner", "price": 4999}, headers=auth_headers)).json()
    assert (regular["course_type"], regular["price"], regular["linked_internships"]) == ("regular", 4999.0, [])
    # an internship that uses an internship course charges, issues and records exactly as an internship without one
    internship, (s0, s1) = await onboarding_world(db_session, organization)
    other, (t0,) = await onboarding_world(db_session, organization, n=1)
    course = (await client.post("/api/v1/courses/", json={"title": COURSE, "slug": "devsecops-l1", "level": "beginner", "course_type": "internship", "show_internship_fee": True}, headers=auth_headers)).json()
    assert (await client.patch(f"{BASE}/{internship.id}", json={"lms_course_id": course["id"]}, headers=auth_headers)).status_code == 200
    await paid_by_bank(client, auth_headers, db_session, internship, s0, **TAX, _amount="5900.00")
    await paid_by_bank(client, auth_headers, db_session, other, t0, **TAX, _amount="5900.00")  # the same with no course linked at all
    docs = (await db_session.execute(select(FinancialDocument).order_by(FinancialDocument.issued_at))).scalars().all()
    assert len(docs) == 2
    for doc in docs:
        assert COURSE not in json.dumps(doc.details, default=str)  # no course name on a financial document
        assert doc.kind == "tax_invoice" and str(doc.amount) == "5900.00"
    pdf = (await client.get(f"{BASE}/{internship.id}/receipts/{docs[0].id}/pdf", headers=auth_headers)).content
    assert COURSE not in " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert (await db_session.execute(select(func.count(PaymentTransaction.id)))).scalar_one() == 2  # one payment each: linking a course creates none
    # with Show Fee the course screen reads the amount the onboarding charges, to people who may see finance, and nothing else changed
    shown = (await client.get(f"/api/v1/courses/{course['id']}", headers=auth_headers)).json()["linked_internships"][0]["fee"]
    assert shown["total"] == "5900.00" and shown["tax"] == "900.00"
