"""
Receipts, tax invoices and credit notes for internship onboarding payments.

* Issued once per confirmed transaction (unique ``transaction_id``): calling ``issue`` again returns the same document.
* Immutable: what it says (parties, numbers, amounts, tax lines) is fixed in ``details`` and in the stored PDF; a
  correction is a credit note for a refund, never an edit.
* A "Tax invoice" only when the internship's issuer settings carry a GSTIN and the fee has a tax treatment; otherwise a
  "Payment receipt". Tax lines come from the fee snapshot the student accepted. Nothing is invented.
* Emailing is separate and retried; a failed email never changes the payment.
"""

import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.fees import q
from modules.internship_onboarding.models import FinancialDocument, OnboardingApplication, PaymentTransaction
from modules.internship_onboarding.service import config_of, event, next_number, now

logger = get_logger(__name__)

TITLES = {"receipt": "Payment Receipt", "tax_invoice": "Tax Invoice", "credit_note": "Credit Note"}
METHODS = {"cashfree": "Online (Cashfree)", "bank_transfer": "Bank transfer", "upi": "UPI", "cash": "Cash", "other": "Other"}


def kind_for(transaction: PaymentTransaction, config: OnboardingConfig) -> str:
    if transaction.kind == "refund":
        return "credit_note"
    return "tax_invoice" if config.issuer.gstin and config.fees.tax_mode != "none" else "receipt"


def tax_lines(amount: Decimal, snapshot: dict | None) -> dict[str, str] | None:
    """Split an amount paid into taxable value and tax by the accepted fee's rate (inclusive of tax)."""
    if not snapshot or snapshot.get("tax_mode", "none") == "none":
        return None
    rate = Decimal(snapshot.get("tax_rate_percent", "0"))
    if rate <= 0:
        return None
    taxable = q(amount * 100 / (100 + rate))
    return {"label": snapshot.get("tax_label", "GST"), "rate_percent": str(rate), "taxable": str(taxable), "tax": str(q(amount - taxable))}


def render_pdf(title: str, number: str, d: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from modules.workshop_exams.certificate_pdf import printable_name

    def safe(text: object) -> str:
        return printable_name(str(text or "")) if text else ""

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"{title} {number}")
    width, height = A4
    left, y = 20 * mm, height - 25 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, y, safe(d["issuer"]["name"]))
    c.setFont("Helvetica", 9)
    for line in [d["issuer"].get("address", ""), f"GSTIN {d['issuer']['gstin']}" if d["issuer"].get("gstin") else ""]:
        if line:
            y -= 5 * mm
            c.drawString(left, y, safe(line)[:110])
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - left, height - 25 * mm, title)
    c.setFont("Helvetica", 10)
    c.drawRightString(width - left, height - 31 * mm, f"No. {number}")
    c.drawRightString(width - left, height - 36 * mm, f"Date {d['issued_on']}")
    y -= 14 * mm
    rows = [
        ("Billed to", safe(d["student"]["name"])),
        ("Email", d["student"]["email"]),
        ("Application", d["application_reference"]),
        ("Programme", safe(d["internship"])),
        ("Payment method", d["method"]),
        ("Transaction reference", d.get("transaction_reference") or "-"),
        ("Payment date", d.get("paid_on") or "-"),
    ]
    if d.get("against"):
        rows.append(("Against", d["against"]))
    for label, value in rows:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#6b7280"))
        c.drawString(left, y, label)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        c.drawString(left + 45 * mm, y, str(value)[:90])
        y -= 6 * mm
    y -= 4 * mm
    c.line(left, y, width - left, y)
    y -= 8 * mm
    currency = d["currency"]

    def amount_row(label: str, value: str, bold: bool = False) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(left, y, label)
        c.drawRightString(width - left, y, f"{currency} {Decimal(value):,.2f}")
        y -= 6 * mm

    amount_row(safe(d["description"]), d["amount"] if not d.get("tax") else d["tax"]["taxable"])
    if d.get("tax"):
        amount_row(f"{d['tax']['label']} @ {d['tax']['rate_percent']}%", d["tax"]["tax"])
    amount_row("Total refunded" if d["kind"] == "credit_note" else "Total received", d["amount"], bold=True)
    y -= 10 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6b7280"))
    for line in [d.get("footer") or "", "This document was issued electronically and needs no signature."]:
        if line:
            c.drawString(left, y, safe(line)[:120])
            y -= 4 * mm
    c.showPage()
    c.save()
    return buffer.getvalue()


