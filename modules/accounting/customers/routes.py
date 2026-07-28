import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.customers.schemas import (
    CustomerCreateRequest,
    CustomerPublic,
    CustomerUpdateRequest,
    MessageResponse,
)
from modules.accounting.customers.service import CustomerService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=CustomerPublic, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.customers.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CustomerService(db)
    customer = await service.create_customer(organization_id, **payload.model_dump())
    return CustomerPublic.model_validate(customer)


@router.get("", response_model=dict)
async def list_customers(
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.customers.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CustomerService(db)
    customers, total = await service.list_customers(
        organization_id, is_active=is_active, search=search, skip=skip, limit=limit
    )
    return {
        "items": [CustomerPublic.model_validate(c) for c in customers],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{customer_id}", response_model=CustomerPublic)
async def get_customer(
    customer_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.customers.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CustomerService(db)
    customer = await service.get_customer(customer_id, organization_id)
    return CustomerPublic.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerPublic)
async def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.customers.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CustomerService(db)
    customer = await service.update_customer(
        customer_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return CustomerPublic.model_validate(customer)


@router.delete("/{customer_id}", response_model=MessageResponse)
async def delete_customer(
    customer_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.customers.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CustomerService(db)
    await service.delete_customer(customer_id, organization_id)
    return MessageResponse(message="Customer deleted successfully.")
