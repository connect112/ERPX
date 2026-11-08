"""
Financial safety of the Receipt Designer integration, against both renderers (the original layout, used until a design is saved, and the
designer's): the database guard on issued documents does not get in the way of email delivery, tax figures and numbering are the same
whichever renderer draws the document, duplicate Cashfree notifications make one document in either state, and the download paths that
already existed still work for documents drawn by either renderer. Synthetic data only; the gateway and the mail server are fakes.
"""

import io
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from modules.internship_onboarding import financial
from modules.internship_onboarding.models import FinancialDocument, OnboardingCounter, PaymentTransaction
from tests.api.test_internship_onboarding import BASE, PUBLIC, link, storage, tok, world  # noqa: F401
from tests.api.test_internship_onboarding_payments import gateway, online, payment_event, signed  # noqa: F401
from tests.api.test_receipt_designer import TAX, only_document, paid_by_bank, pdf_text, use_designer

pytestmark = pytest.mark.api

HOOK = "/api/v1/public/payments/cashfree/webhook"
IDENTITY = ("organization_id", "application_id", "transaction_id", "kind", "number", "amount", "currency", "details", "storage_key", "sha256", "issued_at")


def identity(doc: FinancialDocument) -> dict:
    return {c: (json.dumps(getattr(doc, c), sort_keys=True) if c == "details" else getattr(doc, c)) for c in IDENTITY}


@pytest.fixture
def mailbox(db_session, monkeypatch):
    """The real ``financial._send`` against the test session, with the mail server replaced by a list."""
    from packages.email.service import email_service

    sent: list[dict] = []
    outcome = {"ok": True}

    @asynccontextmanager
    async def same_session():
        yield db_session
        await db_session.flush()  # what the real context's commit does: the UPDATE reaches the database (and its guard) here

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append({"to": to, "subject": subject, "attachments": attachments})
        return outcome["ok"]

    monkeypatch.setattr(financial, "get_db_context", same_session)
    monkeypatch.setattr(financial, "enqueue_email", lambda document_id: None)
    monkeypatch.setattr(email_service, "send", fake_send)
    return sent, outcome


@pytest.mark.parametrize("designer", [False, True], ids=["original layout", "designer"])
async def test_email_delivery_updates_are_not_blocked_by_the_guard_and_change_nothing_that_was_issued(client, auth_headers, db_session, organization, storage, mailbox, designer):
    sent, outcome = mailbox
    internship, (s0, _) = await world(db_session, organization)
    if designer:
        await use_designer(client, auth_headers, internship)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    issued = identity(doc)
    pdf = storage.objects[doc.storage_key]
    assert doc.email_status == "pending" and doc.email_attempts == 0 and doc.emailed_at is None

    outcome["ok"] = False  # the mail server refuses: the status moves to failed and the attempt is counted
    assert await financial._send(doc.id) is False
    await db_session.refresh(doc)
    assert doc.email_status == "failed" and doc.email_attempts == 1 and doc.emailed_at is None

    outcome["ok"] = True  # a retry succeeds
    assert await financial._send(doc.id) is True
    await db_session.refresh(doc)
    assert doc.email_status == "sent" and doc.email_attempts == 2 and doc.emailed_at is not None
    assert len(sent) == 2 and sent[-1]["to"].endswith("@example.com")
    attached = sent[-1]["attachments"][0]
    assert attached.filename == f"{doc.number}.pdf" and attached.content == pdf and attached.mime_type == "application/pdf"  # the stored file, as issued

    assert await financial._send(doc.id) is True  # already sent: nothing is sent twice
    assert len(sent) == 2

    # staff resend: back to pending through the real endpoint (an ordinary UPDATE of the delivery field)
    r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/financial-documents/{doc.id}/resend", headers=auth_headers)
    assert r.status_code == 202
    await db_session.refresh(doc)
    assert doc.email_status == "pending"
    assert identity(doc) == issued and storage.objects[doc.storage_key] == pdf  # nothing that was issued moved


