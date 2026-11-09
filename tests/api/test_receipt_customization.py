"""
Customizing the receipt designer: document titles and wording through issuing, sample preview overrides, the issuer's identity through the
existing versioned finance settings, designs saved before these controls existed, and that none of it can change an issued document or
cross organizations. Synthetic data only.
"""

import hashlib
import json
import uuid

import pytest
from sqlalchemy import select

from modules.internship_onboarding.models import FinancialDocument, ReceiptDesignRecord
from tests.api.test_internship_onboarding import BASE, configure, storage, world  # noqa: F401
from tests.api.test_receipt_designer import MANAGER, NO_FINANCE, TAX, VIEWER, counts, design, only_document, paid_by_bank, pdf_text, rd, use_designer
from tests.api.test_storage_manager import admin_headers

pytestmark = pytest.mark.api

LABELS = {"title_receipt": "Fee Receipt", "title_tax_invoice": "GST Tax Invoice", "title_credit_note": "Credit Note (Refund)", "billed_to": "CUSTOMER",
          "total_received": "Amount received", "status_paid": "SETTLED", "status_paid_word": "Settled"}  # fmt: skip


def issuer_url(internship) -> str:
    return f"{rd(internship)}/issuer"


# ------------------------------------------------------------------ titles and wording reach the issued document


async def test_a_saved_wording_is_used_for_new_documents_and_never_changes_one_already_issued(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship, data={"labels": LABELS})
    await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00", **TAX)
    first = await only_document(db_session)
    text = pdf_text(storage.objects[first.storage_key])
    assert first.kind == "tax_invoice" and "GST Tax Invoice" in text and "CUSTOMER" in text and "Amount received" in text and "SETTLED" in text and "PAYMENT RECEIPT" not in text
    assert first.details["design"]["design"]["labels"]["title_tax_invoice"] == "GST Tax Invoice"  # the wording used is kept with the document
    for figure in ("5,000.00", "900.00", "5,900.00"):
        assert figure in text
    stored = (storage.objects[first.storage_key], first.sha256, json.dumps(first.details, sort_keys=True))

    await design(client, auth_headers, internship, {"labels": {**LABELS, "title_tax_invoice": "Tax Invoice (GIR)", "billed_to": "BUYER"}}, scope="organization")
    await paid_by_bank(client, auth_headers, db_session, internship, s1, _amount="5900.00", **TAX)
    second = await only_document(db_session)
    assert "Tax Invoice (GIR)" in pdf_text(storage.objects[second.storage_key]) and "BUYER" in pdf_text(storage.objects[second.storage_key])
    await db_session.refresh(first)
    assert (storage.objects[first.storage_key], first.sha256, json.dumps(first.details, sort_keys=True)) == stored
    served = await client.get(f"{BASE}/{internship.id}/receipts/{first.id}/pdf", headers=auth_headers)
    assert served.content == stored[0] and "GST Tax Invoice" in pdf_text(served.content)


@pytest.mark.parametrize(
    "labels",
    [{"title_tax_invoice": "Bill"}, {"title_credit_note": "Refund slip"}, {"title_receipt": "Tax Invoice"}, {"status_paid": "REFUNDED"}, {"billed_to": ""}],
)
async def test_a_title_that_would_misrepresent_the_document_is_refused_when_saving_and_nothing_is_stored(client, auth_headers, db_session, organization, labels):
    internship, _ = await world(db_session, organization)
    r = await client.put(f"{rd(internship)}/design", json={"scope": "internship", "design": {"labels": labels}}, headers=auth_headers)
    assert r.status_code in (400, 422)
    assert (await counts(db_session))["designs"] == 0


async def test_a_stored_design_with_a_misleading_title_is_not_used_to_draw_a_document(client, auth_headers, db_session, organization, storage):
    """Even if a bad design reached the table by another route, the document is drawn with the safe built-in design."""
    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship, data={"labels": {"title_tax_invoice": "GST Tax Invoice"}})
    record = (await db_session.execute(select(ReceiptDesignRecord))).scalar_one()
    record.design = {**record.design, "labels": {**record.design["labels"], "title_tax_invoice": "Plain bill"}}
    await db_session.flush()
    await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00", **TAX)
    doc = await only_document(db_session)
    text = pdf_text(storage.objects[doc.storage_key])
    assert doc.kind == "tax_invoice" and "TAX INVOICE" in text and "Plain bill" not in text


