"""
Internship onboarding (modules/internship_onboarding): settings and templates, references and links, the student
portal (drafts, documents, acceptance), deadlines and reopening, document review, the dashboard, and offer-email values.
Synthetic data only; object storage is an in-memory fake.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from modules.institutions.models import Institution, InstitutionStudent
from modules.internship_onboarding.models import OnboardingApplication, OnboardingDocument, PaymentTransaction
from modules.our_internships.models import InternshipScope, InternshipSelection, OfferStatus, OurInternship
from packages.storage import client as storage_client
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

BASE = "/api/v1/our-internships"
PUBLIC = "/api/v1/public/internship-onboarding"
PDF = b"%PDF-1.4 synthetic test document\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
BANK = {"holder": "GIR Technologies", "bank": "Test Bank", "account_number": "123456789012", "ifsc": "TEST0123456"}


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    async def upload_bytes(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data

    async def delete_object(self, key):
        self.objects.pop(key, None)

    def presigned_download_url(self, key, expires=None, download_name=None):
        return f"https://files.example.test/{key}?sig=1&exp={int(expires.total_seconds()) if expires else 0}"


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage_client, "get_storage_client", lambda: fake)
    return fake


def iso(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def settings(**over) -> dict:
    s = {
        "modes": {"mode": "hybrid", "require_payment": True, "allow_info_edit": True},
        "fees": {"base_amount": "5000", "methods": ["bank_transfer"], "late_fee": {"mode": "fixed", "value": "500"}},
        "deadlines": {"opens_at": iso(-1), "closes_at": iso(10)},
        "payment_accounts": {"bank": BANK},
        "policies": {"refund_policy": "Synthetic refund policy for tests."},
        "form": [
            {"key": "tshirt", "label": "T-shirt size", "type": "dropdown", "options": ["S", "M", "L"], "required": True},
            {"key": "laptop", "label": "Do you have a laptop?", "type": "checkbox"},
        ],
    }
    for k, v in over.items():
        s[k] = {**s.get(k, {}), **v} if isinstance(v, dict) else v
    return s


async def world(db, organization, n=2):
    internship = OurInternship(organization_id=organization.id, title="Cloud Internship 2026", scope=InternshipScope.ALL)
    institution = Institution(organization_id=organization.id, name="City College", location="Pune", faculty_name="Dr. K")
    db.add_all([internship, institution])
    await db.flush()
    students = []
    for i in range(n):
        st = InstitutionStudent(organization_id=organization.id, institution_id=institution.id, name=f"Student {i}",
                                email=f"s{i}-{uuid.uuid4().hex[:6]}@example.com", phone="9876543210", details={"Registration Number": f"R-{i}"})
        db.add(st)
        await db.flush()
        db.add(InternshipSelection(organization_id=organization.id, internship_id=internship.id, student_id=st.id, offer_status=OfferStatus.SENT))
        students.append(st)
    await db.flush()
    return internship, students


async def configure(client, headers, internship, **over):
    r = await client.put(f"{BASE}/{internship.id}/onboarding-flow/config", json={"settings": settings(**over)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def link(client, headers, internship, student) -> str:
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{student.id}/link", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["link"].split("#t=")[1]


def tok(token):
    return {"X-Onboarding-Token": token}


# ------------------------------------------------------------------ settings and templates


async def test_settings_are_versioned_and_contradictions_are_refused(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    fresh = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()
    assert fresh["version"] == 0 and fresh["settings"]["modes"]["mode"] == "manual"  # manual onboarding stays the default
    assert (await configure(client, auth_headers, internship))["version"] == 1
    assert (await configure(client, auth_headers, internship, fees={"base_amount": "6000"}))["version"] == 2
    versions = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config/versions", headers=auth_headers)).json()
    assert [v["version"] for v in versions] == [2, 1]
    bad = await client.put(f"{BASE}/{internship.id}/onboarding-flow/config",
                           json={"settings": settings(fees={"methods": []})}, headers=auth_headers)
    assert bad.status_code in (400, 422) and "payment method" in bad.text


async def test_fees_and_bank_details_need_the_finance_permission(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    admin = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    view = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=admin)).json()
    assert view["settings"]["payment_accounts"]["bank"]["account_number"].endswith("9012")
    assert "1234" not in view["settings"]["payment_accounts"]["bank"]["account_number"]  # masked
    assert view["can_edit_finance"] is False
    # routine settings can be changed...
    ok = await client.put(f"{BASE}/{internship.id}/onboarding-flow/config", json={"settings": settings(communication={"contact_email": "help@example.com"})}, headers=admin)
    assert ok.status_code == 200, ok.text
    # ...but not the fee
    refused = await client.put(f"{BASE}/{internship.id}/onboarding-flow/config", json={"settings": settings(fees={"base_amount": "1"})}, headers=admin)
    assert refused.status_code == 403


async def test_templates_are_versioned_and_applying_one_never_changes_accepted_terms(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))
    accepted = await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))
    assert accepted.status_code == 200 and accepted.json()["acceptance"]["fees"]["total"] == "5000.00"

    t = (await client.post("/api/v1/internship-onboarding-templates", json={"name": "3-Month DevSecOps", "from_internship_id": str(internship.id)}, headers=auth_headers)).json()
    assert t["version"] == 1 and t["settings"]["fees"]["base_amount"] == "5000"
    changed = settings(fees={"base_amount": "9000"})
    t = (await client.patch(f"/api/v1/internship-onboarding-templates/{t['id']}", json={"settings": changed}, headers=auth_headers)).json()
    assert t["version"] == 2
    dup = await client.post(f"/api/v1/internship-onboarding-templates/{t['id']}/duplicate", json={"name": "Copy"}, headers=auth_headers)
    assert dup.status_code == 201 and dup.json()["version"] == 1
    assert (await client.post("/api/v1/internship-onboarding-templates", json={"name": "copy"}, headers=auth_headers)).status_code == 409
    applied = (await client.post(f"{BASE}/{internship.id}/onboarding-flow/apply-template", json={"template_id": t["id"]}, headers=auth_headers)).json()
    assert applied["settings"]["fees"]["base_amount"] == "9000" and applied["template_version"] == 2
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["acceptance"]["fees"]["total"] == "5000.00" and view["payment"]["payable"] == "5000.00"  # what they accepted


# ------------------------------------------------------------------ references and links


async def test_references_are_unique_and_links_are_stored_only_as_hashes(client, auth_headers, db_session, organization):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    first = await link(client, auth_headers, internship, s0)
    await link(client, auth_headers, internship, s1)
    apps = (await db_session.execute(select(OnboardingApplication).where(OnboardingApplication.internship_id == internship.id))).scalars().all()
    refs = sorted(a.reference for a in apps)
    year = datetime.now(timezone.utc).year
    assert refs == [f"ERPX-INT-{year}-000001", f"ERPX-INT-{year}-000002"]
    assert all(a.token_hash and len(a.token_hash) == 64 and a.token_hash != first for a in apps)
    raw = (await db_session.execute(text("select count(*) from audit_logs where changes::text like :t"), {"t": f"%{first}%"})).scalar_one()
    assert raw == 0  # the token is in no row and no audit entry

    # a new link replaces the old one; one application per student whatever happens
    second = await link(client, auth_headers, internship, s0)
    assert (await client.get(PUBLIC, headers=tok(first))).status_code == 404
    assert (await client.get(PUBLIC, headers=tok(second))).status_code == 200
    assert len((await db_session.execute(select(OnboardingApplication).where(OnboardingApplication.internship_id == internship.id))).scalars().all()) == 2
    await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/link/revoke", headers=auth_headers)
    assert (await client.get(PUBLIC, headers=tok(second))).status_code == 404
    assert (await client.get(PUBLIC, headers=tok("x" * 43))).status_code == 404
    assert (await client.get(PUBLIC)).status_code == 404


async def test_manual_onboarding_has_no_student_links(client, auth_headers, db_session, organization):
    internship, (s0, _) = await world(db_session, organization)
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/link", headers=auth_headers)
    assert r.status_code in (400, 422) and "manual" in r.text


async def test_another_organizations_internship_is_invisible(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    theirs, _ = await world(db_session, other)
    assert (await client.get(f"{BASE}/{theirs.id}/onboarding-flow/config", headers=auth_headers)).status_code == 404
    assert (await client.get(f"{BASE}/{theirs.id}/onboarding-flow/dashboard", headers=auth_headers)).status_code == 404


# ------------------------------------------------------------------ the student's side


async def test_a_student_saves_drafts_proposes_corrections_and_uploads_documents(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["student_name"] == "Student 0" and view["open"] and view["statuses"]["overall"] == "not_started"
    assert view["payment"]["bank"] is None  # bank details only once payment is open

    bad = (await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "XXL"}}, headers=tok(token))).json()
    assert bad["errors"] == {"tshirt": "Choose from the list."}
    good = await client.put(f"{PUBLIC}/draft", json={"step": "form", "answers": {"tshirt": "L", "unknown": "x"}, "info": {"name": "Student Zero"}}, headers=tok(token))
    assert good.status_code == 200 and good.json()["errors"] == {}
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["form"]["answers"] == {"tshirt": "L"} and view["current_step"] == "form"
    assert view["information"]["proposed"] == {"name": "Student Zero"} and view["information"]["review"] == "pending"
    assert view["information"]["current"]["name"] == "Student 0"  # nothing is overwritten without review

    exe = await client.post(f"{PUBLIC}/documents/college_id", files={"file": ("id.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")}, headers=tok(token))
    assert exe.status_code in (400, 422) and "do not match" in exe.text
    assert (await client.post(f"{PUBLIC}/documents/aadhaar", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=tok(token))).status_code == 404
    png_for_pdf_only = await client.post(f"{PUBLIC}/documents/signed_offer_letter", files={"file": ("s.png", PNG, "image/png")}, headers=tok(token))
    assert png_for_pdf_only.status_code in (400, 422)
    up = await client.post(f"{PUBLIC}/documents/college_id", files={"file": ("../../id card.jpeg", PNG, "image/png")}, headers=tok(token))
    assert up.status_code == 201 and up.json()["filename"] == "id card.png" and up.json()["version"] == 1
    again = await client.post(f"{PUBLIC}/documents/college_id", files={"file": ("id.pdf", PDF, "application/pdf")}, headers=tok(token))
    assert again.json()["version"] == 2
    docs = (await db_session.execute(select(OnboardingDocument).order_by(OnboardingDocument.version))).scalars().all()
    assert [d.status for d in docs] == ["superseded", "submitted"]
    assert all(k.startswith(f"onboarding/{organization.id}/") for k in storage.objects)

    # staff approve the proposed correction; only then does the record change
    await client.post(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}/info-review", json={"approve": True}, headers=auth_headers)
    await db_session.refresh(s0)
    assert s0.name == "Student Zero"


async def test_acceptance_needs_an_active_declaration_and_records_the_terms_and_fee(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    no_form = await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))
    assert no_form.status_code in (400, 422) and "tshirt" in no_form.text
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "S"}}, headers=tok(token))
    assert (await client.post(f"{PUBLIC}/accept", json={"confirmed": False, "terms_version": "1"}, headers=tok(token))).status_code in (400, 422)
    assert (await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "0"}, headers=tok(token))).status_code == 409
    ok = await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token), )
    assert ok.status_code == 200 and ok.json()["statuses"]["offer"] == "accepted"
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    application = (await db_session.execute(select(OnboardingApplication).where(OnboardingApplication.selection_id == selection.id))).scalar_one()
    assert selection.offer_response.value == "accepted"  # the same field the manual process uses
    assert application.terms_version == "1" and "I accept the internship offer" in application.declaration_text
    assert application.fee_snapshot["total"] == "5000.00" and application.acceptance_meta["ip_hash"]
    assert (await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))).status_code == 409
    assert (await client.post(f"{PUBLIC}/decline", json={}, headers=tok(token))).status_code == 409

    other = await link(client, auth_headers, internship, s1)
    declined = await client.post(f"{PUBLIC}/decline", json={"reason": "Joining another programme"}, headers=tok(other))
    assert declined.json()["statuses"] == {"offer": "declined", "documents": "not_submitted", "payment": "not_initiated", "overall": "cancelled"}
    assert (await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "S"}}, headers=tok(other))).status_code == 409


async def test_after_the_deadline_the_link_is_read_only_until_the_student_is_reopened(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "S"}}, headers=tok(token))
    await configure(client, auth_headers, internship, deadlines={"opens_at": iso(-5), "closes_at": iso(-1 / 24)})
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert view["open"] is False and view["statuses"]["overall"] == "expired"
    assert view["form"]["answers"] == {"tshirt": "S"}  # nothing is lost
    assert (await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))).status_code == 409

    past = await client.post(f"{BASE}/{internship.id}/onboarding-flow/reopen", json={"student_ids": [str(s0.id)], "until": iso(-1), "reason": "x"}, headers=auth_headers)
    assert past.status_code in (400, 422)
    body = {"student_ids": [str(s0.id)], "until": iso(3), "reason": "Medical leave", "late_fee": "config"}
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/reopen", json=body, headers=auth_headers)
    assert r.status_code == 200 and r.json()["reopened"] == 1
    assert (await client.get(PUBLIC, headers=tok(token))).json()["open"] is True
    assert (await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "M"}}, headers=tok(token))).status_code == 200
    # only this student was reopened
    other = await link(client, auth_headers, internship, s1)
    assert (await client.get(PUBLIC, headers=tok(other))).json()["open"] is False
    # one late fee, never two; a waiver cancels it
    await client.post(f"{BASE}/{internship.id}/onboarding-flow/reopen", json={**body, "until": iso(4)}, headers=auth_headers)
    charges = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "charge"))).scalars().all()
    assert [str(c.amount) for c in charges] == ["500.00"]
    assert (await client.get(PUBLIC, headers=tok(token))).json()["payment"]["payable"] == "5500.00"
    await client.post(f"{BASE}/{internship.id}/onboarding-flow/reopen", json={**body, "late_fee": "waive"}, headers=auth_headers)
    assert (await client.get(PUBLIC, headers=tok(token))).json()["payment"]["payable"] == "5000.00"


async def test_late_fees_need_the_finance_permission(client, auth_headers, db_session, organization):
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    admin = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    body = {"student_ids": [str(s0.id)], "until": iso(3), "reason": "x", "late_fee": "custom", "late_fee_amount": "100"}
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/reopen", json=body, headers=admin)).status_code == 403
    body["late_fee"] = "none"
    assert (await client.post(f"{BASE}/{internship.id}/onboarding-flow/reopen", json=body, headers=admin)).status_code == 200


# ------------------------------------------------------------------ review


async def test_document_review_drives_verification_and_needs_the_reviewer_permission(client, auth_headers, db_session, organization, storage, monkeypatch):
    from app.core.config import settings as app_settings
    from modules.internship_onboarding import scan

    async def clean(*args):
        return "stream: OK"

    # identity documents are only collected with a virus scanner (a fake clamd here) and a retention period
    monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
    monkeypatch.setattr(scan, "clamd_instream", clean)
    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, documents=[
        {"key": "college_id", "label": "College ID card"},
        {"key": "govt_id", "label": "Government ID (Aadhaar or alternative)", "sensitive": True},
    ], policies={"refund_policy": "Synthetic refund policy for tests.", "identity_document_retention_days": 365})  # fmt: skip
    token = await link(client, auth_headers, internship, s0)
    for key in ("college_id", "govt_id"):
        await client.post(f"{PUBLIC}/documents/{key}", files={"file": (f"{key}.pdf", PDF, "application/pdf")}, headers=tok(token))
    docs = {d.requirement_key: d for d in (await db_session.execute(select(OnboardingDocument))).scalars().all()}
    manager = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.manage"))
    url = f"{BASE}/{internship.id}/onboarding-flow/documents"
    assert (await client.post(f"{url}/{docs['college_id'].id}/review", json={"approve": True}, headers=manager)).status_code == 403
    assert (await client.get(f"{url}/{docs['govt_id'].id}/preview", headers=manager)).status_code == 403
    detail = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/students/{s0.id}", headers=manager)).json()
    assert {d["key"]: d["filename"] for d in detail["documents"]}["govt_id"] == "(restricted)"
    assert detail["payments"] is None  # no finance permission, no payment records

    reviewer = await admin_headers(db_session, organization, permissions=("our_internships.view", "our_internships.onboarding.review"))
    preview = (await client.get(f"{url}/{docs['govt_id'].id}/preview", headers=reviewer)).json()["url"]
    assert "exp=180" in preview  # a three-minute link
    assert (await client.post(f"{url}/{docs['college_id'].id}/review", json={"approve": False}, headers=reviewer)).status_code in (400, 422)
    await client.post(f"{url}/{docs['college_id'].id}/review", json={"approve": True}, headers=reviewer)
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.verification_status.value == "pending"
    await client.post(f"{url}/{docs['govt_id'].id}/review", json={"approve": True}, headers=reviewer)
    await db_session.refresh(selection)
    assert selection.verification_status.value == "verified"
    # a verified document cannot be replaced by the student
    assert (await client.post(f"{PUBLIC}/documents/govt_id", files={"file": ("x.pdf", PDF, "application/pdf")}, headers=tok(token))).status_code == 409
    # asking for it again puts verification back to pending and lets the student resubmit only that one
    await client.post(f"{url}/{docs['govt_id'].id}/review", json={"approve": False, "note": "Blurred photo"}, headers=reviewer)
    await db_session.refresh(selection)
    assert selection.verification_status.value == "pending"
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert {d["key"]: (d["status"], d["note"]) for d in view["documents"]} == {"college_id": ("verified", None), "govt_id": ("rejected", "Blurred photo")}
    assert (await client.post(f"{PUBLIC}/documents/govt_id", files={"file": ("x.pdf", PDF, "application/pdf")}, headers=tok(token))).status_code == 201


async def test_the_dashboard_counts_each_student_once_with_derived_statuses(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    token = await link(client, auth_headers, internship, s0)
    await client.put(f"{PUBLIC}/draft", json={"answers": {"tshirt": "S"}}, headers=tok(token))
    await client.post(f"{PUBLIC}/accept", json={"confirmed": True, "terms_version": "1"}, headers=tok(token))
    board = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/dashboard", headers=auth_headers)).json()
    rows = {r["name"]: r for r in board["rows"]}
    assert rows["Student 0"]["overall_status"] == "awaiting_documents" and rows["Student 0"]["reference"]
    assert rows["Student 1"]["overall_status"] == "not_started" and rows["Student 1"]["reference"] is None
    assert board["metrics"]["selected"] == 2 and board["metrics"]["accepted"] == 1
    assert board["money"] == {"payable": "5000.00", "received": "0.00", "outstanding": "5000.00"}


# ------------------------------------------------------------------ offer email


async def test_offer_emails_carry_a_fresh_link_and_the_fees_only_when_students_onboard_themselves(client, auth_headers, db_session, organization):
    from modules.internship_onboarding.emails import onboarding_values

    internship, (s0, _) = await world(db_session, organization)
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert set((await onboarding_values(db_session, internship, selection)).values()) == {""}  # manual: nothing to show
    await configure(client, auth_headers, internship, fees={"tax_mode": "exclusive", "tax_rate_percent": "18"})
    values = await onboarding_values(db_session, internship, selection)
    assert "#t=" in values["onboarding_link"] and values["application_reference"].startswith("ERPX-INT-")
    assert values["internship_fee"] == "INR 5,900.00" and values["total_payable"] == "INR 5,900.00" and values["late_fee"] == ""
    token = values["onboarding_link"].split("#t=")[1]
    assert (await client.get(PUBLIC, headers=tok(token))).status_code == 200
