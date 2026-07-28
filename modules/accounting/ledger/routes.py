import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.ledger.models import AccountType
from modules.accounting.ledger.schemas import (
    AccountBalanceResponse,
    AccountCreateRequest,
    AccountPublic,
    AccountUpdateRequest,
    MessageResponse,
)
from modules.accounting.ledger.service import AccountService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=AccountPublic, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.ledger.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AccountService(db)
    account = await service.create_account(organization_id, **payload.model_dump())
    return AccountPublic.model_validate(account)


@router.get("", response_model=dict)
async def list_accounts(
    account_type: AccountType | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.ledger.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AccountService(db)
    accounts, total = await service.list_accounts(
        organization_id,
        account_type=account_type,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [AccountPublic.model_validate(a) for a in accounts],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{account_id}", response_model=AccountPublic)
async def get_account(
    account_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.ledger.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AccountService(db)
    account = await service.get_account(account_id, organization_id)
    return AccountPublic.model_validate(account)


@router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance(
    account_id: uuid.UUID,
    as_of_date: date | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.ledger.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AccountService(db)
    balance = await service.get_account_balance(account_id, organization_id, as_of_date)
    return AccountBalanceResponse(**balance)


@router.patch("/{account_id}", response_model=AccountPublic)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.ledger.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AccountService(db)
    account = await service.update_account(
        account_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AccountPublic.model_validate(account)