async def test_a_design_saved_before_the_new_controls_existed_still_issues_with_the_original_wording(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)
    record = (await db_session.execute(select(ReceiptDesignRecord))).scalar_one()
    record.design = {"branding": {"brand_color": "#0F766E", "accent_color": "#E6F4F1", "header_align": "center"}, "texts": {"thank_you": "Thanks", "footer": ""},
                     "sections": {"student_mobile": False}}  # fmt: skip  (what a design saved by the first version looks like)
    await db_session.flush()
    out = (await client.get(rd(internship), headers=auth_headers)).json()["effective"]["design"]
    assert out["labels"]["title_receipt"] == "PAYMENT RECEIPT" and out["style"]["body_size"] == 9 and out["body_order"] == ["details", "items", "thank_you", "signature"]
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    assert doc.details["render"]["engine"] == "receipt_pdf" and "PAYMENT RECEIPT" in pdf_text(storage.objects[doc.storage_key]) and "Thanks" in pdf_text(storage.objects[doc.storage_key])


# ------------------------------------------------------------------ sample overrides are preview-only


async def test_sample_details_change_only_the_preview_and_are_never_stored(client, auth_headers, db_session, organization, storage):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship, **TAX)
    before = await counts(db_session)
    sample = {"customer_name": "Priya Nair", "customer_email": "priya@example.org", "amount": "11800.00", "description": "Advanced SOC analyst cohort",
              "application_reference": "ERPX-INT-2026-777777", "programme": "SOC Cohort 7", "payment_method": "UPI", "transaction_reference": "SAMPLE-UTR-1"}  # fmt: skip
    r = await client.post(f"{rd(internship)}/preview", json={"kind": "tax_invoice", "source": "sample", "sample": sample}, headers=auth_headers)
    assert r.status_code == 200 and r.headers["x-page-count"] == "1"
    text = pdf_text(r.content)
    for shown in ("Priya Nair", "priya@example.org", "Advanced SOC analyst cohort", "ERPX-INT-2026-777777", "SOC Cohort 7", "UPI", "SAMPLE-UTR-1", "SAMPLE - NOT A VALID RECEIPT", "SAMPLE-0001"):
        assert shown in text, shown
    assert "₹ 11,800.00" in text and "₹ 1,800.00" in text and "₹ 10,000.00" in text  # the tax split is recomputed from the sample amount
    assert await counts(db_session) == before  # nothing stored: not a payment, a document, a number or a design


@pytest.mark.parametrize(
    "sample",
    [{"amount": "0"}, {"amount": "-5"}, {"amount": "10000000"}, {"amount": "1.234"}, {"amount": "abc"}, {"customer_name": "x" * 121}, {"customer_name": "a\x00b"}, {"transaction_id": "X"}, {"gst": "0"}],
)
async def test_invalid_sample_details_are_refused(client, auth_headers, db_session, organization, sample):
    internship, _ = await world(db_session, organization)
    r = await client.post(f"{rd(internship)}/preview", json={"source": "sample", "sample": sample}, headers=auth_headers)
    assert r.status_code in (400, 422)


async def test_sample_details_can_never_be_applied_to_a_real_payment(client, auth_headers, db_session, organization, storage):
    from modules.internship_onboarding.models import PaymentTransaction

    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    tx = (await db_session.execute(select(PaymentTransaction).where(PaymentTransaction.kind == "payment"))).scalar_one()
    bad = await client.post(f"{rd(internship)}/preview", json={"source": "transaction", "transaction_id": str(tx.id), "sample": {"amount": "1.00"}}, headers=auth_headers)
    assert bad.status_code in (400, 422)
    ok = await client.post(f"{rd(internship)}/preview", json={"source": "transaction", "transaction_id": str(tx.id), "design": {"labels": LABELS}}, headers=auth_headers)
    text = pdf_text(ok.content)
    assert ok.status_code == 200 and "Fee Receipt" in text and "₹ 5,000.00" in text and "PREVIEW - NOT AN OFFICIAL COPY" in text  # real figures, draft wording


# ------------------------------------------------------------------ the issuer's identity goes through the versioned finance settings


