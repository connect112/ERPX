"""
{{lms_course_name}} in the offer letter and its email: it resolves from the internship's linked LMS course for the preview, the generated
PDF and the release email alike; an unlinked internship leaves it blank (never a raw placeholder) and is never blocked; letters that do
not use it are untouched by a course link or rename; letters that do are marked outdated when the course changes; and a letter that was
generated or released is never rewritten. Synthetic data only.
"""

import uuid

import pytest

from modules.our_internships import letter_tasks
from modules.our_internships.letter_config import PLACEHOLDERS
from tests.api.test_internship_offers import _setup
from tests.api.test_offer_letters import (
    _INTERN,
    approved,
    by_name,
    generate,
    students,
    text_of,
    url,
    world,  # noqa: F401  (the fixture)
)

pytestmark = pytest.mark.api

ABOUT = {"description": "You will study {{lms_course_name}} while you intern."}
EMAIL = {"subject": "Your offer: {{internship_name}}", "body": "Dear {{student_name}},\n\nYour learning course is {{lms_course_name}}.\n\nRegards"}


async def linked_course(client, headers, internship, title="DevSecOps Level-1", publish=False):
    c = await client.post("/api/v1/courses/", json={"title": title, "slug": f"c-{uuid.uuid4().hex[:8]}", "level": "beginner", "course_type": "internship"}, headers=headers)
    assert c.status_code == 201, c.text
    r = await client.patch(f"{_INTERN}/{internship['id']}", json={"lms_course_id": c.json()["id"], "confirm_replace": True}, headers=headers)
    assert r.status_code == 200, r.text
    return c.json()


async def letter_pdf(client, headers, internship, letter_id):
    return (await client.get(url(internship, f"/letters/{letter_id}/pdf"), headers=headers)).content


async def preview_pdf(client, headers, internship):
    r = await client.post(url(internship, "/preview"), json={}, headers=headers)
    assert r.status_code == 200, r.text
    return r.content


def test_the_placeholder_is_offered_in_the_designer_and_the_email_template_list():
    from packages.email.registry import TEMPLATES

    assert "lms_course_name" in PLACEHOLDERS
    offer = next(t for t in TEMPLATES if t.key == "internship_offer_letter")
    assert "lms_course_name" in {v.name for v in offer.variables}


