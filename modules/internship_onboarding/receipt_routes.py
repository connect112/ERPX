"""
Receipt Designer and Generated Receipts endpoints (staff only), under /our-internships/{internship_id}/.

Seeing a design, a preview or a document needs the internship's view access plus a finance permission; changing a design or an image
needs ``our_internships.finance.manage``. Everything is scoped to the internship's organization. No endpoint here issues, edits or
regenerates a financial document: documents are issued only by ``financial.issue`` when a payment is confirmed.
"""

import hashlib
import uuid
from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from modules.authentication.models import User
from modules.internship_onboarding.models import (
    FinancialDocument,
    OnboardingApplication,
    OnboardingEvent,
    PaymentTransaction,
)
from modules.internship_onboarding.receipt_service import ReceiptDesignService
from modules.internship_onboarding.service import FINANCE_MANAGE, FINANCE_VIEW, has, require
from modules.our_internships.access import internship_access
from modules.our_internships.models import OurInternship
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_SAFE_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Security-Policy": "default-src 'none'; sandbox"}


class SaveDesign(BaseModel):
    scope: Literal["internship", "organization"] = "internship"
    design: dict
    base_version: int | None = None


class IssuerUpdate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    gstin: str | None = Field(default=None, pattern=r"^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]{3}$")
    receipt_prefix: str = Field(pattern=r"^[A-Z][A-Z0-9-]{1,11}$")
    footer: str = Field(default="", max_length=500)


class PreviewRequest(BaseModel):
    sample: dict | None = None  # preview-only sample customer/payment details (never stored; sample previews only)
    design: dict | None = None  # the draft on screen (unsaved); empty: the design that applies now
    kind: Literal["receipt", "tax_invoice", "credit_note"] = "receipt"
    source: Literal["sample", "transaction"] = "sample"
    transaction_id: uuid.UUID | None = None


class NewTemplate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    design: dict


class ApplyTemplate(BaseModel):
    scope: Literal["internship", "organization"] = "internship"


async def _internship(db: AsyncSession, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
    row = (await db.execute(select(OurInternship).where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id))).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Internship", internship_id)
    return row


async def _need_finance_view(db: AsyncSession, user: User) -> None:
    if not (await has(db, user, FINANCE_VIEW) or await has(db, user, FINANCE_MANAGE)):
        await require(db, user, FINANCE_VIEW)


# ------------------------------------------------------------------ the designer


