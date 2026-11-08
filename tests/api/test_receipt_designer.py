"""
The Receipt Designer and Generated Receipts: saving designs, defaults and overrides, images, read-only previews, automatic issuing
with the saved design, duplicate and failed payments, credit notes, immutability of issued documents, permissions, organization
isolation and compatibility with documents issued before the designer existed. Synthetic data only; the payment gateway is a fake.
"""

import hashlib
import io
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import undefer

from modules.internship_onboarding import financial
from modules.internship_onboarding.models import (
    FinancialDocument,
    OnboardingCounter,
    OnboardingEvent,
    PaymentTransaction,
    ReceiptAsset,
    ReceiptDesignRecord,
    ReceiptDesignVersion,
)
from tests.api.test_internship_onboarding import BASE, PUBLIC, configure, link, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import gateway, online, payment_event, ready_to_pay, signed  # noqa: F401
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

HOOK = "/api/v1/public/payments/cashfree/webhook"
VIEWER = ("our_internships.view", "our_internships.finance.view")
MANAGER = ("our_internships.view", "our_internships.finance.manage")
NO_FINANCE = ("our_internships.view", "our_internships.manage")
TAX = dict(fees={"tax_mode": "exclusive", "tax_rate_percent": "18"}, issuer={"legal_name": "GIR Technologies Pvt Ltd", "address": "Hyderabad", "gstin": "36ABCDE1234F1Z5"})


async def paid_by_bank(client, headers, db, internship, student, _amount="5000.00", **over):
    """One student pays by bank transfer and finance confirms that claim; returns (the student's link token, the confirmed payment)."""
    from tests.api.test_internship_onboarding_payments import claim

    await configure(client, headers, internship, **over)
    token = await ready_to_pay(client, headers, internship, student)
    assert (await client.post(f"{PUBLIC}/payments/manual", **claim(token, amount=_amount, reference=f"UTR{uuid.uuid4().int % 10**9:09d}"))).status_code == 201
    pending = (await db.execute(select(PaymentTransaction).where(PaymentTransaction.status == "awaiting_verification"))).scalars().all()
    assert len(pending) == 1
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{pending[0].id}/verify", json={"approve": True}, headers=headers)
    assert r.status_code == 200, r.text
    return token, pending[0]


def rd(internship) -> str:
    return f"{BASE}/{internship.id}/receipt-designer"


def png(w=300, h=120, color=(31, 58, 95, 255)) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGBA", (w, h), color).save(out, "PNG")
    return out.getvalue()


