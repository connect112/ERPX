import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.bank.schemas import (
    BankAccountBalanceResponse,
    BankAccountCreateRequest,
    BankAccountPublic,
    BankAccountUpdateRequest,
    BankTransactionCreateRequest,
    BankTransactionPublic,
    MessageResponse,
)
from modules.accounting.bank.service import BankService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/accounts", response_model=BankAccountPublic, status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    payload: BankAccountCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    account = await service.create_bank_account(organization_id, **payload.model_dump())
    return BankAccountPublic.model_validate(account)


@router.get("/accounts", response_model=list[BankAccountPublic])
async def list_bank_accounts(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    accounts = await service.list_bank_accounts(organization_id, is_active)
    return [BankAccountPublic.model_validate(a) for a in accounts]


@router.get("/accounts/{bank_account_id}", response_model=BankAccountPublic)
async def get_bank_account(
    bank_account_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    account = await service.get_bank_account(bank_account_id, organization_id)
    return BankAccountPublic.model_validate(account)


@router.patch("/accounts/{bank_account_id}", response_model=BankAccountPublic)
async def update_bank_account(
    bank_account_id: uuid.UUID,
    payload: BankAccountUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    account = await service.update_bank_account(
        bank_account_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return BankAccountPublic.model_validate(account)


@router.get("/accounts/{bank_account_id}/balance", response_model=BankAccountBalanceResponse)
async def get_bank_account_balance(
    bank_account_id: uuid.UUID,
    as_of_date: date | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    balance = await service.get_balance(bank_account_id, organization_id, as_of_date)
    return BankAccountBalanceResponse(**balance)


@router.post(
    "/accounts/{bank_account_id}/transactions",
    response_model=BankTransactionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def record_bank_transaction(
    bank_account_id: uuid.UUID,
    payload: BankTransactionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    txn = await service.record_manual_transaction(
        bank_account_id,
        organization_id,
        created_by_user_id=user.id,
        **payload.model_dump(),
    )
    return BankTransactionPublic.model_validate(txn)


@router.get("/accounts/{bank_account_id}/transactions", response_model=dict)
async def list_bank_transactions(
    bank_account_id: uuid.UUID,
    is_reconciled: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.bank.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    # Ownership check.
    await service.get_bank_account(bank_account_id, organization_id)
    txns, total = await service.list_transactions(
        bank_account_id,
        is_reconciled=is_reconciled,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [BankTransactionPublic.model_validate(t) for t in txns],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/transactions/{transaction_id}/reconcile", response_model=BankTransactionPublic)
async def reconcile_bank_transaction(
    transaction_id: uuid.UUID,
    user: User = Depends(require_permissions("accounting.bank.reconcile")),
    db: AsyncSession = Depends(get_db),
):
    service = BankService(db)
    txn = await service.reconcile_transaction(transaction_id)
    return BankTransactionPublic.model_validate(txn)
