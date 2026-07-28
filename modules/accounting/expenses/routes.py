import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.expenses.models import ExpenseStatus
from modules.accounting.expenses.schemas import (
    ExpenseCreateRequest,
    ExpensePublic,
    ExpenseRejectRequest,
    ExpenseUpdateRequest,
    MessageResponse,
)
from modules.accounting.expenses.service import ExpenseService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=ExpensePublic, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expense = await service.create_expense(organization_id, **payload.model_dump())
    return ExpensePublic.model_validate(expense)


@router.get("", response_model=dict)
async def list_expenses(
    vendor_id: uuid.UUID | None = None,
    status_filter: ExpenseStatus | None = Query(default=None, alias="status"),
    category: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expenses, total = await service.list_expenses(
        organization_id,
        vendor_id=vendor_id,
        status=status_filter,
        category=category,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [ExpensePublic.model_validate(e) for e in expenses],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{expense_id}", response_model=ExpensePublic)
async def get_expense(
    expense_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expense = await service.get_expense(expense_id, organization_id)
    return ExpensePublic.model_validate(expense)


@router.patch("/{expense_id}", response_model=ExpensePublic)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expense = await service.update_expense(
        expense_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return ExpensePublic.model_validate(expense)


@router.post("/{expense_id}/approve", response_model=ExpensePublic)
async def approve_expense(
    expense_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.approve")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expense = await service.approve_expense(expense_id, organization_id, approved_by_user_id=user.id)
    return ExpensePublic.model_validate(expense)


@router.post("/{expense_id}/reject", response_model=ExpensePublic)
async def reject_expense(
    expense_id: uuid.UUID,
    payload: ExpenseRejectRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.approve")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expense = await service.reject_expense(expense_id, organization_id, payload.rejection_reason)
    return ExpensePublic.model_validate(expense)


@router.post("/{expense_id}/cancel", response_model=ExpensePublic)
async def cancel_expense(
    expense_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.expenses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ExpenseService(db)
    expense = await service.cancel_expense(expense_id, organization_id)
    return ExpensePublic.model_validate(expense)