async def test_the_guard_still_refuses_changes_that_are_not_delivery_bookkeeping(client, auth_headers, db_session, organization, storage):
    internship, (s0, _) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    # delivery fields together with an issued field in one statement are still refused
    with pytest.raises(DBAPIError, match="cannot be changed"):
        async with db_session.begin_nested():
            await db_session.execute(update(FinancialDocument).where(FinancialDocument.id == doc.id).values(email_status="sent", amount=Decimal("1.00")))
    await db_session.refresh(doc)
    assert doc.amount == Decimal("5000.00") and doc.email_status == "pending"
    # and an update that changes nothing is fine
    await db_session.execute(update(FinancialDocument).where(FinancialDocument.id == doc.id).values(amount=doc.amount, details=doc.details, number=doc.number))


async def test_tax_figures_and_amounts_are_the_same_whichever_renderer_draws_the_document(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    await paid_by_bank(client, auth_headers, db_session, internship, s0, _amount="5900.00", **TAX)
    original = await only_document(db_session)
    await use_designer(client, auth_headers, internship)
    await paid_by_bank(client, auth_headers, db_session, internship, s1, _amount="5900.00", **TAX)
    designed = await only_document(db_session)
    assert original.details["render"]["engine"] == "legacy" and designed.details["render"]["engine"] == "receipt_pdf"
    expected = {"label": "GST", "rate_percent": "18", "taxable": "5000.00", "tax": "900.00"}
    assert original.details["tax"] == designed.details["tax"] == expected
    assert (original.kind, original.amount, original.currency) == (designed.kind, designed.amount, designed.currency) == ("tax_invoice", Decimal("5900.00"), "INR")
    text_original, text_designed = " ".join(pdf_text(storage.objects[original.storage_key]).split()), " ".join(pdf_text(storage.objects[designed.storage_key]).split())
    for figure in ("5,000.00", "900.00", "5,900.00"):  # the same three figures appear in both
        assert figure in text_original and figure in text_designed
    for key in ("issuer", "student", "application_reference", "internship", "description", "method", "currency", "amount", "tax", "against", "footer", "kind"):
        assert key in designed.details and (key in original.details)


async def test_receipt_and_credit_note_numbers_keep_counting_across_a_switch_of_renderer(client, auth_headers, db_session, organization, storage):
    internship, (s0, s1) = await world(db_session, organization)
    _, tx0 = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    first = await only_document(db_session)
    await use_designer(client, auth_headers, internship)
    _, tx1 = await paid_by_bank(client, auth_headers, db_session, internship, s1)
    second = await only_document(db_session)
    assert first.number.endswith("-000001") and second.number.endswith("-000002")
    notes = []
    for tx in (tx0, tx1):
        r = await client.post(f"{BASE}/{internship.id}/onboarding-flow/payments/{tx.id}/refund", json={"amount": "500", "reason": "Goodwill"}, headers=auth_headers)
        assert r.status_code == 201, r.text
        decided = await client.post(f"{BASE}/{internship.id}/onboarding-flow/refunds/{r.json()['id']}/decide", json={"approve": True, "reference": f"NEFT-{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        assert decided.json()["status"] == "confirmed"
        notes.append(await only_document(db_session))
        await use_designer(client, auth_headers, internship, data={"texts": {"thank_you": "x"}}) if tx is tx0 else None
    assert [n.number[-6:] for n in notes] == ["000001", "000002"] and all("-CN-" in n.number for n in notes)
    assert notes[0].details["render"]["engine"] == "receipt_pdf"  # (a design was saved before either refund was decided)
    counters = {(c.series, c.last_value) for c in (await db_session.execute(select(OnboardingCounter))).scalars() if c.series != "application"}
    assert counters == {("receipt", 2), ("credit_note", 2)}
    assert notes[0].details["against"] == f"Receipt {first.number}" and notes[1].details["against"] == f"Receipt {second.number}"


@pytest.mark.parametrize("designer", [False, True], ids=["original layout", "designer"])
async def test_duplicate_cashfree_notifications_make_one_document_in_either_state(client, auth_headers, db_session, organization, storage, gateway, designer):
    internship, (s0, _) = await world(db_session, organization)
    token = await online(client, auth_headers, internship, s0)
    if designer:
        await use_designer(client, auth_headers, internship)
    order_id = (await client.post(f"{PUBLIC}/payments/checkout", headers=tok(token))).json()["order_id"]
    raw, headers = signed(payment_event(order_id, payment_id=77))
    assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "confirmed"
    for _ in range(3):
        assert (await client.post(HOOK, content=raw, headers=headers)).json()["outcome"] == "duplicate"
    docs = (await db_session.execute(select(FinancialDocument))).scalars().all()
    assert len(docs) == 1 and docs[0].details["render"]["engine"] == ("receipt_pdf" if designer else "legacy")
    assert (await db_session.execute(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.kind == "payment"))).scalar_one() == 1
    assert (await db_session.execute(select(OnboardingCounter.last_value).where(OnboardingCounter.series == "receipt"))).scalar_one() == 1


@pytest.mark.parametrize("designer", [False, True], ids=["original layout", "designer"])
async def test_the_download_paths_that_already_existed_work_for_documents_of_either_renderer(client, auth_headers, db_session, organization, storage, designer):
    internship, (s0, s1) = await world(db_session, organization)
    if designer:
        await use_designer(client, auth_headers, internship)
    token, _ = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    doc = await only_document(db_session)
    # the student's own page and signed link
    view = (await client.get(PUBLIC, headers=tok(token))).json()
    assert [d["number"] for d in view["financial_documents"]] == [doc.number]
    url = (await client.get(f"{PUBLIC}/financial-documents/{doc.id}", headers=tok(token))).json()["url"]
    assert doc.storage_key in url and "exp=300" in url
    other = await link(client, auth_headers, internship, s1)
    assert (await client.get(f"{PUBLIC}/financial-documents/{doc.id}", headers=tok(other))).status_code == 404  # another student's document
    # finance's existing list and signed download
    listed = (await client.get(f"{BASE}/{internship.id}/onboarding-flow/financial-documents", headers=auth_headers)).json()
    assert [d["number"] for d in listed] == [doc.number]
    assert doc.storage_key in (await client.get(f"{BASE}/{internship.id}/onboarding-flow/financial-documents/{doc.id}/download", headers=auth_headers)).json()["url"]
    # and the new viewer serves the same stored bytes
    served = await client.get(f"{BASE}/{internship.id}/receipts/{doc.id}/pdf", headers=auth_headers)
    assert served.content == storage.objects[doc.storage_key] and len(PdfReader(io.BytesIO(served.content)).pages) == 1


async def test_a_payment_without_a_document_is_issued_by_the_sweep_with_whichever_layout_is_in_force_at_that_moment(client, auth_headers, db_session, organization, storage, monkeypatch):
    """A document that could not be issued at confirmation time is issued later, never twice, and uses the design saved by then."""
    from modules.internship_onboarding.completion import sweep

    calls = {"n": 0}
    real = financial.issue

    async def failing_once(db, tx):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("storage was down")
        return await real(db, tx)

    monkeypatch.setattr(financial, "issue", failing_once)
    internship, (s0, _) = await world(db_session, organization)
    _, tx = await paid_by_bank(client, auth_headers, db_session, internship, s0)
    assert (await db_session.execute(select(func.count(FinancialDocument.id)))).scalar_one() == 0  # the payment is confirmed, its document is still to come
    assert (await db_session.get(PaymentTransaction, tx.id)).status == "confirmed"
    await use_designer(client, auth_headers, internship)
    await sweep(db_session)
    await sweep(db_session)  # a second sweep finds nothing left to do
    docs = (await db_session.execute(select(FinancialDocument))).scalars().all()
    assert len(docs) == 1 and docs[0].number.endswith("-000001") and docs[0].details["render"]["engine"] == "receipt_pdf"
    assert datetime.now(timezone.utc) >= docs[0].issued_at
