"""
Curriculum resource uploads: a course author attaches a real file to a lesson. It is validated before anything is kept, stored in object
storage (never in the database or a public address), downloaded only through an authenticated, short-lived link, and removed with its
record. Editing the curriculum still needs the course permission, which managing an internship never grants. Synthetic data only.
"""

import uuid

import pytest
from sqlalchemy import select

from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.resources import service as resource_service
from modules.courses.resources.models import Resource
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.organizations.repository import OrganizationRepository
from tests._fixtures import _make_user
from tests.api.test_internship_instructors import _assign, _instructor, _iso
from tests.api.test_internship_learning import FakeStorage, _world
from tests.api.test_internship_lms_integrity import course_in
from tests.api.test_learning_integration import _link, _roles, _solo  # noqa: F401  (the autouse role fixture)

pytestmark = pytest.mark.api

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(resource_service, "get_storage_client", lambda: fake)
    return fake


async def _lesson(db, organization):
    course = await course_in(db, organization)
    chapter = (await ChapterRepository(db).list_for_course(course.id))[0]
    lesson = await LessonRepository(db).create(chapter_id=chapter.id, title="Intro", order_index=1)
    await db.flush()
    return course, chapter, lesson


def _base(course, chapter, lesson) -> str:
    return f"/api/v1/courses/{course.id}/chapters/{chapter.id}/lessons/{lesson.id}/resources"


async def _upload(client, headers, base, name="notes.pdf", data=PDF, title="Week 1 notes", rtype="pdf", downloadable=True, content_type="application/pdf"):
    return await client.post(
        f"{base}/upload",
        files={"file": (name, data, content_type)},
        data={"title": title, "resource_type": rtype, "is_downloadable": str(downloadable).lower()},
        headers=headers,
    )


async def test_an_author_uploads_a_file_that_is_stored_and_listed_with_an_authenticated_download(client, auth_headers, db_session, organization, storage):
    course, chapter, lesson = await _lesson(db_session, organization)
    base = _base(course, chapter, lesson)
    r = await _upload(client, auth_headers, base)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_upload"] is True and body["original_filename"] == "notes.pdf" and body["size_bytes"] == len(PDF)
    assert body["file_url"] == f"{base}/{body['id']}/download"  # never a public storage address
    assert len(storage.objects) == 1
    key, stored = next(iter(storage.objects.items()))
    assert stored == PDF and key.startswith(f"courses/{organization.id}/{course.id}/lessons/{lesson.id}/")
    link = (await client.get(f"{base}/{body['id']}/download", headers=auth_headers)).json()
    assert link["url"] == f"https://storage.test/{key}" and link["filename"] == "notes.pdf"
    assert [x["id"] for x in (await client.get(base, headers=auth_headers)).json()] == [body["id"]]
    # no unauthenticated door
    assert (await client.get(f"{base}/{body['id']}/download")).status_code in (401, 403)


@pytest.mark.parametrize("name", ["setup.exe", "run.bat", "page.html", "image.svg", "script.js", "tool.sh"])
async def test_programs_and_active_content_are_refused_and_nothing_is_stored(client, auth_headers, db_session, organization, storage, name):
    course, chapter, lesson = await _lesson(db_session, organization)
    r = await _upload(client, auth_headers, _base(course, chapter, lesson), name=name, data=b"x", rtype="other", content_type="application/octet-stream")
    assert r.status_code in (400, 422) and "cannot be uploaded" in r.text
    assert storage.objects == {}


