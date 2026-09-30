import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.employees.dependencies import get_current_employee
from modules.employees.models import Employee
from modules.expense_claims.models import ExpenseClaimStatus
from modules.expense_claims.schemas import (
    ExpenseClaimPublic,
    ExpenseClaimRejectRequest,
    ExpenseClaimSelfCreateRequest,
    MessageResponse,
    ReceiptUploadRequest,
    ReceiptUploadResponse,
)
from modules.expense_claims.service import ExpenseClaimService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Employee self-service ----
#
# Ownership-gated via get_current_employee, same "owning the record is
# the authorization" pattern as modules/leave's /applications/me — no
# employee holds documents.manage, so receipt upload is exposed here
# rather than through modules/documents' own admin-gated routes.


@router.post("/me/receipts/presigned-upload", response_model=ReceiptUploadResponse)
async def request_receipt_upload(
    payload: ReceiptUploadRequest,
    employee: Employee = Depends(get_current_employee),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    document_id, upload_url = await service.request_receipt_upload(
        employee.organization_id, employee.id, employee.user_id, payload.filename, payload.content_type
    )
    return ReceiptUploadResponse(document_id=document_id, upload_url=upload_url)


@router.post("/me/receipts/{document_id}/confirm", response_model=MessageResponse)
async def confirm_receipt_upload(
    document_id: uuid.UUID,
    employee: Employee = Depends(get_current_employee),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    await service.confirm_receipt_upload(employee.organization_id, document_id)
    return MessageResponse(message="Receipt uploaded successfully.")


@router.post("/me", response_model=ExpenseClaimPublic, status_code=status.HTTP_201_CREATED)
async def submit_claim_as_employee(
    payload: ExpenseClaimSelfCreateRequest,
    employee: Employee = Depends(get_current_employee),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claim = await service.submit_claim(
        employee.organization_id, employee_id=employee.id, **payload.model_dump()
    )
    return ExpenseClaimPublic.model_validate(claim)


@router.get("/me", response_model=dict)
async def list_my_claims(
    status_filter: ExpenseClaimStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    employee: Employee = Depends(get_current_employee),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claims, total = await service.list_for_employee(
        employee.id, employee.organization_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [ExpenseClaimPublic.model_validate(c) for c in claims],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


# ---- Admin review ----


@router.get("", response_model=dict)
async def list_claims(
    status_filter: ExpenseClaimStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("expense_claims.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claims, total = await service.list_for_organization(
        organization_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [ExpenseClaimPublic.model_validate(c) for c in claims],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/employees/{employee_id}", response_model=dict)
async def list_employee_claims(
    employee_id: uuid.UUID,
    status_filter: ExpenseClaimStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("expense_claims.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claims, total = await service.list_for_employee(
        employee_id, organization_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [ExpenseClaimPublic.model_validate(c) for c in claims],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{claim_id}", response_model=ExpenseClaimPublic)
async def get_claim(
    claim_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("expense_claims.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claim = await service.get_claim(claim_id, organization_id)
    return ExpenseClaimPublic.model_validate(claim)


@router.post("/{claim_id}/approve", response_model=ExpenseClaimPublic)
async def approve_claim(
    claim_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("expense_claims.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claim = await service.approve_claim(claim_id, organization_id, reviewed_by_user_id=user.id)
    return ExpenseClaimPublic.model_validate(claim)


@router.post("/{claim_id}/reject", response_model=ExpenseClaimPublic)
async def reject_claim(
    claim_id: uuid.UUID,
    payload: ExpenseClaimRejectRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("expense_claims.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseClaimService(db)
    claim = await service.reject_claim(
        claim_id, organization_id, reviewed_by_user_id=user.id, rejection_reason=payload.rejection_reason
    )
    return ExpenseClaimPublic.model_validate(claim)