async def issue(db: AsyncSession, transaction: PaymentTransaction) -> FinancialDocument | None:
    """The document for a confirmed payment or refund. Idempotent; None for anything else (charges, waivers, claims)."""
    from modules.institutions.models import InstitutionStudent
    from modules.organizations.models import Organization
    from modules.our_internships.models import InternshipSelection, OurInternship
    from packages.storage.client import get_storage_client

    if transaction.status != "confirmed" or transaction.kind not in ("payment", "refund"):
        return None
    existing = (await db.execute(select(FinancialDocument).where(FinancialDocument.transaction_id == transaction.id))).scalar_one_or_none()
    if existing is not None:
        return existing
    application = await db.get(OnboardingApplication, transaction.application_id)
    internship = await db.get(OurInternship, application.internship_id) if application else None
    selection = await db.get(InternshipSelection, application.selection_id) if application else None
    student = await db.get(InstitutionStudent, selection.student_id) if selection else None
    if application is None or internship is None or student is None:
        raise NotFoundError("Payment", transaction.id)
    _, config = await config_of(db, internship)
    org = await db.get(Organization, internship.organization_id)
    kind = kind_for(transaction, config)
    issued = now()
    tz = ZoneInfo(config.deadlines.timezone)
    year = issued.astimezone(tz).year
    prefix = f"{config.issuer.receipt_prefix}-CN" if kind == "credit_note" else config.issuer.receipt_prefix
    number = f"{prefix}-{year}-{await next_number(db, internship.organization_id, 'credit_note' if kind == 'credit_note' else 'receipt', year):06d}"
    against = None
    if transaction.refund_of_id:
        original = (await db.execute(select(FinancialDocument.number).where(FinancialDocument.transaction_id == transaction.refund_of_id))).scalar_one_or_none()
        against = f"Receipt {original}" if original else None
    details = {
        "kind": kind,
        "issuer": {"name": config.issuer.legal_name or (org.name if org else ""), "address": config.issuer.address, "gstin": config.issuer.gstin},
        "student": {"name": student.name, "email": student.email},
        "application_reference": application.reference,
        "internship": internship.title,
        "description": (application.fee_snapshot or {}).get("description") or config.fees.description,
        "method": METHODS.get(transaction.method or "", transaction.method or "-"),
        "transaction_reference": transaction.reference or transaction.provider_payment_id,
        "paid_on": transaction.paid_on.isoformat() if transaction.paid_on else None,
        "issued_on": issued.astimezone(tz).date().isoformat(),
        "currency": transaction.currency,
        "amount": str(q(transaction.amount)),
        "tax": tax_lines(transaction.amount, application.fee_snapshot) if kind == "tax_invoice" else None,
        "against": against,
        "footer": config.issuer.footer,
    }
    pdf = render_pdf(TITLES[kind], number, details)
    key = f"onboarding/{application.organization_id}/{application.id}/financial/{number}-{uuid.uuid4().hex[:8]}.pdf"
    await get_storage_client().upload_bytes(key, pdf, "application/pdf")
    document = FinancialDocument(
        organization_id=application.organization_id, application_id=application.id, transaction_id=transaction.id, kind=kind,
        number=number, amount=q(transaction.amount), currency=transaction.currency, details=details, storage_key=key,
        sha256=hashlib.sha256(pdf).hexdigest(), issued_at=issued, email_status="pending" if config.modes.invoice_emails else "none",
    )  # fmt: skip
    try:
        async with db.begin_nested():
            db.add(document)
            await db.flush()
    except IntegrityError:  # issued by a concurrent call a moment ago
        return (await db.execute(select(FinancialDocument).where(FinancialDocument.transaction_id == transaction.id))).scalar_one()
    await event(db, application, "document_issued", actor="system", number=number, kind=kind, amount=details["amount"])
    if document.email_status == "pending":
        enqueue_email(document.id)
    return document