@router.get("/{internship_id}/receipt-designer")
async def designer(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    out = await ReceiptDesignService(db).view(internship, user)
    from modules.internship_onboarding.service import config_of

    _, config = await config_of(db, internship)
    # the legal identity comes from the onboarding settings (finance-controlled and versioned); the designer only shows it
    out["issuer"] = {"legal_name": config.issuer.legal_name, "address": config.issuer.address, "gstin": config.issuer.gstin, "receipt_prefix": config.issuer.receipt_prefix, "footer": config.issuer.footer}
    out["fee"] = {"tax_mode": config.fees.tax_mode, "invoices_issued": bool(config.issuer.gstin and config.fees.tax_mode != "none")}
    return out


@router.put("/{internship_id}/receipt-designer/design")
async def save_design(
    internship_id: uuid.UUID,
    payload: SaveDesign,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Save a design for future documents. Documents already issued are never touched."""
    record = await ReceiptDesignService(db).save(await _internship(db, internship_id, organization_id), user, payload.scope, payload.design, payload.base_version)
    return {"version": record.version, "scope": record.scope, "message": "Saved. It applies to documents issued from now on; documents already issued are unchanged."}


@router.delete("/{internship_id}/receipt-designer/design")
async def reset_design(
    internship_id: uuid.UUID,
    scope: Literal["internship", "organization"] = "internship",
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    await ReceiptDesignService(db).reset(await _internship(db, internship_id, organization_id), user, scope)
    return {"message": "Reset to the default. Documents already issued are unchanged."}


@router.put("/{internship_id}/receipt-designer/issuer")
async def save_issuer(
    internship_id: uuid.UUID,
    payload: IssuerUpdate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Change the issuer's legal name, address, GSTIN, number prefix or footer through the versioned onboarding settings (finance
    management permission). Affects only documents issued afterwards."""
    version = await ReceiptDesignService(db).save_issuer(await _internship(db, internship_id, organization_id), user, payload.model_dump())
    return {"settings_version": version, "message": "Saved in the finance settings. It applies to documents issued from now on; documents already issued are unchanged."}


@router.post("/{internship_id}/receipt-designer/preview")
async def preview(
    internship_id: uuid.UUID,
    payload: PreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The draft design drawn as a PDF. Read-only: no number is taken, nothing is stored or sent. Every page is marked as a sample."""
    internship = await _internship(db, internship_id, organization_id)
    pdf, pages, watermark = await ReceiptDesignService(db).preview(internship, user, payload.design, payload.kind, payload.source, payload.transaction_id, payload.sample)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={**_SAFE_HEADERS, "Content-Disposition": 'inline; filename="receipt-preview.pdf"', "X-Page-Count": str(pages), "X-Watermark": watermark,
                 "Access-Control-Expose-Headers": "X-Page-Count, X-Watermark"},
    )  # fmt: skip


# ------------------------------------------------------------------ images


@router.post("/{internship_id}/receipt-designer/assets", status_code=201)
async def upload_asset(
    internship_id: uuid.UUID,
    kind: str = Form(...),
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.receipt_service import MAX_UPLOAD_BYTES

    data = await file.read(MAX_UPLOAD_BYTES + 1)  # never read more than the limit
    return await ReceiptDesignService(db).upload(await _internship(db, internship_id, organization_id), user, kind, file.filename or "image.png", data)


@router.get("/{internship_id}/receipt-designer/assets/{asset_id}/image")
async def asset_image(
    internship_id: uuid.UUID,
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    asset = await ReceiptDesignService(db).asset(await _internship(db, internship_id, organization_id), user, asset_id)
    return Response(content=asset.data, media_type="image/png", headers={**_SAFE_HEADERS, "Content-Disposition": 'inline; filename="image.png"'})


@router.delete("/{internship_id}/receipt-designer/assets/{asset_id}")
async def delete_asset(
    internship_id: uuid.UUID,
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    await ReceiptDesignService(db).archive_asset(await _internship(db, internship_id, organization_id), user, asset_id)
    return {"message": "Removed."}


# ------------------------------------------------------------------ templates


@router.post("/{internship_id}/receipt-designer/templates", status_code=201)
async def create_template(
    internship_id: uuid.UUID,
    payload: NewTemplate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    record = await ReceiptDesignService(db).create_template(await _internship(db, internship_id, organization_id), user, payload.name, payload.description, payload.design)
    return {"id": record.id, "name": record.name, "version": record.version}


@router.post("/{internship_id}/receipt-designer/templates/{template_id}/apply")
async def apply_template(
    internship_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: ApplyTemplate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    record = await ReceiptDesignService(db).apply_template(await _internship(db, internship_id, organization_id), user, template_id, payload.scope)
    return {"version": record.version, "scope": record.scope}


@router.delete("/{internship_id}/receipt-designer/templates/{template_id}")
async def archive_template(
    internship_id: uuid.UUID,
    template_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    await ReceiptDesignService(db).archive_template(await _internship(db, internship_id, organization_id), user, template_id)
    return {"message": "Archived."}


# ------------------------------------------------------------------ generated receipts


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _row(d: FinancialDocument, reference: str, title: str, t: PaymentTransaction) -> dict:
    used = d.details.get("design") or {}
    render = d.details.get("render") or {}
    return {
        "id": d.id, "number": d.number, "kind": d.kind, "student": d.details["student"]["name"], "email": d.details["student"].get("email"),
        "internship": title, "application": reference, "amount": str(d.amount), "currency": d.currency, "paid_on": t.paid_on,
        "method": t.method, "issued_at": d.issued_at, "email_status": d.email_status, "emailed_at": d.emailed_at, "transaction_id": d.transaction_id,
        "design_source": used.get("source"), "design_version": used.get("version"), "pages": render.get("pages"), "engine": render.get("engine", "legacy"),
    }  # fmt: skip


@router.get("/{internship_id}/receipts")
async def list_receipts(
    internship_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=100),
    kind: Literal["receipt", "tax_invoice", "credit_note"] | None = None,
    email_status: Literal["none", "pending", "sent", "failed"] | None = None,
    issued_from: date | None = None,
    issued_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The documents issued for this internship, newest first, with search and filters."""
    internship = await _internship(db, internship_id, organization_id)
    await _need_finance_view(db, user)
    conditions = [OnboardingApplication.internship_id == internship.id, FinancialDocument.organization_id == internship.organization_id]
    if q:
        like = _like(q.strip())
        conditions.append(or_(
            FinancialDocument.number.ilike(like, escape="\\"), OnboardingApplication.reference.ilike(like, escape="\\"),
            FinancialDocument.details["student"]["name"].astext.ilike(like, escape="\\"), FinancialDocument.details["student"]["email"].astext.ilike(like, escape="\\"),
            PaymentTransaction.reference.ilike(like, escape="\\"),
        ))  # fmt: skip
    if kind:
        conditions.append(FinancialDocument.kind == kind)
    if email_status:
        conditions.append(FinancialDocument.email_status == email_status)
    if issued_from:
        conditions.append(FinancialDocument.issued_at >= datetime.combine(issued_from, time.min, tzinfo=timezone.utc))
    if issued_to:
        conditions.append(FinancialDocument.issued_at <= datetime.combine(issued_to, time.max, tzinfo=timezone.utc))
    base = (
        select(FinancialDocument, OnboardingApplication.reference, PaymentTransaction)
        .join(OnboardingApplication, OnboardingApplication.id == FinancialDocument.application_id)
        .join(PaymentTransaction, PaymentTransaction.id == FinancialDocument.transaction_id)
        .where(and_(*conditions))
    )  # fmt: skip
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(FinancialDocument.issued_at.desc(), FinancialDocument.id).limit(limit).offset(offset))).all()
    return {"total": total, "items": [_row(d, ref, internship.title, t) for d, ref, t in rows]}


async def _document(db: AsyncSession, internship: OurInternship, document_id: uuid.UUID) -> FinancialDocument:
    row = (
        await db.execute(
            select(FinancialDocument).join(OnboardingApplication, OnboardingApplication.id == FinancialDocument.application_id)
            .where(FinancialDocument.id == document_id, OnboardingApplication.internship_id == internship.id, FinancialDocument.organization_id == internship.organization_id)
        )
    ).scalar_one_or_none()  # fmt: skip
    if row is None:
        raise NotFoundError("Financial document", document_id)
    return row


@router.get("/{internship_id}/receipts/{document_id}/pdf")
async def receipt_pdf(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    download: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The stored PDF, exactly as it was issued (never drawn again), for the in-page viewer or as a download. There is no public link."""
    from packages.storage.client import get_storage_client

    internship = await _internship(db, internship_id, organization_id)
    await _need_finance_view(db, user)
    document = await _document(db, internship, document_id)
    data = await get_storage_client().read_bytes(document.storage_key)
    if hashlib.sha256(data).hexdigest() != document.sha256:
        # the stored file no longer matches what was issued: never hand it out as the document
        raise ConflictError("The stored copy of this document does not match the checksum recorded when it was issued. Contact an administrator.")
    name = "".join(ch for ch in document.number if ch.isalnum() or ch in "-_") or "document"
    disposition = "attachment" if download else "inline"
    return Response(content=data, media_type="application/pdf", headers={**_SAFE_HEADERS, "Content-Disposition": f'{disposition}; filename="{name}.pdf"'})


@router.get("/{internship_id}/receipts/{document_id}/history")
async def receipt_history(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """How this document came to be: the linked payment, the design it was issued with, its delivery, and the timeline entries about it."""
    internship = await _internship(db, internship_id, organization_id)
    await _need_finance_view(db, user)
    d = await _document(db, internship, document_id)
    t = await db.get(PaymentTransaction, d.transaction_id)
    events = (
        await db.execute(select(OnboardingEvent).where(OnboardingEvent.application_id == d.application_id).order_by(OnboardingEvent.created_at))
    ).scalars().all()
    used = d.details.get("design") or {}
    return {
        "document": {"id": d.id, "number": d.number, "kind": d.kind, "amount": str(d.amount), "currency": d.currency, "issued_at": d.issued_at, "sha256": d.sha256},
        "transaction": {
            "id": t.id, "kind": t.kind, "method": t.method, "amount": str(t.amount), "currency": t.currency, "status": t.status, "reference": t.reference or t.provider_payment_id,
            "paid_on": t.paid_on, "verified_at": t.verified_at, "provider": t.provider,
        } if t else None,  # fmt: skip
        "design": {"source": used.get("source"), "version": used.get("version"), "assets": used.get("assets"), "engine": (d.details.get("render") or {}).get("engine", "legacy"),
                   "pages": (d.details.get("render") or {}).get("pages")},  # fmt: skip
        "delivery": {"status": d.email_status, "attempts": d.email_attempts, "emailed_at": d.emailed_at},
        "events": [
            {"at": e.created_at, "actor": e.actor, "event": e.event, "detail": e.detail}
            for e in events
            if e.event == "document_issued" and (e.detail or {}).get("number") == d.number
        ],
    }  # fmt: skip
