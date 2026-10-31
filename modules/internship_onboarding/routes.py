"""
Internship onboarding endpoints.

Staff (``router``, mounted under /our-internships): the internship's own permissions decide who sees and changes it
(``internship_access``, so instructors keep their time-boxed rights); document review needs
``our_internships.onboarding.review`` and money needs ``our_internships.finance.*`` on top.

Students (``public_router``): no login. The link token travels in the ``X-Onboarding-Token`` header, never in the URL,
so it cannot end up in access logs. Every route is rate-limited.
"""

import uuid

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.limiter import limiter
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.emails import enqueue_invitations
from modules.internship_onboarding.payments import MAX_PROOF_BYTES, PaymentService
from modules.internship_onboarding.portal import GONE, PortalService
from modules.internship_onboarding.schemas import (
    AcceptRequest,
    ApplyTemplateRequest,
    ConfigSaveRequest,
    DecisionRequest,
    DeclineRequest,
    DraftRequest,
    LinkOut,
    CancelRequest,
    RecordPaymentRequest,
    RefundDecisionRequest,
    RefundRequest,
    ReopenRequest,
    ReviewRequest,
    StudentIdsRequest,
    TemplateArchiveRequest,
    TemplateCreateRequest,
    TemplateDuplicateRequest,
    TemplateOut,
    TemplateUpdateRequest,
    VerifyPaymentRequest,
)
from modules.internship_onboarding.service import ApplicationService, ConfigService, TemplateService, config_of
from modules.our_internships.access import internship_access
from modules.our_internships.models import OurInternship
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
templates_router = APIRouter()
public_router = APIRouter()