async def test_the_course_name_resolves_the_same_in_the_designer_settings_preview_and_generated_letter(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    await linked_course(client, auth_headers, internship)
    await approved(client, auth_headers, internship, programme=ABOUT)
    assert "lms_course_name" in (await client.get(url(internship), headers=auth_headers)).json()["placeholders"]
    assert "You will study DevSecOps Level-1 while you intern." in text_of(await preview_pdf(client, auth_headers, internship))
    await generate(client, auth_headers, internship, world)
    rows = by_name(await students(client, auth_headers, internship))
    for name, row in rows.items():
        assert "You will study DevSecOps Level-1 while you intern." in text_of(await letter_pdf(client, auth_headers, internship, row["letter"]["id"])), name


async def test_an_unlinked_internship_leaves_it_blank_shows_a_note_and_is_never_blocked(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    await approved(client, auth_headers, internship, programme=ABOUT, email=EMAIL)
    settings = (await client.get(url(internship), headers=auth_headers)).json()
    assert settings["problems"] == [] and any("no LMS course is linked" in n for n in settings["notes"])  # a note, not an obstacle
    await generate(client, auth_headers, internship, world)
    rows = by_name(await students(client, auth_headers, internship))
    asha = rows["Asha Rao"]["letter"]
    text = text_of(await letter_pdf(client, auth_headers, internship, asha["id"]))
    assert "{{" not in text and "lms_course_name" not in text and "You will study while you intern." in text
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    released = (await client.post(url(internship, "/release"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)).json()
    assert released["queued"] == 1  # no course needed to release
    await letter_tasks._send_letter(uuid.UUID(asha["id"]))
    mail = world.mail.sent[0]
    assert "Your learning course is ." in mail["text"] and "{{" not in mail["text"] + mail["subject"]


async def test_the_release_email_uses_the_linked_course_and_matches_the_preview(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    await linked_course(client, auth_headers, internship)
    await approved(client, auth_headers, internship, email=EMAIL)
    await generate(client, auth_headers, internship, world)
    preview = (await client.post(url(internship, "/email-preview"), json={}, headers=auth_headers))
    assert preview.status_code == 200, preview.text
    assert "Your learning course is DevSecOps Level-1." in preview.json()["body"]
    rows = by_name(await students(client, auth_headers, internship))
    asha = rows["Asha Rao"]["letter"]
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await client.post(url(internship, "/release"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await letter_tasks._send_letter(uuid.UUID(asha["id"]))
    assert "Your learning course is DevSecOps Level-1." in world.mail.sent[0]["text"]


async def test_letters_that_do_not_use_the_course_are_not_touched_by_linking_or_renaming_it(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    await approved(client, auth_headers, internship)  # the wording does not mention the course
    await generate(client, auth_headers, internship, world)
    before = by_name(await students(client, auth_headers, internship))
    assert not any(r["letter"]["outdated"] for r in before.values())
    course = await linked_course(client, auth_headers, internship)
    await client.patch(f"/api/v1/courses/{course['id']}", json={"title": "DevSecOps Level-2"}, headers=auth_headers)
    after = by_name(await students(client, auth_headers, internship))
    assert not any(r["letter"]["outdated"] for r in after.values())  # exactly as before this feature existed


async def test_changing_the_course_marks_only_letters_that_print_it_as_outdated_and_never_rewrites_a_pdf(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    course = await linked_course(client, auth_headers, internship)
    await approved(client, auth_headers, internship, programme=ABOUT)
    await generate(client, auth_headers, internship, world)
    rows = by_name(await students(client, auth_headers, internship))
    asha, meera = rows["Asha Rao"]["letter"], rows["Meera Iyer"]["letter"]
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha["id"], meera["id"]]}, headers=auth_headers)
    await client.post(url(internship, "/release"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await letter_tasks._send_letter(uuid.UUID(asha["id"]))
    released_pdf = await letter_pdf(client, auth_headers, internship, asha["id"])
    approved_pdf = await letter_pdf(client, auth_headers, internship, meera["id"])

    await client.patch(f"/api/v1/courses/{course['id']}", json={"title": "DevSecOps Level-2"}, headers=auth_headers)  # a rename
    rows = by_name(await students(client, auth_headers, internship))
    assert all(r["letter"]["outdated"] for r in rows.values())  # flagged, so they cannot be released unseen
    blocked = (await client.post(url(internship, "/release"), json={"letter_ids": [meera["id"]]}, headers=auth_headers)).json()
    assert blocked["queued"] == 0 and "outdated" in blocked["skipped"][0]["reason"]
    # nothing was rewritten: the stored PDFs are byte-for-byte what they were, and still say Level-1
    assert await letter_pdf(client, auth_headers, internship, asha["id"]) == released_pdf
    assert await letter_pdf(client, auth_headers, internship, meera["id"]) == approved_pdf
    assert "DevSecOps Level-1" in text_of(approved_pdf) and "Level-2" not in text_of(approved_pdf)

    redo = await generate(client, auth_headers, internship, world, regenerate=True)
    assert redo["queued"] == 3
    rows = by_name(await students(client, auth_headers, internship))
    new = rows["Meera Iyer"]["letter"]
    assert new["version"] == 2 and new["outdated"] is False
    assert "DevSecOps Level-2" in text_of(await letter_pdf(client, auth_headers, internship, new["id"]))
    assert await letter_pdf(client, auth_headers, internship, meera["id"]) == approved_pdf  # version 1 is kept as it was
    # linking a different course, or removing the link, is a change too
    other = await linked_course(client, auth_headers, internship, title="Cloud Security")
    assert all(r["letter"]["outdated"] for r in by_name(await students(client, auth_headers, internship)).values())
    assert other["id"] != course["id"]


async def test_a_legacy_email_without_the_placeholder_and_a_mistyped_one_behave_as_before(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    await approved(client, auth_headers, internship)  # the default wording: no course placeholder, nothing changes
    config = (await client.get(url(internship), headers=auth_headers)).json()["config"]
    config["email"]["body"] = "Dear {{student_name}}, {{lms_course_nam}}"
    bad = await client.put(url(internship, "/config"), json={"config": config, "scope": "internship"}, headers=auth_headers)
    assert bad.status_code == 422 and "lms_course_nam" in bad.text


async def test_an_assigned_email_studio_template_can_use_the_course_name_and_preview_matches_delivery(client, auth_headers, world):
    from tests.api.test_email_studio import assign, create, page, publish

    internship, _ = await _setup(client, auth_headers)
    await linked_course(client, auth_headers, internship)
    await approved(client, auth_headers, internship)
    template = await create(
        client, auth_headers, name="Offer with course", html=page("<p>Dear {{student_name}}, your course: <b>{{lms_course_name}}</b></p>"),
        subject="Offer for {{internship_name}}",
    )
    await publish(client, auth_headers, template)
    await assign(client, auth_headers, "internship_offer_letter", template["id"])
    await generate(client, auth_headers, internship, world)
    preview = (await client.post(url(internship, "/email-preview"), json={}, headers=auth_headers)).json()
    assert preview["source"] == "studio" and "DevSecOps Level-1" in preview["html"]
    rows = by_name(await students(client, auth_headers, internship))
    asha = rows["Asha Rao"]["letter"]
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await client.post(url(internship, "/release"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await letter_tasks._send_letter(uuid.UUID(asha["id"]))
    assert "DevSecOps Level-1" in world.mail.sent[0]["html"]