def pdf_text(data: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


def pages_of(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


async def design(client, headers, internship, data, scope="internship", expect=200):
    r = await client.put(f"{rd(internship)}/design", json={"scope": scope, "design": data}, headers=headers)
    assert r.status_code == expect, r.text
    return r


async def use_designer(client, headers, internship, scope="organization", data=None):
    """An administrator explicitly saves a design: from then on new documents are drawn with the designer."""
    await design(client, headers, internship, data or {}, scope=scope)


async def upload(client, headers, internship, kind="logo", data=None, name="logo.png", ctype="image/png"):
    return await client.post(f"{rd(internship)}/assets", data={"kind": kind}, files={"file": (name, data if data is not None else png(), ctype)}, headers=headers)


async def counts(db) -> dict:
    return {
        "documents": (await db.execute(select(func.count(FinancialDocument.id)))).scalar_one(),
        "transactions": (await db.execute(select(func.count(PaymentTransaction.id)))).scalar_one(),
        "events": (await db.execute(select(func.count(OnboardingEvent.id)))).scalar_one(),
        "counters": [(c.series, c.year, c.last_value) for c in (await db.execute(select(OnboardingCounter).order_by(OnboardingCounter.series, OnboardingCounter.year))).scalars()],
        "designs": (await db.execute(select(func.count(ReceiptDesignRecord.id)))).scalar_one(),
        "versions": (await db.execute(select(func.count(ReceiptDesignVersion.id)))).scalar_one(),
    }


async def only_document(db) -> FinancialDocument:
    return (await db.execute(select(FinancialDocument).order_by(FinancialDocument.issued_at))).scalars().all()[-1]


# ------------------------------------------------------------------ the designer: defaults, saving, overrides


async def test_the_designer_opens_with_the_built_in_design_and_the_issuers_legal_identity_read_only(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship, **TAX)
    out = (await client.get(rd(internship), headers=auth_headers)).json()
    assert out["effective"]["source"] == "default" and out["effective"]["version"] == 0 and out["effective"] == {**out["effective"], "design": out["built_in"]}
    assert out["issuer"]["gstin"] == "36ABCDE1234F1Z5" and out["issuer"]["legal_name"] == "GIR Technologies Pvt Ltd"  # shown, edited only in the finance-controlled settings
    assert out["fee"]["invoices_issued"] is True and out["can_edit"] is True and out["templates"] == [] and out["assets"] == []


async def test_a_design_can_be_saved_for_the_organization_and_overridden_for_one_internship(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    await design(client, auth_headers, internship, {"branding": {"brand_color": "#0F766E"}, "texts": {"thank_you": "Org thanks"}}, scope="organization")
    out = (await client.get(rd(internship), headers=auth_headers)).json()
    assert out["effective"]["source"] == "organization" and out["effective"]["design"]["texts"]["thank_you"] == "Org thanks"
    await design(client, auth_headers, internship, {"branding": {"brand_color": "#7C2D12"}, "texts": {"thank_you": "Own thanks"}})
    out = (await client.get(rd(internship), headers=auth_headers)).json()
    assert out["effective"]["source"] == "internship" and out["effective"]["design"]["branding"]["brand_color"] == "#7C2D12"
    assert out["organization_design"]["design"]["texts"]["thank_you"] == "Org thanks"  # the default is untouched
    # a sibling internship of the same organization follows the organization's default
    other, _ = await world(db_session, organization, n=1)
    assert (await client.get(rd(other), headers=auth_headers)).json()["effective"]["source"] == "organization"
    # resetting the internship's design returns it to the organization's; resetting that returns to the built-in design
    assert (await client.delete(f"{rd(internship)}/design?scope=internship", headers=auth_headers)).status_code == 200
    assert (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["source"] == "organization"
    assert (await client.delete(f"{rd(internship)}/design?scope=organization", headers=auth_headers)).status_code == 200
    assert (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["source"] == "default"


async def test_every_saved_version_is_kept_a_resave_without_changes_makes_none_and_stale_edits_are_refused(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    assert (await design(client, auth_headers, internship, {"texts": {"thank_you": "One"}})).json()["version"] == 1
    assert (await design(client, auth_headers, internship, {"texts": {"thank_you": "One"}})).json()["version"] == 1  # unchanged: no new version
    assert (await design(client, auth_headers, internship, {"texts": {"thank_you": "Two"}})).json()["version"] == 2
    versions = (await db_session.execute(select(ReceiptDesignVersion.version, ReceiptDesignVersion.design).order_by(ReceiptDesignVersion.version))).all()
    assert [v for v, _ in versions] == [1, 2] and versions[0][1]["texts"]["thank_you"] == "One"
    stale = await client.put(f"{rd(internship)}/design", json={"scope": "internship", "design": {"texts": {"thank_you": "Three"}}, "base_version": 1}, headers=auth_headers)
    assert stale.status_code == 409
    ok = await client.put(f"{rd(internship)}/design", json={"scope": "internship", "design": {"texts": {"thank_you": "Three"}}, "base_version": 2}, headers=auth_headers)
    assert ok.json()["version"] == 3


@pytest.mark.parametrize(
    "bad",
    [{"branding": {"brand_color": "#FFFF99"}}, {"branding": {"brand_color": "red"}}, {"texts": {"footer": "x" * 501}}, {"nonsense": True}, {"sections": {"amount": False}}],
)
async def test_an_invalid_design_is_refused_and_nothing_is_stored(client, auth_headers, db_session, organization, bad):
    internship, _ = await world(db_session, organization)
    r = await client.put(f"{rd(internship)}/design", json={"scope": "internship", "design": bad}, headers=auth_headers)
    assert r.status_code in (400, 422)
    assert (await counts(db_session))["designs"] == 0


async def test_templates_are_reusable_unique_and_never_cross_organizations(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    internship, _ = await world(db_session, organization)
    created = await client.post(f"{rd(internship)}/templates", json={"name": "Teal", "design": {"branding": {"brand_color": "#0F766E"}}}, headers=auth_headers)
    assert created.status_code == 201
    template = created.json()["id"]
    assert (await client.post(f"{rd(internship)}/templates", json={"name": "Teal", "design": {}}, headers=auth_headers)).status_code == 409
    assert (await client.post(f"{rd(internship)}/templates", json={"name": "Bad", "design": {"branding": {"brand_color": "#FFFF99"}}}, headers=auth_headers)).status_code in (400, 422)
    assert [t["name"] for t in (await client.get(rd(internship), headers=auth_headers)).json()["templates"]] == ["Teal"]
    applied = await client.post(f"{rd(internship)}/templates/{template}/apply", json={"scope": "internship"}, headers=auth_headers)
    assert applied.status_code == 200
    assert (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["design"]["branding"]["brand_color"] == "#0F766E"
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    theirs, _ = await world(db_session, other, n=1)
    outsider = await admin_headers(db_session, other, permissions=MANAGER)
    assert (await client.post(f"{rd(theirs)}/templates/{template}/apply", json={"scope": "internship"}, headers=outsider)).status_code == 404
    assert (await client.delete(f"{rd(internship)}/templates/{template}", headers=auth_headers)).status_code == 200
    assert (await client.get(rd(internship), headers=auth_headers)).json()["templates"] == []
    assert (await client.post(f"{rd(internship)}/templates/{template}/apply", json={"scope": "internship"}, headers=auth_headers)).status_code == 404  # archived


# ------------------------------------------------------------------ images


async def test_a_logo_is_validated_normalized_stored_privately_and_can_be_used_by_a_design(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    r = await upload(client, auth_headers, internship, data=png(1800, 700))
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["kind"] == "logo" and max(asset["width_px"], asset["height_px"]) <= 900
    stored = (await db_session.execute(select(ReceiptAsset).options(undefer(ReceiptAsset.data)))).scalar_one()
    assert stored.content_type == "image/png" and stored.data.startswith(b"\x89PNG") and stored.sha256 == hashlib.sha256(stored.data).hexdigest()
    image = await client.get(f"{rd(internship)}/assets/{asset['id']}/image", headers=auth_headers)
    assert image.status_code == 200 and image.headers["content-type"] == "image/png" and image.headers["cache-control"] == "private, no-store"
    assert (await client.get(f"{rd(internship)}/assets/{asset['id']}/image")).status_code in (401, 403)  # no public link
    await design(client, auth_headers, internship, {"logo": {"asset_id": asset["id"], "width_mm": 30}})
    assert (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["design"]["logo"]["asset_id"] == asset["id"]
    # an image a saved design uses cannot be removed from under it
    assert (await client.delete(f"{rd(internship)}/assets/{asset['id']}", headers=auth_headers)).status_code == 409
    await design(client, auth_headers, internship, {})
    assert (await client.delete(f"{rd(internship)}/assets/{asset['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{rd(internship)}/assets/{asset['id']}/image", headers=auth_headers)).status_code == 404
    assert (await db_session.execute(select(func.count(ReceiptAsset.id)))).scalar_one() == 1  # archived, never erased: documents can be traced to it


@pytest.mark.parametrize(
    "name, data, ctype",
    [
        pytest.param("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "image/svg+xml", id="svg"),
        pytest.param("logo.png", b"not an image at all", "image/png", id="not-an-image"),
        pytest.param("logo.png", bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10]) + b"fake", "image/png", id="fake-png"),
        pytest.param("logo.pdf", b"%PDF-1.4 hello", "application/pdf", id="pdf"),
        pytest.param("logo.png", b"0" * (2 * 1024 * 1024 + 10), "image/png", id="too-big"),
        pytest.param("logo.png", b"", "image/png", id="empty"),
    ],
)
async def test_unsafe_or_unusable_uploads_are_refused(client, auth_headers, db_session, organization, name, data, ctype):
    internship, _ = await world(db_session, organization)
    r = await upload(client, auth_headers, internship, data=data, name=name, ctype=ctype)
    assert r.status_code in (400, 422), r.text
    assert (await db_session.execute(select(func.count(ReceiptAsset.id)))).scalar_one() == 0


async def test_a_design_can_only_use_this_organizations_own_images_of_the_right_kind(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    internship, _ = await world(db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    theirs, _ = await world(db_session, other, n=1)
    outsider = await admin_headers(db_session, other, permissions=MANAGER)
    foreign = (await upload(client, outsider, theirs)).json()["id"]
    assert (await client.get(f"{rd(internship)}/assets/{foreign}/image", headers=auth_headers)).status_code == 404
    await design(client, auth_headers, internship, {"logo": {"asset_id": foreign}}, expect=422)
    mine = (await upload(client, auth_headers, internship, kind="signature")).json()["id"]
    await design(client, auth_headers, internship, {"logo": {"asset_id": mine}}, expect=422)  # a signature is not a logo
    await design(client, auth_headers, internship, {"signature": {"asset_id": mine, "show": True}})
    # a missing image id is refused too
    await design(client, auth_headers, internship, {"logo": {"asset_id": str(uuid.uuid4())}}, expect=422)


# ------------------------------------------------------------------ permissions and isolation


async def test_the_designer_needs_a_finance_permission_and_changing_anything_needs_finance_manage(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    nobody = await admin_headers(db_session, organization, permissions=NO_FINANCE)
    viewer = await admin_headers(db_session, organization, permissions=VIEWER)
    manager = await admin_headers(db_session, organization, permissions=MANAGER)
    assert (await client.get(rd(internship))).status_code in (401, 403)
    assert (await client.get(rd(internship), headers=nobody)).status_code == 403
    assert (await client.post(f"{rd(internship)}/preview", json={}, headers=nobody)).status_code == 403
    assert (await client.get(f"{BASE}/{internship.id}/receipts", headers=nobody)).status_code == 403
    assert (await client.get(rd(internship), headers=viewer)).json()["can_edit"] is False
    assert (await client.post(f"{rd(internship)}/preview", json={}, headers=viewer)).status_code == 200
    assert (await client.get(f"{BASE}/{internship.id}/receipts", headers=viewer)).status_code == 200
    for call in (
        client.put(f"{rd(internship)}/design", json={"scope": "internship", "design": {}}, headers=viewer),
        client.delete(f"{rd(internship)}/design", headers=viewer),
        client.post(f"{rd(internship)}/templates", json={"name": "T", "design": {}}, headers=viewer),
        upload(client, viewer, internship),
    ):
        assert (await call).status_code == 403
    assert (await design(client, manager, internship, {"texts": {"thank_you": "Hello"}})).json()["version"] == 1
    assert (await upload(client, manager, internship)).status_code == 201


async def test_nothing_crosses_organizations(client, auth_headers, db_session, organization, storage):
    from modules.organizations.repository import OrganizationRepository

    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    document = await only_document(db_session)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    outsider = await admin_headers(db_session, other, permissions=MANAGER)
    for path in ("", "/receipts", f"/receipts/{document.id}/pdf", f"/receipts/{document.id}/history"):
        url = f"{BASE}/{internship.id}{path}" if path else rd(internship)
        assert (await client.get(url, headers=outsider)).status_code == 404, path
    assert (await client.put(f"{rd(internship)}/design", json={"scope": "organization", "design": {}}, headers=outsider)).status_code == 404
    assert (await client.post(f"{rd(internship)}/preview", json={}, headers=outsider)).status_code == 404
    # and a sibling internship of the same organization does not show this internship's documents
    sibling, _ = await world(db_session, organization, n=1)
    assert (await client.get(f"{BASE}/{sibling.id}/receipts", headers=auth_headers)).json() == {"total": 0, "items": []}
    assert (await client.get(f"{BASE}/{sibling.id}/receipts/{document.id}/pdf", headers=auth_headers)).status_code == 404


# ------------------------------------------------------------------ preview is read-only


async def test_a_preview_changes_nothing_takes_no_number_and_is_marked_as_a_sample(client, auth_headers, db_session, organization, storage, monkeypatch):
    sent = []
    monkeypatch.setattr(financial, "enqueue_email", lambda document_id: sent.append(document_id))
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0, **TAX, _amount="5900.00")
    sent.clear()
    tx = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()
    stored_before = dict(storage.objects)
    before = await counts(db_session)
    for kind in ("receipt", "tax_invoice", "credit_note"):
        r = await client.post(f"{rd(internship)}/preview", json={"kind": kind, "source": "sample", "design": {"texts": {"thank_you": "Draft thanks"}}}, headers=auth_headers)
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.headers["x-page-count"] == "1" and pages_of(r.content) == 1
        assert "SAMPLE - NOT A VALID RECEIPT" in pdf_text(r.content) and "SAMPLE-0001" in pdf_text(r.content) and r.headers["cache-control"] == "private, no-store"
    real = await client.post(f"{rd(internship)}/preview", json={"source": "transaction", "transaction_id": str(tx.id)}, headers=auth_headers)
    assert real.status_code == 200 and "PREVIEW - NOT AN OFFICIAL COPY" in pdf_text(real.content)
    assert "₹ 5,900.00" in pdf_text(real.content) and "Student 0" in pdf_text(real.content) and "PREVIEW" in pdf_text(real.content)  # the real payment's data, marked as a preview
    assert await counts(db_session) == before  # no document, number, payment, event or design written
    assert sent == [] and storage.objects == stored_before  # nothing emailed, nothing stored


async def test_a_preview_needs_a_valid_draft_and_a_confirmed_payment_of_this_internship(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    bad = await client.post(f"{rd(internship)}/preview", json={"design": {"branding": {"brand_color": "#FFFF99"}}}, headers=auth_headers)
    assert bad.status_code in (400, 422)
    assert (await client.post(f"{rd(internship)}/preview", json={"source": "transaction"}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.post(f"{rd(internship)}/preview", json={"source": "transaction", "transaction_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404
    await configure(client, auth_headers, internship)
    token = await ready_to_pay(client, auth_headers, internship, s0)
    await client.post(f"{PUBLIC}/payments/manual", data={"method": "bank_transfer", "reference": "UTR123456789", "paid_on": date.today().isoformat(), "amount": "5000.00"},
                      files={"proof": ("p.png", png(), "image/png")}, headers=tok(token))  # fmt: skip
    claim = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()
    unconfirmed = await client.post(f"{rd(internship)}/preview", json={"source": "transaction", "transaction_id": str(claim.id)}, headers=auth_headers)
    assert unconfirmed.status_code == 409  # a claim awaiting verification has no document to preview
    sibling, _ = await world(db_session, organization, n=1)
    assert (await client.post(f"{rd(sibling)}/preview", json={"source": "transaction", "transaction_id": str(claim.id)}, headers=auth_headers)).status_code == 404


# ------------------------------------------------------------------ automatic issuing uses the saved design


async def test_a_confirmed_payment_gets_one_single_page_receipt_in_the_saved_design_and_it_is_stored_privately(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    logo = (await upload(client, auth_headers, internship)).json()["id"]
    await design(client, auth_headers, internship, {"branding": {"brand_color": "#0F766E", "header_align": "center"}, "logo": {"asset_id": logo}, "texts": {"thank_you": "Thanks from GIR", "footer": "Registered office Hyderabad"}},
                 scope="organization")  # fmt: skip
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    pdf = storage.objects[doc.storage_key]
    assert doc.kind == "receipt" and doc.number.endswith("-000001") and doc.sha256 == hashlib.sha256(pdf).hexdigest()
    assert pages_of(pdf) == 1 and doc.details["render"] == {"engine": "receipt_pdf", "pages": 1}
    text = pdf_text(pdf)
    assert "PAYMENT RECEIPT" in text and doc.number in text and "₹ 5,000.00" in text and "Thanks from GIR" in text and "Registered office Hyderabad" in text
    assert "SAMPLE" not in text and "PREVIEW" not in text  # an official document carries no preview mark
    used = doc.details["design"]
    assert used["source"] == "organization" and used["version"] == 1 and used["design"]["branding"]["brand_color"] == "#0F766E" and list(used["assets"]) == ["logo"]
    assert used["assets"]["logo"]["sha256"] == (await db_session.execute(select(ReceiptAsset.sha256))).scalar_one()
    assert doc.storage_key.startswith(f"onboarding/{organization.id}/") and "http" not in doc.storage_key  # private storage, no public URL
    events = (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.event == "document_issued"))).scalars().all()
    assert len(events) == 1 and events[0].detail["design"] == "organization" and events[0].detail["pages"] == 1


async def test_a_tax_invoice_keeps_the_existing_gst_rules_and_a_credit_note_the_existing_refund_rules(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)
    token, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00", **TAX)
    invoice = await only_document(db_session)
    assert invoice.kind == "tax_invoice" and invoice.details["tax"] == {"label": "GST", "rate_percent": "18", "taxable": "5000.00", "tax": "900.00"}
    text = pdf_text(storage.objects[invoice.storage_key])
    assert "TAX INVOICE" in text and "GSTIN: 36ABCDE1234F1Z5" in text and "GST @ 18%" in text and "₹ 5,000.00" in text and "₹ 900.00" in text and "₹ 5,900.00" in text
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/refund", json={"amount": "2000", "reason": "Partial withdrawal"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    decided = await client.post(f"{BASE}/{internship.id}/onboarding-flow/refunds/{r.json()['id']}/decide", json={"approve": True, "reference": "NEFT-REF-1"}, headers=auth_headers)
    assert decided.json()["status"] == "confirmed"
    note = (await db_session.execute(select(FinancialDocument).where(FinancialDocument.kind == "credit_note"))).scalar_one()
    credit = storage.objects[note.storage_key]
    assert pages_of(credit) == 1 and note.number.startswith("RCPT-CN-") and note.amount == Decimal("2000.00") and note.details["design"]["source"] == "organization"
    text = pdf_text(credit)
    assert "CREDIT NOTE" in text and "Total refunded" in text and f"Receipt {invoice.number}" in text and "₹ 2,000.00" in text and "REFUNDED" in text
    assert (await db_session.get(PaymentTransaction, tx.id)).amount == Decimal("5900.00")  # the payment itself is never touched


async def test_the_mobile_number_is_in_the_document_only_when_the_design_shows_it(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    first = await only_document(db_session)
    assert "phone" not in first.details["student"] and "9876543210" not in pdf_text(storage.objects[first.storage_key])
    await design(client, auth_headers, internship, {"sections": {"student_mobile": True}})
    await paid_by_bank(client, auth_headers, db_session, internship, s1)
    second = await only_document(db_session)
    assert second.id != first.id and second.details["student"]["phone"] == "9876543210" and "Mobile: 9876543210" in pdf_text(storage.objects[second.storage_key])


# ------------------------------------------------------------------ duplicates, failures, pending


async def test_a_duplicate_cashfree_notification_never_makes_a_second_document(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, payment_id=88))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"
    for _ in range(3):
        again = await client.post(HOOK, content=raw, headers=headers)
        assert again.status_code == 200 and again.json()["outcome"] == "duplicate"
    # the same payment reported again with a new signature timestamp is also recognised
    raw2, headers2 = signed(payment_event(order_id, payment_id=88))
    assert (await client.post(HOOK, content=raw2, headers=headers2)).status_code == 200
    docs = (await db_session.execute(select(FinancialDocument))).scalars().all()
    assert len(docs) == 1 and docs[0].number.endswith("-000001") and docs[0].details["render"]["engine"] == "receipt_pdf" and pages_of(storage.objects[docs[0].storage_key]) == 1
    assert (await db_session.execute(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.kind == "payment"))).scalar_one() == 1
    assert (await db_session.execute(select(OnboardingCounter.last_value).where(OnboardingCounter.series == "receipt"))).scalar_one() == 1  # one number used


async def test_calling_issue_again_returns_the_same_document_and_takes_no_new_number(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    _, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    before = await counts(db_session)
    for _ in range(3):
        assert (await financial.issue(db_session, tx)).id == doc.id
    assert await counts(db_session) == before


async def test_failed_dropped_pending_and_unverified_payments_get_no_document(client, auth_headers, db_session, organization, storage, gateway):
    internship, (s0, s1) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    dropped = payment_event(order_id, status="USER_DROPPED", payment_id=61)
    dropped["type"] = "PAYMENT_USER_DROPPED_WEBHOOK"
    for body in (dropped, payment_event(order_id, status="FAILED", payment_id=62)):
        raw, headers = signed(body)
        await client.post(HOOK, content=raw, headers=headers)
    gateway.payments[order_id] = [{"cf_payment_id": "63", "payment_status": "PENDING", "payment_amount": 5000, "payment_currency": "INR"}]
    assert (await client.post(f"{PUBLIC}/payments/refresh", headers=tok(token))).json()["outcome"] == "pending"
    forged_raw, forged_headers = signed(payment_event(order_id, payment_id=64), secret="not-the-secret")
    await client.post(HOOK, content=forged_raw, headers=forged_headers)
    # a bank claim waiting for finance is not a payment either
    await configure(client, auth_headers, internship)
    other = await ready_to_pay(client, auth_headers, internship, s1)
    await client.post(f"{PUBLIC}/payments/manual", data={"method": "bank_transfer", "reference": "UTR999888777", "paid_on": date.today().isoformat(), "amount": "5000.00"},
                      files={"proof": ("p.png", png(), "image/png")}, headers=tok(other))  # fmt: skip
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar_one() == 0
    claim = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.status == "awaiting_verification"))).scalar_one()
    assert await financial.issue(db_session, claim) is None  # not confirmed: nothing to document
    rejected = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{claim.id}/verify", json={"approve": False, "note": "Not received"}, headers=auth_headers)
    assert rejected.status_code == 200 and (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar_one() == 0
    assert (await db_session.execute(select(OnboardingCounter.last_value).where(OnboardingCounter.series == "receipt"))).first() is None  # no number was used


async def test_a_manually_recorded_payment_is_documented_once_when_finance_confirms_it(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    assert doc.details["method"] == "Bank transfer" and doc.details["transaction_reference"].startswith("UTR") and "Online" not in pdf_text(storage.objects[doc.storage_key])
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar_one() == 1


async def test_a_design_or_rendering_problem_never_stops_a_confirmed_payment_from_getting_its_document(client, auth_headers, db_session, organization, storage, monkeypatch):
    from modules.internship_onboarding import receipt_pdf

    def broken(*args, **kwargs):
        raise RuntimeError("renderer is broken")

    monkeypatch.setattr(receipt_pdf, "build_receipt_pdf", broken)
    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)  # a design is saved, so the designer's renderer IS tried, and fails
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    assert doc.number.endswith("-000001") and doc.details["render"]["engine"] == "legacy" and "design" not in doc.details
    pdf = storage.objects[doc.storage_key]
    assert pdf.startswith(b"%PDF") and doc.sha256 == hashlib.sha256(pdf).hexdigest() and "Payment Receipt" in pdf_text(pdf)
    tx = (await db_session.execute(select(PaymentTransaction))).scalar_one()
    assert tx.status == "confirmed"


async def test_a_stored_design_that_no_longer_validates_falls_back_to_the_built_in_one(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await design(client, auth_headers, internship, {"texts": {"thank_you": "Fine"}})
    record = (await db_session.execute(select(ReceiptDesignRecord))).scalar_one()
    record.design = {"branding": {"brand_color": "not a colour"}}
    await db_session.flush()
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    assert doc.details["render"]["engine"] == "receipt_pdf" and doc.details["design"]["design"]["branding"]["brand_color"] == "#1F3A5F"


# ------------------------------------------------------------------ issued documents are immutable


async def test_changing_the_design_only_affects_documents_issued_afterwards(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await design(client, auth_headers, internship, {"texts": {"thank_you": "First wording"}})
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    first = await only_document(db_session)
    snapshot = (first.storage_key, storage.objects[first.storage_key], first.sha256, json.dumps(first.details, sort_keys=True), first.number, first.amount, first.issued_at)
    await design(client, auth_headers, internship, {"texts": {"thank_you": "Second wording"}, "branding": {"brand_color": "#7C2D12"}})
    await design(client, auth_headers, internship, {}, scope="organization")
    await client.delete(f"{rd(internship)}/design?scope=internship", headers=auth_headers)
    await db_session.refresh(first)
    assert (first.storage_key, storage.objects[first.storage_key], first.sha256, json.dumps(first.details, sort_keys=True), first.number, first.amount, first.issued_at) == snapshot
    served = await client.get(f"{BASE}/{internship.id}/receipts/{first.id}/pdf", headers=auth_headers)
    assert served.status_code == 200 and served.content == snapshot[1] and "First wording" in pdf_text(served.content)  # exactly as originally issued
    await design(client, auth_headers, internship, {"texts": {"thank_you": "Third wording"}})
    await paid_by_bank(client, auth_headers, db_session, internship, s1)
    second = await only_document(db_session)
    assert second.id != first.id and second.number.endswith("-000002") and "Third wording" in pdf_text(storage.objects[second.storage_key])
    assert second.details["design"]["version"] == 1 and first.details["design"]["design"]["texts"]["thank_you"] == "First wording"


async def test_the_database_refuses_any_change_to_an_issued_document_but_allows_email_delivery_updates(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    changes = {
        "amount": Decimal("1.00"), "number": "RCPT-2026-999999", "kind": "credit_note", "currency": "USD", "sha256": "0" * 64, "storage_key": "elsewhere.pdf",
        "details": {"tampered": True}, "issued_at": doc.issued_at + timedelta(days=1), "transaction_id": uuid.uuid4(),
    }  # fmt: skip
    for column, value in changes.items():
        with pytest.raises(DBAPIError, match="cannot be changed"):
            async with db_session.begin_nested():
                await db_session.execute(update(FinancialDocument).where(FinancialDocument.id == doc.id).values({column: value}))
    # delivery bookkeeping is not part of what was issued
    doc.email_status, doc.email_attempts, doc.emailed_at = "sent", 1, datetime.now(timezone.utc)
    await db_session.flush()
    await db_session.refresh(doc)
    assert doc.email_status == "sent" and doc.amount == Decimal("5000.00") and doc.details["design"]["source"] == "organization"


async def test_there_is_no_endpoint_that_regenerates_or_replaces_an_issued_document(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    stored = storage.objects[doc.storage_key]
    base = f"{BASE}/{internship.id}"
    for method, path in (("post", f"/receipts/{doc.id}/regenerate"), ("put", f"/receipts/{doc.id}"), ("patch", f"/receipts/{doc.id}"), ("delete", f"/receipts/{doc.id}"),
                         ("put", f"/receipts/{doc.id}/pdf"), ("post", "/receipts"), ("post", f"/onboarding-flow/financial-documents/{doc.id}/regenerate")):  # fmt: skip
        assert (await getattr(client, method)(base + path, headers=auth_headers)).status_code in (404, 405, 422), (method, path)
    await db_session.refresh(doc)
    assert storage.objects[doc.storage_key] == stored and (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar_one() == 1


# ------------------------------------------------------------------ generated receipts


async def test_generated_receipts_can_be_listed_searched_filtered_viewed_and_traced(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)
    _, tx0 = await paid_by_bank(client, auth_headers, db_session, internship, s0, **TAX, _amount="5900.00")
    await paid_by_bank(client, auth_headers, db_session, internship, s1, **TAX, _amount="5900.00")
    first = (await db_session.execute(select(FinancialDocument).order_by(FinancialDocument.number))).scalars().all()[0]
    refund = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx0.id}/refund", json={"amount": "1000", "reason": "Goodwill"}, headers=auth_headers)
    await client.post(f"{BASE}/{internship.id}/onboarding-flow/refunds/{refund.json()['id']}/decide", json={"approve": True, "reference": "NEFT-1"}, headers=auth_headers)
    url = f"{BASE}/{internship.id}/receipts"
    everything = (await client.get(url, headers=auth_headers)).json()
    assert everything["total"] == 3 and {i["kind"] for i in everything["items"]} == {"tax_invoice", "credit_note"}
    row = next(i for i in everything["items"] if i["number"] == first.number)
    assert row["student"] == "Student 0" and row["internship"] == "Cloud Internship 2026" and row["amount"] == "5900.00" and row["email_status"] in ("pending", "none", "sent", "failed")
    assert row["transaction_id"] == str(tx0.id) and row["paid_on"] == date.today().isoformat() and row["pages"] == 1 and row["engine"] == "receipt_pdf" and row["design_source"] == "organization"
    assert (await client.get(url, params={"q": "student 1"}, headers=auth_headers)).json()["total"] == 1
    assert (await client.get(url, params={"q": first.number}, headers=auth_headers)).json()["total"] == 1
    assert (await client.get(url, params={"q": row["application"]}, headers=auth_headers)).json()["total"] >= 1
    assert (await client.get(url, params={"q": "UTR"}, headers=auth_headers)).json()["total"] == 2  # the two payments (the refund has a NEFT reference)
    assert (await client.get(url, params={"q": "%"}, headers=auth_headers)).json()["total"] == 0  # wildcards are plain characters
    assert (await client.get(url, params={"q": "_"}, headers=auth_headers)).json()["total"] == 0
    assert (await client.get(url, params={"kind": "credit_note"}, headers=auth_headers)).json()["total"] == 1
    assert (await client.get(url, params={"kind": "tax_invoice"}, headers=auth_headers)).json()["total"] == 2
    assert (await client.get(url, params={"issued_from": (date.today() + timedelta(days=2)).isoformat()}, headers=auth_headers)).json()["total"] == 0
    assert (await client.get(url, params={"issued_from": (date.today() - timedelta(days=1)).isoformat(), "issued_to": (date.today() + timedelta(days=1)).isoformat()}, headers=auth_headers)).json()["total"] == 3
    assert (await client.get(url, params={"limit": 2}, headers=auth_headers)).json()["total"] == 3 and len((await client.get(url, params={"limit": 2}, headers=auth_headers)).json()["items"]) == 2
    assert len((await client.get(url, params={"limit": 2, "offset": 2}, headers=auth_headers)).json()["items"]) == 1
    assert (await client.get(url, params={"limit": 1000}, headers=auth_headers)).status_code == 422
    assert (await client.get(url, params={"kind": "nonsense"}, headers=auth_headers)).status_code == 422

    view = await client.get(f"{url}/{first.id}/pdf", headers=auth_headers)
    assert view.status_code == 200 and view.headers["content-type"] == "application/pdf" and view.headers["content-disposition"].startswith("inline")
    assert view.content == storage.objects[first.storage_key] and view.headers["cache-control"] == "private, no-store" and view.headers["x-content-type-options"] == "nosniff"
    download = await client.get(f"{url}/{first.id}/pdf", params={"download": "true"}, headers=auth_headers)
    assert download.headers["content-disposition"] == f'attachment; filename="{first.number}.pdf"'

    history = (await client.get(f"{url}/{first.id}/history", headers=auth_headers)).json()
    assert history["document"]["number"] == first.number and history["document"]["sha256"] == first.sha256
    assert history["transaction"]["id"] == str(tx0.id) and history["transaction"]["method"] == "bank_transfer" and history["transaction"]["status"] == "confirmed"
    assert history["design"]["source"] == "organization" and history["design"]["pages"] == 1 and history["design"]["engine"] == "receipt_pdf"
    assert [e["event"] for e in history["events"]] == ["document_issued"] and history["events"][0]["detail"]["number"] == first.number
    assert (await client.get(f"{url}/{uuid.uuid4()}/pdf", headers=auth_headers)).status_code == 404


async def test_a_stored_file_that_no_longer_matches_its_checksum_is_never_served_as_the_document(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    storage.objects[doc.storage_key] = storage.objects[doc.storage_key] + b"\n% tampered"
    r = await client.get(f"{BASE}/{internship.id}/receipts/{doc.id}/pdf", headers=auth_headers)
    assert r.status_code == 409 and "checksum" in r.text


# ------------------------------------------------------------------ documents issued before the designer existed


async def test_a_document_issued_before_the_designer_existed_still_lists_downloads_and_traces(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    _, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    current = await only_document(db_session)
    legacy_details = {k: v for k, v in current.details.items() if k not in ("design", "render")}  # what the old code wrote
    legacy_pdf = financial.render_pdf("Payment Receipt", "RCPT-2026-000777", {**legacy_details, "issued_on": "2026-10-30"})
    key = f"onboarding/{organization.id}/legacy/RCPT-2026-000777-abcd1234.pdf"
    storage.objects[key] = legacy_pdf
    await db_session.delete(current)  # (the old document stands in for it: deleting is allowed, editing is not)
    await db_session.flush()
    db_session.add(FinancialDocument(
        organization_id=organization.id, application_id=current.application_id, transaction_id=tx.id, kind="receipt", number="RCPT-2026-000777", amount=Decimal("5000.00"),
        currency="INR", details=legacy_details, storage_key=key, sha256=hashlib.sha256(legacy_pdf).hexdigest(), issued_at=datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc), email_status="sent",
    ))  # fmt: skip
    await db_session.flush()
    listed = (await client.get(f"{BASE}/{internship.id}/receipts", headers=auth_headers)).json()["items"]
    assert [i["number"] for i in listed] == ["RCPT-2026-000777"] and listed[0]["engine"] == "legacy" and listed[0]["design_source"] is None and listed[0]["pages"] is None
    served = await client.get(f"{BASE}/{internship.id}/receipts/{listed[0]['id']}/pdf", headers=auth_headers)
    assert served.status_code == 200 and served.content == legacy_pdf and "Payment Receipt" in pdf_text(served.content)
    history = (await client.get(f"{BASE}/{internship.id}/receipts/{listed[0]['id']}/history", headers=auth_headers)).json()
    assert history["design"] == {"source": None, "version": None, "assets": None, "engine": "legacy", "pages": None}
    # the existing endpoints that students and finance already use are unchanged
    old = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/financial-documents", headers=auth_headers)).json()
    assert old[0]["number"] == "RCPT-2026-000777"
    assert (await financial.issue(db_session, tx)).number == "RCPT-2026-000777"  # still the one document of this payment
    token = await link(client, auth_headers, internship, s0)
    assert [d["number"] for d in (await client.get(PUBLIC, headers=tok(token))).json()["financial_documents"]] == ["RCPT-2026-000777"]
    assert "exp=300" in (await client.get(f"{PUBLIC}/financial-documents/{listed[0]['id']}", headers=tok(token))).json()["url"]


async def test_the_migration_only_adds_tables_and_a_guard_and_leaves_documents_alone():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "apps/api/alembic/versions/0103_receipt_designer.py").read_text(encoding="utf-8")
    upgrade = source.split("def upgrade")[1].split("def downgrade")[0].lower()
    assert upgrade.count("create_table") + upgrade.count("_base(") >= 3 and "alter_table" not in upgrade and "drop_" not in upgrade and "add_column" not in upgrade
    assert "update internship_financial_documents" not in upgrade and "delete from" not in upgrade


async def test_the_guard_trigger_exists_and_the_receipt_tables_are_in_the_schema(db_session):
    names = {r[0] for r in (await db_session.execute(text("select tgname from pg_trigger where tgrelid = 'internship_financial_documents'::regclass"))).all()}
    assert "trg_internship_financial_documents_immutable" in names
    tables = {r[0] for r in (await db_session.execute(text("select table_name from information_schema.tables where table_name like 'internship_receipt_%'"))).all()}
    assert tables == {"internship_receipt_designs", "internship_receipt_design_versions", "internship_receipt_assets"}


# ------------------------------------------------------------------ the original layout stays in use until a design is saved


def legacy_text(doc: FinancialDocument, storage) -> str:
    return pdf_text(storage.objects[doc.storage_key])


async def test_without_a_saved_design_every_document_type_is_drawn_with_the_original_layout(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    view = (await client.get(rd(internship), headers=auth_headers)).json()["effective"]
    assert view["source"] == "default" and view["layout"] == "legacy"
    token, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00", **TAX)
    invoice = await only_document(db_session)
    assert invoice.kind == "tax_invoice" and invoice.details["render"] == {"engine": "legacy", "pages": 1} and "design" not in invoice.details
    text = legacy_text(invoice, storage)
    assert "Tax Invoice" in text and "INR 5,900.00" in text and "INR 900.00" in text and "\u20b9" not in text  # the original wording and currency style
    assert "TAX INVOICE" not in text and "GSTIN" in text
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/refund", json={"amount": "1000", "reason": "Goodwill"}, headers=auth_headers)
    await client.post(f"{BASE}/{internship.id}/onboarding-flow/refunds/{r.json()['id']}/decide", json={"approve": True, "reference": "NEFT-1"}, headers=auth_headers)
    note = (await db_session.execute(select(FinancialDocument).where(FinancialDocument.kind == "credit_note"))).scalar_one()
    assert note.details["render"]["engine"] == "legacy" and "Credit Note" in legacy_text(note, storage) and "INR 1,000.00" in legacy_text(note, storage)
    listed = (await client.get(f"{BASE}/{internship.id}/receipts", headers=auth_headers)).json()["items"]
    assert {i["engine"] for i in listed} == {"legacy"} and {i["design_source"] for i in listed} == {None}
    assert (await db_session.execute(select(func.count(ReceiptDesignRecord.id)))).scalar_one() == 0  # nothing was saved on anyone's behalf


async def test_the_original_layout_is_byte_for_byte_what_the_original_renderer_draws(client, auth_headers, db_session, organization, storage, monkeypatch):
    """The same facts through the original renderer, and through the issuing path with no design saved, give the same text and layout."""
    from modules.internship_onboarding import receipt_pdf

    called = []
    monkeypatch.setattr(receipt_pdf, "build_receipt_pdf", lambda *a, **k: called.append(1))
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    assert called == []  # the designer's renderer is not even asked
    again = financial.render_pdf(financial.TITLES[doc.kind], doc.number, doc.details)
    one, two = PdfReader(io.BytesIO(storage.objects[doc.storage_key])), PdfReader(io.BytesIO(again))
    assert [p.extract_text() for p in one.pages] == [p.extract_text() for p in two.pages]
    assert [tuple(p.mediabox) for p in one.pages] == [tuple(p.mediabox) for p in two.pages]


async def test_saving_a_design_switches_new_documents_only_and_resetting_returns_them_to_the_original_layout(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1, s2) = await world(db_session, organization, n=3)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    before = await only_document(db_session)
    kept = (storage.objects[before.storage_key], before.sha256, json.dumps(before.details, sort_keys=True), before.number)
    assert before.details["render"]["engine"] == "legacy"

    await use_designer(client, auth_headers, internship, data={"texts": {"thank_you": "Designer thanks"}})  # the explicit step
    assert (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["layout"] == "designer"
    await paid_by_bank(client, auth_headers, db_session, internship, s1)
    during = await only_document(db_session)
    assert during.id != before.id and during.number.endswith("-000002") and during.details["render"]["engine"] == "receipt_pdf" and "Designer thanks" in legacy_text(during, storage)

    assert (await client.delete(f"{rd(internship)}/design?scope=organization", headers=auth_headers)).status_code == 200
    assert (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["layout"] == "legacy"
    await paid_by_bank(client, auth_headers, db_session, internship, s2)
    after = await only_document(db_session)
    assert after.number.endswith("-000003") and after.details["render"]["engine"] == "legacy"  # numbering carried on across the switches

    for doc, expected in ((before, kept),):
        await db_session.refresh(doc)
        assert (storage.objects[doc.storage_key], doc.sha256, json.dumps(doc.details, sort_keys=True), doc.number) == expected  # never changed
    await db_session.refresh(during)
    assert during.details["render"]["engine"] == "receipt_pdf" and "Designer thanks" in legacy_text(during, storage)


async def test_an_organization_design_covers_its_internships_and_an_internship_design_takes_precedence(client, auth_headers, db_session, organization, storage):
    one, (a0, a1) = await world(db_session, organization)
    two, (b0, b1) = await world(db_session, organization)
    await use_designer(client, auth_headers, one, scope="organization", data={"texts": {"thank_you": "Organization wording"}})
    await use_designer(client, auth_headers, two, scope="internship", data={"texts": {"thank_you": "Own wording"}})
    for internship, student in ((one, a0), (two, b0)):
        await paid_by_bank(client, auth_headers, db_session, internship, student)
    from modules.internship_onboarding.models import OnboardingApplication

    rows = (await db_session.execute(select(FinancialDocument, OnboardingApplication.internship_id).join(OnboardingApplication, OnboardingApplication.id == FinancialDocument.application_id))).all()
    by_internship = {internship_id: d for d, internship_id in rows}  # (both internships share a title, so documents are told apart by their application)
    first, second = by_internship[one.id], by_internship[two.id]
    assert first.details["design"]["source"] == "organization" and "Organization wording" in legacy_text(first, storage)
    assert second.details["design"]["source"] == "internship" and "Own wording" in legacy_text(second, storage) and "Organization wording" not in legacy_text(second, storage)
    # a third internship of the organization, with no design of its own, follows the organization's
    three, (c0,) = await world(db_session, organization, n=1)
    await paid_by_bank(client, auth_headers, db_session, three, c0)
    third = [d for d in (await db_session.execute(select(FinancialDocument).order_by(FinancialDocument.issued_at))).scalars().all() if d.id not in (first.id, second.id)][-1]
    assert third.details["design"]["source"] == "organization"
    # removing the internship's own design returns it to the organization's design (not to the original layout)
    await client.delete(f"{rd(two)}/design?scope=internship", headers=auth_headers)
    assert (await client.get(rd(two), headers=auth_headers)).json()["effective"]["source"] == "organization"


async def test_a_designer_failure_falls_back_to_the_original_layout_and_a_default_organization_never_reaches_the_designer(client, auth_headers, db_session, organization, storage, monkeypatch):
    from modules.internship_onboarding import receipt_pdf

    attempts = []

    def broken(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("designer renderer failed")

    monkeypatch.setattr(receipt_pdf, "build_receipt_pdf", broken)
    internship, (s0, s1) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    assert attempts == []  # nothing saved: not attempted
    await use_designer(client, auth_headers, internship)
    await paid_by_bank(client, auth_headers, db_session, internship, s1)
    assert attempts == [1]  # a design is saved: attempted, failed
    docs = (await db_session.execute(select(FinancialDocument).order_by(FinancialDocument.number))).scalars().all()
    assert [d.details["render"]["engine"] for d in docs] == ["legacy", "legacy"] and docs[1].number.endswith("-000002")
    assert all(storage.objects[d.storage_key].startswith(b"%PDF") for d in docs)