async def test_an_empty_oversized_or_mislabelled_file_is_refused(client, auth_headers, db_session, organization, storage, monkeypatch):
    course, chapter, lesson = await _lesson(db_session, organization)
    base = _base(course, chapter, lesson)
    assert (await _upload(client, auth_headers, base, data=b"")).status_code in (400, 422)
    monkeypatch.setattr(resource_service, "MAX_UPLOAD_BYTES", 10)
    assert "larger than" in (await _upload(client, auth_headers, base, data=PDF)).text
    monkeypatch.setattr(resource_service, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
    # a PNG renamed to .pdf, and a text file declared to be a PDF
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    assert "not a valid PDF" in (await _upload(client, auth_headers, base, name="fake.pdf", data=png)).text
    assert "must be a .pdf" in (await _upload(client, auth_headers, base, name="notes.txt", data=b"hello", rtype="pdf", content_type="text/plain")).text
    assert storage.objects == {}
    assert (await db_session.execute(select(Resource))).scalars().all() == []


async def test_a_hostile_file_name_cannot_escape_its_folder(client, auth_headers, db_session, organization, storage):
    course, chapter, lesson = await _lesson(db_session, organization)
    r = await _upload(client, auth_headers, _base(course, chapter, lesson), name="../../etc/passwd.pdf")
    assert r.status_code == 201
    assert r.json()["original_filename"] == "passwd.pdf"
    key = next(iter(storage.objects))
    assert ".." not in key and key.startswith(f"courses/{organization.id}/")


async def test_deleting_the_resource_removes_the_stored_file_and_a_failed_save_leaves_none(client, auth_headers, db_session, organization, storage, monkeypatch):
    course, chapter, lesson = await _lesson(db_session, organization)
    base = _base(course, chapter, lesson)
    rid = (await _upload(client, auth_headers, base)).json()["id"]
    assert len(storage.objects) == 1
    assert (await client.delete(f"{base}/{rid}", headers=auth_headers)).status_code == 200
    assert storage.objects == {}
    # a record that cannot be saved must not leave an orphan file behind
    from modules.courses.resources.repository import ResourceRepository

    async def broken(self, **fields):
        raise RuntimeError("database down")

    monkeypatch.setattr(ResourceRepository, "create", broken)
    with pytest.raises(RuntimeError):
        await _upload(client, auth_headers, base)
    assert storage.objects == {}


async def test_an_uploaded_files_address_cannot_be_repointed_and_a_link_has_nothing_to_download(client, auth_headers, db_session, organization):
    course, chapter, lesson = await _lesson(db_session, organization)
    base = _base(course, chapter, lesson)
    uploaded = (await _upload(client, auth_headers, base)).json()
    assert (await client.patch(f"{base}/{uploaded['id']}", json={"file_url": "https://evil.example/x"}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.patch(f"{base}/{uploaded['id']}", json={"title": "Renamed"}, headers=auth_headers)).status_code == 200
    link = (await client.post(base, json={"title": "Docs site", "resource_type": "link", "file_url": "https://docs.example/"}, headers=auth_headers)).json()
    assert link["is_upload"] is False and link["file_url"] == "https://docs.example/"
    assert (await client.get(f"{base}/{link['id']}/download", headers=auth_headers)).status_code in (400, 422)


# ------------------------------------------------------------ who may upload and who may download


async def test_an_internship_instructor_cannot_upload_or_attach_anything_to_the_curriculum(client, auth_headers, db_session, organization, storage):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    chapter = (await ChapterRepository(db_session).list_for_course(course.id))[0]
    lesson = await LessonRepository(db_session).create(chapter_id=chapter.id, title="Intro", order_index=1)
    await db_session.flush()
    trainer, ila = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer, access_from=_iso(-1), access_until=_iso(10))
    base = _base(course, chapter, lesson)
    existing = (await _upload(client, auth_headers, base)).json()
    assert (await _upload(client, ila, base, name="mine.pdf")).status_code == 403
    assert (await client.post(base, json={"title": "Link", "resource_type": "link", "file_url": "https://x.example"}, headers=ila)).status_code == 403
    assert (await client.delete(f"{base}/{existing['id']}", headers=ila)).status_code == 403
    assert len(storage.objects) == 1
    # but may read and download what the course has, for their own internship's course
    assert (await client.get(base, headers=ila)).status_code == 200
    assert (await client.get(f"{base}/{existing['id']}/download", headers=ila)).status_code == 200


async def test_a_student_downloads_only_through_a_live_enrolment_and_only_a_downloadable_resource(client, auth_headers, db_session, organization):
    course, chapter, lesson = await _lesson(db_session, organization)
    base = _base(course, chapter, lesson)
    open_file = (await _upload(client, auth_headers, base)).json()
    view_only = (await _upload(client, auth_headers, base, name="slides.pdf", title="Slides", downloadable=False)).json()
    student, headers = await _solo(db_session, organization, course)
    assert (await client.get(f"{base}/{open_file['id']}/download", headers=headers)).status_code == 200
    assert (await client.get(f"{base}/{view_only['id']}/download", headers=headers)).status_code == 403  # view only
    assert (await client.get(f"{base}/{view_only['id']}/download", headers=auth_headers)).status_code == 200  # staff may
    enrolment = (await db_session.execute(select(Enrollment).where(Enrollment.student_id == student.id))).scalar_one()
    enrolment.status = EnrollmentStatus.DROPPED
    await db_session.flush()
    assert (await client.get(f"{base}/{open_file['id']}/download", headers=headers)).status_code == 403  # dropped: nothing opens
    # a student of the platform who was never enrolled in this course
    other_course, _, _ = await _lesson(db_session, organization)
    _, stranger = await _solo(db_session, organization, other_course, email="stranger@example.com")
    assert (await client.get(f"{base}/{open_file['id']}/download", headers=stranger)).status_code == 403
    assert (await client.post(f"{base}/upload", files={"file": ("x.pdf", PDF, "application/pdf")}, data={"title": "Mine"}, headers=headers)).status_code == 403  # students never upload


async def test_another_organization_cannot_reach_a_resource_or_its_file(client, auth_headers, db_session, organization, storage):
    course, chapter, lesson = await _lesson(db_session, organization)
    base = _base(course, chapter, lesson)
    rid = (await _upload(client, auth_headers, base)).json()["id"]
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{base}/{rid}/download", headers=outsider)).status_code == 404
    assert (await _upload(client, outsider, base, name="evil.pdf")).status_code == 404
    assert len(storage.objects) == 1
    # a resource addressed through another lesson of the same course is not found
    other_lesson = await LessonRepository(db_session).create(chapter_id=chapter.id, title="Second", order_index=2)
    await db_session.flush()
    assert (await client.get(f"{_base(course, chapter, other_lesson)}/{rid}/download", headers=auth_headers)).status_code == 404