async def test_the_issuer_can_be_changed_through_the_finance_settings_and_only_affects_later_documents(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship)
    await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00", **TAX)
    first = await only_document(db_session)
    kept = (storage.objects[first.storage_key], first.sha256, json.dumps(first.details, sort_keys=True), first.number)
    versions_before = len((await client.get(f"{BASE}/{internship.id}/onboarding-flow/config/versions", headers=auth_headers)).json())

    body = {"legal_name": "Pentrix Cyber Academy Pvt Ltd", "address": "5th Floor, Cyber Towers, Hyderabad 500081", "gstin": "36AAAAA1111A1Z5", "receipt_prefix": "PCA", "footer": "Registered in India."}
    r = await client.put(issuer_url(internship), json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    config = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()["settings"]
    assert {k: config["issuer"][k] for k in body} == body  # the one record of the legal identity is config.issuer
    assert config["fees"]["tax_mode"] == "exclusive" and config["fees"]["base_amount"] == "5000"  # nothing else in the settings moved
    versions = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config/versions", headers=auth_headers)).json()
    assert len(versions) == versions_before + 1  # a new version in the history
    designer = (await client.get(rd(internship), headers=auth_headers)).json()
    assert designer["issuer"]["legal_name"] == "Pentrix Cyber Academy Pvt Ltd" and designer["issuer"]["receipt_prefix"] == "PCA"

    await paid_by_bank(client, auth_headers, db_session, internship, s1, _amount="5900.00", **{"fees": TAX["fees"], "issuer": body})
    second = await only_document(db_session)
    text = pdf_text(storage.objects[second.storage_key])
    assert second.number.startswith("PCA-") and second.number.endswith("-000002") and "Pentrix Cyber Academy Pvt Ltd" in text and "GSTIN: 36AAAAA1111A1Z5" in text
    await db_session.refresh(first)
    assert (storage.objects[first.storage_key], first.sha256, json.dumps(first.details, sort_keys=True), first.number) == kept  # the first one is exactly as issued
    assert "GIR Technologies Pvt Ltd" in pdf_text(kept[0])


@pytest.mark.parametrize(
    "change, message",
    [
        ({"gstin": "NOT-A-GSTIN"}, ""),
        ({"receipt_prefix": "lower"}, ""),
        ({"receipt_prefix": "X"}, ""),
        ({"legal_name": ""}, ""),
    ],
)
async def test_an_invalid_issuer_is_refused_and_the_settings_do_not_change(client, auth_headers, db_session, organization, change, message):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    before = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()
    body = {"legal_name": "GIR Technologies", "address": "", "gstin": None, "receipt_prefix": "RCPT", "footer": "", **change}
    assert (await client.put(issuer_url(internship), json=body, headers=auth_headers)).status_code in (400, 422)
    assert (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()["version"] == before["version"]


async def test_a_gstin_needs_a_tax_treatment_exactly_as_in_the_finance_settings(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship)  # no tax treatment
    body = {"legal_name": "GIR Technologies", "address": "", "gstin": "36AAAAA1111A1Z5", "receipt_prefix": "RCPT", "footer": ""}
    r = await client.put(issuer_url(internship), json=body, headers=auth_headers)
    assert r.status_code in (400, 422) and "tax treatment" in r.text


async def test_only_finance_management_can_change_the_issuer_and_it_stays_inside_the_organization(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    body = {"legal_name": "Changed Name", "address": "", "gstin": None, "receipt_prefix": "RCPT", "footer": ""}
    for perms in (VIEWER, NO_FINANCE):
        headers = await admin_headers(db_session, organization, permissions=perms)
        assert (await client.put(issuer_url(internship), json=body, headers=headers)).status_code == 403
    assert (await client.put(issuer_url(internship))).status_code in (401, 403, 422)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    outsider = await admin_headers(db_session, other, permissions=MANAGER)
    assert (await client.put(issuer_url(internship), json=body, headers=outsider)).status_code == 404
    assert (await client.post(f"{rd(internship)}/preview", json={"sample": {"customer_name": "X"}}, headers=outsider)).status_code == 404
    unchanged = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()["settings"]["issuer"]
    assert unchanged["legal_name"] == "GIR Technologies"
    manager = await admin_headers(db_session, organization, permissions=MANAGER)
    assert (await client.put(issuer_url(internship), json=body, headers=manager)).status_code == 200


async def test_the_issuer_endpoint_accepts_nothing_but_the_five_identity_fields(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    await configure(client, auth_headers, internship)
    body = {"legal_name": "GIR Technologies", "address": "", "gstin": None, "receipt_prefix": "RCPT", "footer": ""}
    for extra in ({"base_amount": "1"}, {"fees": {"base_amount": "1"}}, {"payment_accounts": {}}):
        r = await client.put(issuer_url(internship), json={**body, **extra}, headers=auth_headers)
        assert r.status_code in (200, 422)  # unknown keys are ignored by the request model, never applied
    config = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/config", headers=auth_headers)).json()["settings"]
    assert config["fees"]["base_amount"] == "5000" and config["payment_accounts"]["bank"] is not None


async def test_the_database_still_refuses_any_change_to_an_issued_document_after_all_this(client, auth_headers, db_session, organization, storage):
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError

    internship, (s0, _) = await world(db_session, organization)
    await use_designer(client, auth_headers, internship, data={"labels": LABELS})
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    for column, value in (("details", {"x": 1}), ("sha256", "0" * 64), ("amount", 1)):
        with pytest.raises(DBAPIError, match="cannot be changed"):
            async with db_session.begin_nested():
                await db_session.execute(update(FinancialDocument).where(FinancialDocument.id == doc.id).values({column: value}))
    assert hashlib.sha256(storage.objects[doc.storage_key]).hexdigest() == doc.sha256
