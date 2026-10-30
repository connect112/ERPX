"""
Bulk downloads (modules/bulk_exports).

What must hold: only documents the person may see, inside their own organization, end up in a ZIP; the ZIP holds the
documents exactly as the module produces them, under the names the administrator chose; a large selection is handed to
the worker; failures are reported without stopping the rest; every job, link and file belongs to the person who asked;
the ZIP expires and is removed; and the request leaves an audit record.
"""

import io
import secrets
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from modules.audit.models import AuditLog
from modules.bulk_exports.models import BulkExportJob, ExportStatus
from modules.bulk_exports.service import BulkExportService
from modules.bulk_exports.sources import SOURCES
from modules.documents.models import Document, DocumentStatus
from modules.institutions.models import Institution, InstitutionStudent
from modules.our_internships.letter_models import OfferLetter
from modules.our_internships.models import InternshipScope, OurInternship
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from packages.storage import client as storage_client
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

BASE = "/api/v1/bulk-exports"


class FakeStorage:
    """Object storage in memory: what the export uploads, reads and removes."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.links: list[dict] = []

    async def upload_file(self, key, path, content_type="application/octet-stream"):
        with open(path, "rb") as fh:
            self.objects[key] = fh.read()

    async def read_bytes(self, key, max_bytes=0):
        return self.objects[key]

    async def delete_object(self, key):
        self.objects.pop(key, None)

    def presigned_download_url(self, key, expires=None, download_name=None):
        self.links.append({"key": key, "expires": expires, "name": download_name})
        return f"https://files.example.test/{key}?sig=1"


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage_client, "get_storage_client", lambda: fake)
    return fake


@pytest.fixture
def queued(monkeypatch):
    from modules.bulk_exports.tasks import run_bulk_export_task

    calls: list[list] = []
    monkeypatch.setattr(run_bulk_export_task, "apply_async", lambda args=None, **kw: calls.append(args))
    return calls


async def make_exam(db, organization, *, title="Cloud Basics", names=("Asha Rao", "Ben Paul", "Chitra N"), unissued=1):
    exam = WorkshopExam(
        organization_id=organization.id,
        public_code=secrets.token_urlsafe(9),
        title=title,
        info_fields=[{"key": "registration_id", "label": "Registration ID", "required": False, "type": "text"}],
    )
    db.add(exam)
    await db.flush()
    attendees = []
    now = datetime.now(timezone.utc)
    for i, name in enumerate(names):
        a = WorkshopExamAttendee(
            exam_id=exam.id, name=name, email=f"p{i}-{uuid.uuid4().hex[:6]}@example.com",
            access_token=secrets.token_urlsafe(24), submitted_at=now, score=10 + i, total_marks=20,
            certificate_number=f"WS-{uuid.uuid4().hex[:8].upper()}", info={"registration_id": f"REG{i + 1:03d}"},
            certificate_sent_at=now if i == 0 else None,
        )
        db.add(a)
        attendees.append(a)
    for i in range(unissued):  # registered but no certificate yet: never offered, never created by an export
        db.add(WorkshopExamAttendee(exam_id=exam.id, name=f"Pending {i}", email=f"pending{i}-{uuid.uuid4().hex[:6]}@example.com",
                                    access_token=secrets.token_urlsafe(24)))
    await db.flush()
    return exam, attendees


def job_body(source, scope_id, selection, template="{{student_name}}_{{certificate_id}}.pdf", **options):
    return {"source": source, "scope_id": str(scope_id) if scope_id else None, "selection": selection,
            "options": {"filename_template": template, **options}}


async def fetch_zip(client, headers, storage, job_id) -> zipfile.ZipFile:
    r = await client.post(f"{BASE}/jobs/{job_id}/download", headers=headers)
    assert r.status_code == 200, r.text
    key = storage.links[-1]["key"]
    return zipfile.ZipFile(io.BytesIO(storage.objects[key]))


# ------------------------------------------------------------ what can be downloaded


async def test_placeholders_include_the_modules_own_fields_and_presets(client, auth_headers, db_session, organization):
    exam, _ = await make_exam(db_session, organization)
    r = await client.get(f"{BASE}/sources/exam_certificates", params={"scope_id": str(exam.id)}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {p["key"]: p for p in body["placeholders"]}
    assert {"student_name", "certificate_id", "program_name", "document_type", "index", "export_date"} <= set(keys)
    assert keys["registration_id"]["custom"] is True and keys["registration_id"]["label"] == "Registration ID"
    assert body["scope_label"] == "Cloud Basics" and body["extension"] == "pdf"
    assert body["presets"] and body["status_options"]


async def test_only_issued_certificates_are_listed_with_paging_search_and_status(client, auth_headers, db_session, organization):
    exam, attendees = await make_exam(db_session, organization)
    url = f"{BASE}/sources/exam_certificates/items"
    page1 = (await client.get(url, params={"scope_id": str(exam.id), "page_size": 2}, headers=auth_headers)).json()
    page2 = (await client.get(url, params={"scope_id": str(exam.id), "page_size": 2, "page": 2}, headers=auth_headers)).json()
    assert page1["total"] == 3  # the attendee without a certificate is not offered
    assert [i["title"] for i in page1["items"] + page2["items"]] == ["Asha Rao", "Ben Paul", "Chitra N"]
    found = (await client.get(url, params={"scope_id": str(exam.id), "search": "chitra"}, headers=auth_headers)).json()
    assert [i["title"] for i in found["items"]] == ["Chitra N"]
    sent = (await client.get(url, params={"scope_id": str(exam.id), "status": "sent"}, headers=auth_headers)).json()
    assert [i["title"] for i in sent["items"]] == ["Asha Rao"]


# ------------------------------------------------------------ naming


async def test_the_preview_shows_the_names_and_refuses_unknown_placeholders_and_wrong_extensions(client, auth_headers, db_session, organization):
    exam, attendees = await make_exam(db_session, organization, names=("Asha Rao", "Asha Rao", "Ben Paul"))
    body = {"source": "exam_certificates", "scope_id": str(exam.id),
            "options": {"filename_template": "{{registration_id}}_{{student_name}}.pdf", "folder_template": "{{program_name}}",
                        "zip_template": "{{scope_name}}_certificates"}}
    ok = (await client.post(f"{BASE}/preview", json=body, headers=auth_headers)).json()
    assert ok["valid"] is True and ok["total"] == 3
    assert ok["zip_filename"] == "Cloud Basics_certificates.zip"
    assert sorted(f["path"] for f in ok["files"]) == ["Cloud Basics/REG001_Asha Rao.pdf", "Cloud Basics/REG002_Asha Rao.pdf", "Cloud Basics/REG003_Ben Paul.pdf"]

    same = (await client.post(f"{BASE}/preview", json={**body, "options": {"filename_template": "{{student_name}}"}}, headers=auth_headers)).json()
    assert [f["path"] for f in same["files"]][:2] == ["Asha Rao.pdf", "Asha Rao_2.pdf"] and same["renamed_duplicates"] == 1

    unknown = (await client.post(f"{BASE}/preview", json={**body, "options": {"filename_template": "{{roll_no}}.pdf"}}, headers=auth_headers)).json()
    assert unknown["valid"] is False and "{{roll_no}}" in unknown["error"]
    wrong = (await client.post(f"{BASE}/preview", json={**body, "options": {"filename_template": "{{student_name}}.exe"}}, headers=auth_headers)).json()
    assert wrong["valid"] is False and ".exe" in wrong["error"]
    escape = (await client.post(f"{BASE}/preview", json={**body, "options": {"filename_template": "../{{student_name}}"}}, headers=auth_headers)).json()
    assert escape["valid"] is False


async def test_missing_values_are_warned_about(client, auth_headers, db_session, organization):
    exam, attendees = await make_exam(db_session, organization)
    attendees[1].info = {}
    await db_session.flush()
    body = {"source": "exam_certificates", "scope_id": str(exam.id), "options": {"filename_template": "{{registration_id}}_{{student_name}}"}}
    out = (await client.post(f"{BASE}/preview", json=body, headers=auth_headers)).json()
    assert out["files"][1]["path"] == "Ben Paul.pdf" and out["files"][1]["missing"] == ["registration_id"]
    assert any("registration_id" in w for w in out["warnings"])


async def test_a_job_with_an_unusable_template_is_refused(client, auth_headers, db_session, organization, storage):
    exam, attendees = await make_exam(db_session, organization)
    r = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}, "{{nope}}"), headers=auth_headers)
    assert r.status_code in (400, 422) and "nope" in r.text


# ------------------------------------------------------------ the ZIP


async def test_a_small_selection_is_zipped_straight_away_with_the_chosen_names(client, auth_headers, db_session, organization, storage):
    exam, attendees = await make_exam(db_session, organization)
    body = job_body("exam_certificates", exam.id, {"mode": "selected", "ids": [str(attendees[2].id), str(attendees[0].id)]},
                    "{{index}}_{{student_name}}_{{certificate_id}}.pdf", folder_template="{{certificate_type}}",
                    zip_template="{{scope_name}}_{{count}}")
    r = await client.post(f"{BASE}/jobs", json=body, headers=auth_headers)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "completed" and job["processed_items"] == 2 and job["failed_items"] == 0
    assert job["zip_filename"] == "Cloud Basics_2.zip" and job["expires_at"]
    archive = await fetch_zip(client, auth_headers, storage, job["id"])
    heading = exam.certificate_heading
    assert archive.namelist() == [
        f"{heading}/001_Chitra N_{attendees[2].certificate_number}.pdf",
        f"{heading}/002_Asha Rao_{attendees[0].certificate_number}.pdf",
    ]
    assert all(archive.read(n).startswith(b"%PDF") for n in archive.namelist())
    link = storage.links[-1]
    assert link["name"] == "Cloud Basics_2.zip" and link["expires"] == timedelta(minutes=settings.BULK_EXPORT_LINK_MINUTES)
    # an export issues nothing: the attendee without a certificate still has none
    pending = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == exam.id,
                                                                            WorkshopExamAttendee.name == "Pending 0"))).scalar_one()
    assert pending.certificate_number is None


async def test_select_all_matching_works_across_pages_minus_the_ones_left_out(client, auth_headers, db_session, organization, storage):
    exam, attendees = await make_exam(db_session, organization, names=[f"Student {i:02d}" for i in range(12)])
    body = job_body("exam_certificates", exam.id, {"mode": "filtered", "search": "student", "exclude_ids": [str(attendees[5].id)]},
                    "{{student_name}}")
    job = (await client.post(f"{BASE}/jobs", json=body, headers=auth_headers)).json()
    assert job["total_items"] == 11 and job["status"] == "completed"
    names = (await fetch_zip(client, auth_headers, storage, job["id"])).namelist()
    assert len(names) == 11 and "Student 05.pdf" not in names


async def test_offer_letters_are_copied_byte_for_byte_with_student_columns_as_placeholders(client, auth_headers, db_session, organization, storage):
    internship = OurInternship(organization_id=organization.id, title="Cloud Internship", scope=InternshipScope.ALL)
    institution = Institution(organization_id=organization.id, name="City College", location="Pune", faculty_name="Dr. K")
    db_session.add_all([internship, institution])
    await db_session.flush()
    letters = []
    for i, name in enumerate(["Asha Rao", "Ben Paul"]):
        student = InstitutionStudent(organization_id=organization.id, institution_id=institution.id, name=name,
                                     email=f"s{i}@example.com", details={"Registration Number": f"R-{i}"})
        db_session.add(student)
        await db_session.flush()
        pdf = b"%PDF-1.4 original letter with signature " + name.encode() + secrets.token_bytes(64)
        letter = OfferLetter(organization_id=organization.id, internship_id=internship.id, student_id=student.id,
                             reference=f"OL-{i}", student_name=name, student_email=student.email, institution_name="City College",
                             status="released", filename="x.pdf", pdf_data=pdf, pdf_size=len(pdf))
        db_session.add(letter)
        letters.append(letter)
    db_session.add(OfferLetter(organization_id=organization.id, internship_id=internship.id, reference="OL-P", student_name="Not Ready",
                               student_email="n@example.com", institution_name="City College", status="pending"))
    await db_session.flush()
    info = (await client.get(f"{BASE}/sources/offer_letters", params={"scope_id": str(internship.id)}, headers=auth_headers)).json()
    assert "registration_number" in {p["key"] for p in info["placeholders"]}
    body = job_body("offer_letters", internship.id, {"mode": "filtered"}, "{{registration_number}}_{{student_name}}.pdf",
                    folder_template="{{institution_name}}")
    job = (await client.post(f"{BASE}/jobs", json=body, headers=auth_headers)).json()
    assert job["status"] == "completed" and job["total_items"] == 2  # the pending letter has no PDF
    archive = await fetch_zip(client, auth_headers, storage, job["id"])
    assert archive.read("City College/R-0_Asha Rao.pdf") == letters[0].pdf_data
    assert archive.read("City College/R-1_Ben Paul.pdf") == letters[1].pdf_data


async def test_uploaded_documents_keep_their_own_extension(client, auth_headers, db_session, organization, storage):
    for name, data in (("contract.docx", b"DOCX"), ("scan.pdf", b"%PDF scan")):
        key = f"{organization.id}/corporate_clients/{uuid.uuid4()}-{name}"
        storage.objects[key] = data
        db_session.add(Document(organization_id=organization.id, entity_type="corporate_clients", filename=name,
                                content_type="application/octet-stream", size_bytes=len(data), storage_key=key,
                                status=DocumentStatus.UPLOADED))
    await db_session.flush()
    refused = await client.post(f"{BASE}/preview", json={"source": "documents", "options": {"filename_template": "{{original_name}}.pdf"}},
                                headers=auth_headers)
    assert refused.json()["valid"] is False
    job = (await client.post(f"{BASE}/jobs", json=job_body("documents", None, {"mode": "filtered"}, "{{record_type}}_{{original_name}}"),
                             headers=auth_headers)).json()
    archive = await fetch_zip(client, auth_headers, storage, job["id"])
    assert sorted(archive.namelist()) == ["corporate_clients_contract.docx", "corporate_clients_scan.pdf"]
    assert archive.read("corporate_clients_contract.docx") == b"DOCX"


async def test_a_document_that_fails_is_reported_and_the_others_are_still_zipped(client, auth_headers, db_session, organization, storage, monkeypatch):
    exam, attendees = await make_exam(db_session, organization)
    source = SOURCES["exam_certificates"]
    original = type(source).fetch

    async def flaky(self, db, scope, item):
        if item.title == "Ben Paul":
            raise RuntimeError("renderer crashed")
        return await original(self, db, scope, item)

    monkeypatch.setattr(type(source), "fetch", flaky)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}, "{{student_name}}"),
                             headers=auth_headers)).json()
    assert job["status"] == "completed" and job["processed_items"] == 2 and job["failed_items"] == 1
    assert job["failures"][0]["title"] == "Ben Paul" and "renderer crashed" not in job["failures"][0]["error"]  # no internals leak
    names = (await fetch_zip(client, auth_headers, storage, job["id"])).namelist()
    assert "_failed_documents.txt" in names and "Ben Paul.pdf" not in names


async def test_a_large_selection_goes_to_the_worker(client, auth_headers, db_session, organization, storage, queued, monkeypatch):
    monkeypatch.setattr(settings, "BULK_EXPORT_INLINE_MAX_ITEMS", 2)
    exam, attendees = await make_exam(db_session, organization)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)).json()
    assert job["status"] == "queued" and queued == [[job["id"]]]
    # what the worker does with it
    row = await db_session.get(BulkExportJob, uuid.UUID(job["id"]))
    await BulkExportService(db_session).run(row, db_session.flush)
    progress = (await client.get(f"{BASE}/jobs/{job['id']}", headers=auth_headers)).json()
    assert progress["status"] == "completed" and progress["processed_items"] == 3


async def test_a_queued_job_can_be_cancelled_and_then_does_nothing(client, auth_headers, db_session, organization, storage, queued, monkeypatch):
    monkeypatch.setattr(settings, "BULK_EXPORT_INLINE_MAX_ITEMS", 0)
    exam, _ = await make_exam(db_session, organization)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)).json()
    cancelled = await client.post(f"{BASE}/jobs/{job['id']}/cancel", headers=auth_headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    row = await db_session.get(BulkExportJob, uuid.UUID(job["id"]))
    await BulkExportService(db_session).run(row, db_session.flush)
    assert row.status == "cancelled" and not storage.objects
    assert (await client.post(f"{BASE}/jobs/{job['id']}/download", headers=auth_headers)).status_code == 409


async def test_limits_on_size_and_on_jobs_running_at_once(client, auth_headers, db_session, organization, storage, queued, monkeypatch):
    exam, _ = await make_exam(db_session, organization)
    monkeypatch.setattr(settings, "BULK_EXPORT_MAX_ITEMS", 2)
    too_many = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)
    assert too_many.status_code in (400, 422) and "at most 2" in too_many.text
    monkeypatch.setattr(settings, "BULK_EXPORT_MAX_ITEMS", 5000)
    monkeypatch.setattr(settings, "BULK_EXPORT_INLINE_MAX_ITEMS", 0)
    monkeypatch.setattr(settings, "BULK_EXPORT_MAX_ACTIVE_PER_USER", 1)
    first = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)
    assert first.status_code == 201
    second = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)
    assert second.status_code == 409


# ------------------------------------------------------------ who may download what


async def test_people_without_the_modules_permission_are_refused(client, staff_headers, db_session, organization, storage):
    exam, attendees = await make_exam(db_session, organization)
    assert (await client.get(f"{BASE}/sources/exam_certificates", params={"scope_id": str(exam.id)}, headers=staff_headers)).status_code == 403
    r = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=staff_headers)
    assert r.status_code == 403
    assert (await client.get(f"{BASE}/sources/payslips", params={"scope_id": str(uuid.uuid4())}, headers=staff_headers)).status_code == 403
    assert (await client.get(f"{BASE}/sources/documents", headers=staff_headers)).status_code == 403
    assert (await client.get(f"{BASE}/sources/no_such_thing", headers=staff_headers)).status_code == 404


async def test_an_administrator_with_the_view_permission_can_download(client, db_session, organization, storage):
    exam, attendees = await make_exam(db_session, organization)
    headers = await admin_headers(db_session, organization, permissions=("workshops.view",))
    job = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=headers)
    assert job.status_code == 201 and job.json()["status"] == "completed"
    # ...but not another module's documents
    assert (await client.get(f"{BASE}/sources/documents", headers=headers)).status_code == 403


async def test_another_organizations_documents_never_get_in(client, auth_headers, db_session, organization, storage):
    from modules.organizations.repository import OrganizationRepository

    other_org = await OrganizationRepository(db_session).create(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    theirs, their_attendees = await make_exam(db_session, other_org, title="Their Exam")
    mine, my_attendees = await make_exam(db_session, organization)
    # their exam does not exist for us
    assert (await client.get(f"{BASE}/sources/exam_certificates", params={"scope_id": str(theirs.id)}, headers=auth_headers)).status_code == 404
    # their attendees' ids smuggled into a selection on our exam are dropped
    smuggled = {"mode": "selected", "ids": [str(their_attendees[0].id), str(my_attendees[0].id)]}
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", mine.id, smuggled, "{{student_name}}"), headers=auth_headers)).json()
    assert job["total_items"] == 1
    assert (await fetch_zip(client, auth_headers, storage, job["id"])).namelist() == ["Asha Rao.pdf"]
    only_theirs = {"mode": "selected", "ids": [str(a.id) for a in their_attendees]}
    refused = await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", mine.id, only_theirs), headers=auth_headers)
    assert refused.status_code in (400, 422)


async def test_a_job_and_its_file_belong_only_to_the_person_who_asked(client, auth_headers, db_session, organization, storage):
    exam, _ = await make_exam(db_session, organization)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)).json()
    colleague = await admin_headers(db_session, organization, permissions=("workshops.view",))
    assert (await client.get(f"{BASE}/jobs/{job['id']}", headers=colleague)).status_code == 404
    assert (await client.post(f"{BASE}/jobs/{job['id']}/download", headers=colleague)).status_code == 404
    assert (await client.delete(f"{BASE}/jobs/{job['id']}/file", headers=colleague)).status_code == 404
    assert job["id"] not in {j["id"] for j in (await client.get(f"{BASE}/jobs", headers=colleague)).json()}
    assert job["id"] in {j["id"] for j in (await client.get(f"{BASE}/jobs", headers=auth_headers)).json()}


async def test_someone_who_lost_access_cannot_collect_the_file(client, db_session, organization, storage):
    from modules.authorization.repository import AuthorizationRepository

    exam, _ = await make_exam(db_session, organization)
    headers = await admin_headers(db_session, organization, permissions=("workshops.view",))
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=headers)).json()
    row = await db_session.get(BulkExportJob, uuid.UUID(job["id"]))
    repo = AuthorizationRepository(db_session)
    for role in await repo.get_roles_for_user(row.requested_by_user_id):
        await repo.revoke_role(row.requested_by_user_id, role.id)
    await db_session.flush()
    assert (await client.post(f"{BASE}/jobs/{job['id']}/download", headers=headers)).status_code == 403


# ------------------------------------------------------------ expiry, clean-up and the record


async def test_expired_files_are_removed_and_can_no_longer_be_downloaded(client, auth_headers, db_session, organization, storage):
    exam, _ = await make_exam(db_session, organization)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)).json()
    row = await db_session.get(BulkExportJob, uuid.UUID(job["id"]))
    key = row.storage_key
    assert key.startswith(f"bulk-exports/{organization.id}/") and key in storage.objects
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    stale = BulkExportJob(organization_id=organization.id, requested_by_user_id=row.requested_by_user_id, source="exam_certificates",
                          scope_id=exam.id, scope_label="x", status="running", selection_mode="filtered", total_items=1,
                          created_at=datetime.now(timezone.utc) - timedelta(hours=3))
    db_session.add(stale)
    await db_session.flush()
    assert (await client.post(f"{BASE}/jobs/{job['id']}/download", headers=auth_headers)).status_code == 409
    result = await BulkExportService(db_session).cleanup()
    assert result["expired"] >= 1 and result["stale"] >= 1
    assert key not in storage.objects and row.status == ExportStatus.EXPIRED.value and row.storage_key is None
    assert stale.status == "failed"


async def test_a_file_can_be_removed_before_it_expires(client, auth_headers, db_session, organization, storage):
    exam, _ = await make_exam(db_session, organization)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)).json()
    r = await client.delete(f"{BASE}/jobs/{job['id']}/file", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "expired" and not storage.objects


async def test_the_request_and_each_download_are_in_the_audit_trail_without_the_id_list(client, auth_headers, superuser, db_session, organization, storage):
    exam, _ = await make_exam(db_session, organization)
    job = (await client.post(f"{BASE}/jobs", json=job_body("exam_certificates", exam.id, {"mode": "filtered"}), headers=auth_headers)).json()
    await client.post(f"{BASE}/jobs/{job['id']}/download", headers=auth_headers)
    rows = (await db_session.execute(select(AuditLog).where(AuditLog.entity_type == "bulk_export_jobs",
                                                            AuditLog.entity_id == uuid.UUID(job["id"])))).scalars().all()
    actions = [r.action.value for r in rows]
    assert "create" in actions and "update" in actions
    created = next(r for r in rows if r.action.value == "create")
    assert created.user_id == superuser[0].id and created.changes["source"] == "exam_certificates"
    assert "item_ids" not in created.changes
    assert any("download_count" in r.changes for r in rows if r.action.value == "update")