async def issue_safely(db: AsyncSession, transaction: PaymentTransaction) -> None:
    """Issue without ever undoing the payment: a problem is logged and the sweep issues it later."""
    try:
        async with db.begin_nested():
            await issue(db, transaction)
    except Exception:  # noqa: BLE001
        logger.warning("onboarding_document_issue_failed", transaction_id=str(transaction.id), exc_info=True)


async def missing(db: AsyncSession, limit: int = 200) -> list[PaymentTransaction]:
    """Confirmed payments and refunds without their document yet (the sweep issues them)."""
    rows = await db.execute(
        select(PaymentTransaction)
        .outerjoin(FinancialDocument, FinancialDocument.transaction_id == PaymentTransaction.id)
        .where(PaymentTransaction.status == "confirmed", PaymentTransaction.kind.in_(("payment", "refund")), FinancialDocument.id.is_(None))
        .limit(limit)
    )
    return list(rows.scalars())


def download_url(document: FinancialDocument) -> str:
    from packages.storage.client import get_storage_client

    return get_storage_client().presigned_download_url(document.storage_key, expires=timedelta(minutes=5), download_name=f"{document.number}.pdf")


# ------------------------------------------------------------------ email


async def _send(document_id: uuid.UUID) -> bool:
    from modules.email_templates.render import render_email_full
    from packages.email.history import set_send_meta
    from packages.email.service import EmailAttachment, email_service
    from packages.storage.client import get_storage_client

    async with get_db_context() as db:
        document = await db.get(FinancialDocument, document_id, with_for_update=True)
        if document is None or document.email_status == "sent":
            return True
        d = document.details
        pdf = await get_storage_client().read_bytes(document.storage_key)
        subject, text, html, meta = await render_email_full(
            db, "internship_onboarding_receipt",
            {"full_name": d["student"]["name"], "student_name": d["student"]["name"], "internship_name": d["internship"],
             "document_title": TITLES[document.kind], "document_number": document.number,
             "amount": f"{document.currency} {document.amount:,.2f}", "application_reference": d["application_reference"]},
            organization_id=document.organization_id, recipient_email=d["student"]["email"],
        )  # fmt: skip
        set_send_meta(meta)
        document.email_attempts += 1
        sent = await email_service.send(
            d["student"]["email"], subject, text, html,
            attachments=[EmailAttachment(filename=f"{document.number}.pdf", content=pdf, mime_type="application/pdf")],
        )  # fmt: skip
        document.email_status = "sent" if sent else "failed"
        document.emailed_at = datetime.now(timezone.utc) if sent else document.emailed_at
        return bool(sent)


@celery_app.task(name="internship_onboarding.send_financial_document", bind=True, max_retries=5, default_retry_delay=300)
def send_document_task(self, document_id: str) -> None:
    try:
        if not run_async(_send(uuid.UUID(document_id))):
            raise RuntimeError("not delivered")
    except Exception as exc:  # noqa: BLE001 - retried; the payment is unaffected
        logger.warning("onboarding_document_email_failed", document_id=document_id)
        raise self.retry(exc=exc) from exc


def enqueue_email(document_id: uuid.UUID) -> None:
    try:
        send_document_task.apply_async(args=[str(document_id)], countdown=10, retry=False)
    except Exception:  # noqa: BLE001 - "pending" stays and staff can resend
        logger.warning("onboarding_document_email_enqueue_failed", document_id=str(document_id))