async def _internship(db: AsyncSession, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
    from sqlalchemy import select

    row = (
        await db.execute(select(OurInternship).where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Internship", internship_id)
    return row


def _template_out(t) -> TemplateOut:
    return TemplateOut(id=t.id, name=t.name, description=t.description, version=t.version, archived=t.archived, settings=t.settings, updated_at=t.updated_at)


# ------------------------------------------------------------------ settings


@router.get("/{internship_id}/onboarding-flow/config")
async def get_config(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return await ConfigService(db).view(await _internship(db, internship_id, organization_id), user)


@router.put("/{internship_id}/onboarding-flow/config")
async def save_config(
    internship_id: uuid.UUID,
    payload: ConfigSaveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    await ConfigService(db).save(internship, user, payload.settings)
    return await ConfigService(db).view(internship, user)


@router.get("/{internship_id}/onboarding-flow/config/versions")
async def config_versions(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await ConfigService(db).versions(await _internship(db, internship_id, organization_id))
    return [{"version": r.version, "created_at": r.created_at, "created_by_user_id": r.created_by_user_id} for r in rows]


@router.post("/{internship_id}/onboarding-flow/apply-template")
async def apply_template(
    internship_id: uuid.UUID,
    payload: ApplyTemplateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    service = TemplateService(db)
    await service.apply(await service.get(organization_id, payload.template_id), internship, user)
    return await ConfigService(db).view(internship, user)


# ------------------------------------------------------------------ students


@router.get("/{internship_id}/onboarding-flow/dashboard")
async def dashboard(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return await ApplicationService(db).dashboard(await _internship(db, internship_id, organization_id))


@router.get("/{internship_id}/onboarding-flow/students/{student_id}")
async def student_detail(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return await ApplicationService(db).detail(await _internship(db, internship_id, organization_id), student_id, user)


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/link", response_model=LinkOut)
async def new_link(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """A new personal link to copy and share by hand. It replaces any link sent before."""
    internship = await _internship(db, internship_id, organization_id)
    service = ApplicationService(db)
    selection, _ = await service.one(internship, student_id)
    issued = await service.issue_link(internship, selection, user.id, "copied by staff")
    return LinkOut(reference=issued.application.reference, link=issued.link)


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/link/revoke")
async def revoke_link(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    service = ApplicationService(db)
    selection, _ = await service.one(internship, student_id)
    await service.revoke_link(await service.ensure(internship, selection), user.id)
    return {"message": "The link no longer works."}


@router.post("/{internship_id}/onboarding-flow/invitations", status_code=status.HTTP_202_ACCEPTED)
async def send_invitations(
    internship_id: uuid.UUID,
    payload: StudentIdsRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Email each chosen student their personal link (a new one; earlier links stop working when it is sent)."""
    internship = await _internship(db, internship_id, organization_id)
    _, config = await config_of(db, internship)
    if not config.modes.self_service:
        from app.core.exceptions import ValidationError

        raise ValidationError("Student self-service is off for this internship (manual onboarding).")
    service = ApplicationService(db)
    ids, skipped = [], []
    for selection, student in await service.selections(internship, payload.student_ids):
        if selection.offer_response.value == "declined":
            skipped.append({"name": student.name, "reason": "Declined the offer."})
            continue
        application = await service.ensure(internship, selection, config)
        ids.append(application.id)
    await db.commit()  # the worker reads the applications
    enqueue_invitations(ids)
    return {"queued": len(ids), "skipped": skipped}


@router.post("/{internship_id}/onboarding-flow/reopen")
async def reopen(
    internship_id: uuid.UUID,
    payload: ReopenRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    return await ApplicationService(db).reopen(
        internship, payload.student_ids, payload.until, payload.reason, payload.late_fee, payload.late_fee_amount, user
    )


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/info-review")
async def review_info(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: DecisionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    await ApplicationService(db).review_info(await _internship(db, internship_id, organization_id), student_id, payload.approve, user)
    return {"message": "Applied." if payload.approve else "Turned down."}


@router.get("/{internship_id}/onboarding-flow/documents/{document_id}/preview")
async def preview_document(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    url = await ApplicationService(db).preview_url(await _internship(db, internship_id, organization_id), document_id, user)
    return {"url": url}


@router.post("/{internship_id}/onboarding-flow/documents/{document_id}/remove-file")
async def remove_identity_file(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Delete an identity document's file after its retention period (reviewers only; the record stays)."""
    document = await ApplicationService(db).remove_identity_file(await _internship(db, internship_id, organization_id), document_id, user)
    return {"id": document.id, "removed_at": document.removed_at}


@router.post("/{internship_id}/onboarding-flow/documents/{document_id}/review")
async def review_document(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ReviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    document = await ApplicationService(db).review(await _internship(db, internship_id, organization_id), document_id, payload.approve, payload.note, user)
    return {"id": document.id, "status": document.status}


# ------------------------------------------------------------------ payments (staff)


@router.get("/{internship_id}/onboarding-flow/payments")
async def list_payments(
    internship_id: uuid.UUID,
    status_filter: str | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Every ledger entry of the internship (finance permission). ``status_filter=awaiting_verification`` is the queue."""
    return await PaymentService(db).list_for_internship(await _internship(db, internship_id, organization_id), user, status_filter)


@router.get("/{internship_id}/onboarding-flow/payments/{transaction_id}/proof")
async def payment_proof(
    internship_id: uuid.UUID,
    transaction_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return {"url": await PaymentService(db).proof_url(await _internship(db, internship_id, organization_id), transaction_id, user)}


@router.post("/{internship_id}/onboarding-flow/payments/{transaction_id}/verify")
async def verify_payment(
    internship_id: uuid.UUID,
    transaction_id: uuid.UUID,
    payload: VerifyPaymentRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Confirm (only after checking the money arrived in the account) or reject a bank/UPI payment."""
    claim = await PaymentService(db).verify_claim(
        await _internship(db, internship_id, organization_id), transaction_id, payload.approve, payload.amount_received, payload.note, user
    )
    return {"id": claim.id, "status": claim.status, "amount": str(claim.amount)}


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/payments", status_code=status.HTTP_201_CREATED)
async def record_payment(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: RecordPaymentRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    row = await PaymentService(db).record_payment(
        await _internship(db, internship_id, organization_id), student_id, payload.method, payload.reference, payload.paid_on,
        payload.amount, payload.note, user,
    )
    return {"id": row.id, "status": row.status}


@router.post("/{internship_id}/onboarding-flow/payments/{transaction_id}/refund", status_code=status.HTTP_201_CREATED)
async def refund_payment(
    internship_id: uuid.UUID,
    transaction_id: uuid.UUID,
    payload: RefundRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Return money from a confirmed payment (finance). Online payments are refunded through the gateway; bank/UPI
    refunds wait for finance to confirm the transfer."""
    from modules.internship_onboarding.payments import RefundService

    refund = await RefundService(db).request(await _internship(db, internship_id, organization_id), transaction_id, payload.amount, payload.reason, user)
    return {"id": refund.id, "status": refund.status, "amount": str(refund.amount)}


@router.post("/{internship_id}/onboarding-flow/refunds/{transaction_id}/decide")
async def decide_refund(
    internship_id: uuid.UUID,
    transaction_id: uuid.UUID,
    payload: RefundDecisionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.payments import RefundService

    refund = await RefundService(db).decide(
        await _internship(db, internship_id, organization_id), transaction_id, payload.approve, payload.reference, payload.note, user
    )
    return {"id": refund.id, "status": refund.status}


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/cancel")
async def cancel_onboarding(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: CancelRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.payments import cancel_application

    await cancel_application(db, await _internship(db, internship_id, organization_id), student_id, payload.reason, user)
    return {"message": "Onboarding cancelled. Any refund is made separately."}


async def _financial(db: AsyncSession, internship: OurInternship, document_id: uuid.UUID, user: User):
    from sqlalchemy import select

    from modules.internship_onboarding.models import FinancialDocument, OnboardingApplication
    from modules.internship_onboarding.payments import _has_any
    from modules.internship_onboarding.service import FINANCE_VIEW, require

    if not await _has_any(db, user):
        await require(db, user, FINANCE_VIEW)
    row = (
        await db.execute(
            select(FinancialDocument).join(OnboardingApplication, OnboardingApplication.id == FinancialDocument.application_id)
            .where(FinancialDocument.id == document_id, OnboardingApplication.internship_id == internship.id,
                   FinancialDocument.organization_id == internship.organization_id)
        )
    ).scalar_one_or_none()  # fmt: skip
    if row is None:
        raise NotFoundError("Financial document", document_id)
    return row


@router.get("/{internship_id}/onboarding-flow/financial-documents")
async def list_financial_documents(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from modules.internship_onboarding.models import FinancialDocument, OnboardingApplication
    from modules.internship_onboarding.payments import _has_any
    from modules.internship_onboarding.service import FINANCE_VIEW, require

    internship = await _internship(db, internship_id, organization_id)
    if not await _has_any(db, user):
        await require(db, user, FINANCE_VIEW)
    rows = (
        await db.execute(
            select(FinancialDocument, OnboardingApplication.reference).join(OnboardingApplication, OnboardingApplication.id == FinancialDocument.application_id)
            .where(OnboardingApplication.internship_id == internship.id).order_by(FinancialDocument.issued_at.desc())
        )
    ).all()  # fmt: skip
    return [
        {"id": d.id, "kind": d.kind, "number": d.number, "amount": str(d.amount), "currency": d.currency, "application": ref,
         "student": d.details["student"]["name"], "issued_at": d.issued_at, "email_status": d.email_status}
        for d, ref in rows
    ]  # fmt: skip


@router.get("/{internship_id}/onboarding-flow/financial-documents/{document_id}/download")
async def download_financial_document(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.financial import download_url

    return {"url": download_url(await _financial(db, await _internship(db, internship_id, organization_id), document_id, user))}


@router.post("/{internship_id}/onboarding-flow/financial-documents/{document_id}/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_financial_document(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.financial import enqueue_email
    from modules.internship_onboarding.payments import _has_any

    document = await _financial(db, await _internship(db, internship_id, organization_id), document_id, user)
    if not await _has_any(db, user):
        raise NotFoundError("Financial document", document_id)
    document.email_status = "pending"
    await db.commit()
    enqueue_email(document.id)
    return {"message": "The email is on its way."}


def _csv(rows: list[list[object]], filename: str):
    import csv
    import io

    from fastapi import Response

    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        # a cell starting with = + - @ would run as a formula in a spreadsheet
        writer.writerow(["'" + str(c) if isinstance(c, str) and c[:1] in ("=", "+", "-", "@") else c for c in row])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/{internship_id}/onboarding-flow/export.csv")
async def export_board(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.payments import _has_any

    board = await ApplicationService(db).dashboard(await _internship(db, internship_id, organization_id))
    money = await _has_any(db, user)
    head = ["Reference", "Name", "Email", "Offer", "Documents", "Payment", "Overall", "LMS", "Deadline"] + (["Payable", "Received", "Outstanding"] if money else [])
    rows = [head] + [
        [r["reference"] or "", r["name"], r["email"], r["offer_status"], r["document_status"], r["payment_status"], r["overall_status"],
         r["lms_status"], r["deadline"].isoformat() if r["deadline"] else ""] + ([r["payable"], r["received"], r["outstanding"]] if money else [])
        for r in board["rows"]
    ]  # fmt: skip
    return _csv(rows, "onboarding-status.csv")


@router.get("/{internship_id}/onboarding-flow/payments.csv")
async def export_payments(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    entries = await PaymentService(db).list_for_internship(await _internship(db, internship_id, organization_id), user, None)
    head = ["Application", "Kind", "Method", "Amount", "Currency", "Status", "Reference", "Paid on", "Created", "Verified"]
    rows = [head] + [
        [e["reference_number"], e["kind"], e["method"] or "", e["amount"], e["currency"], e["status"], e["transaction_reference"] or "",
         e["paid_on"].isoformat() if e["paid_on"] else "", e["created_at"].isoformat(), e["verified_at"].isoformat() if e["verified_at"] else ""]
        for e in entries
    ]  # fmt: skip
    return _csv(rows, "onboarding-payments.csv")


# ------------------------------------------------------------------ templates


@templates_router.get("", response_model=list[TemplateOut])
async def list_templates(
    include_archived: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    return [_template_out(t) for t in await TemplateService(db).list(organization_id, include_archived)]


@templates_router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.settings
    if payload.from_internship_id is not None:
        _, config = await config_of(db, await _internship(db, payload.from_internship_id, organization_id))
        data = config.model_dump(mode="json")
    return _template_out(await TemplateService(db).create(organization_id, user, payload.name, payload.description, data or OnboardingConfig().model_dump(mode="json")))


@templates_router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TemplateService(db)
    return _template_out(await service.update(await service.get(organization_id, template_id), user, payload.name, payload.description, payload.settings))


@templates_router.post("/{template_id}/duplicate", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def duplicate_template(
    template_id: uuid.UUID,
    payload: TemplateDuplicateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TemplateService(db)
    return _template_out(await service.duplicate(await service.get(organization_id, template_id), user, payload.name))


@templates_router.post("/{template_id}/archive", response_model=TemplateOut)
async def archive_template(
    template_id: uuid.UUID,
    payload: TemplateArchiveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TemplateService(db)
    return _template_out(await service.archive(await service.get(organization_id, template_id), payload.archived))


# ------------------------------------------------------------------ students (public, by link)


async def _context(db: AsyncSession, token: str | None):
    try:
        return await PortalService(db).resolve(token or "")
    except NotFoundError:
        raise NotFoundError("Onboarding link", "") from None


@public_router.get("/internship-onboarding")
@limiter.limit("60/minute")
async def portal_view(request: Request, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    service = PortalService(db)
    return await service.view(await _context(db, x_onboarding_token))


@public_router.put("/internship-onboarding/draft")
@limiter.limit("30/minute")
async def portal_save(
    request: Request, payload: DraftRequest, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    service = PortalService(db)
    return await service.save(await _context(db, x_onboarding_token), payload.step, payload.info, payload.answers)


@public_router.post("/internship-onboarding/documents/{key}", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def portal_upload(
    request: Request, key: str, file: UploadFile = File(...), x_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.config import MAX_DOCUMENT_MB

    ctx = await _context(db, x_onboarding_token)
    data = await file.read(MAX_DOCUMENT_MB * 1024 * 1024 + 1)
    document = await PortalService(db).upload(ctx, key, file.filename or "document", data)
    return {"key": document.requirement_key, "version": document.version, "status": document.status, "filename": document.filename}


@public_router.post("/internship-onboarding/accept")
@limiter.limit("10/minute")
async def portal_accept(
    request: Request, payload: AcceptRequest, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    service = PortalService(db)
    ctx = await _context(db, x_onboarding_token)
    await service.accept(ctx, payload.confirmed, payload.terms_version, request.client.host if request.client else None, request.headers.get("User-Agent"))
    return await service.view(ctx)


@public_router.post("/internship-onboarding/decline")
@limiter.limit("10/minute")
async def portal_decline(
    request: Request, payload: DeclineRequest, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    service = PortalService(db)
    ctx = await _context(db, x_onboarding_token)
    await service.decline(ctx, payload.reason)
    return await service.view(ctx)


@public_router.post("/internship-onboarding/payments/manual", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def portal_manual_payment(
    request: Request,
    method: str = Form(...),
    reference: str = Form(..., min_length=4, max_length=120),
    paid_on: date = Form(...),
    amount: Decimal = Form(..., gt=0, max_digits=12, decimal_places=2),
    remarks: str | None = Form(default=None, max_length=1000),
    proof: UploadFile = File(...),
    x_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    from app.core.exceptions import ValidationError

    if method not in ("bank_transfer", "upi"):
        raise ValidationError("Choose bank transfer or UPI.")
    ctx = await _context(db, x_onboarding_token)
    data = await proof.read(MAX_PROOF_BYTES + 1)
    await PaymentService(db).submit_claim(ctx, method, reference, paid_on, amount, remarks, proof.filename or "proof", data)
    return await PortalService(db).view(ctx)


@public_router.post("/internship-onboarding/payments/checkout")
@limiter.limit("10/minute")
async def portal_checkout(request: Request, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    """Start (or resume) online payment. The amount is decided here, never by the browser."""
    return await PaymentService(db).start_checkout(await _context(db, x_onboarding_token))


@public_router.post("/internship-onboarding/payments/refresh")
@limiter.limit("10/minute")
async def portal_refresh(request: Request, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    """Ask the gateway about this student's payment. Returning from the checkout page alone never confirms anything."""
    ctx = await _context(db, x_onboarding_token)
    outcome = await PaymentService(db).refresh_for_student(ctx)
    return {"outcome": outcome, **(await PortalService(db).view(ctx))}


@public_router.get("/internship-onboarding/financial-documents/{document_id}")
@limiter.limit("30/minute")
async def portal_financial_document(
    request: Request, document_id: uuid.UUID, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    """A short-lived link to one of the student's own receipts (also after their deadline)."""
    from modules.internship_onboarding.financial import download_url
    from modules.internship_onboarding.models import FinancialDocument

    ctx = await _context(db, x_onboarding_token)
    document = await db.get(FinancialDocument, document_id)
    if document is None or document.application_id != ctx.application.id:
        raise NotFoundError("Financial document", document_id)
    return {"url": download_url(document)}


@public_router.post("/payments/cashfree/webhook", include_in_schema=False)
@limiter.limit("300/minute")
async def cashfree_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    if len(raw) > 64 * 1024:
        return JSONResponse({"ok": False}, status_code=413)
    code, outcome = await PaymentService(db).handle_webhook(raw, dict(request.headers))
    return JSONResponse({"ok": code == 200, "outcome": outcome}, status_code=code)


__all__ = ["router", "templates_router", "public_router", "GONE"]
