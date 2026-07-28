import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.vendors.schemas import (
    MessageResponse,
    VendorCreateRequest,
    VendorPublic,
    VendorUpdateRequest,
)
from modules.accounting.vendors.service import VendorService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=VendorPublic, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.vendors.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VendorService(db)
    vendor = await service.create_vendor(organization_id, **payload.model_dump())
    return VendorPublic.model_validate(vendor)


@router.get("", response_model=dict)
async def list_vendors(
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.vendors.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VendorService(db)
    vendors, total = await service.list_vendors(
        organization_id, is_active=is_active, search=search, skip=skip, limit=limit
    )
    return {
        "items": [VendorPublic.model_validate(v) for v in vendors],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{vendor_id}", response_model=VendorPublic)
async def get_vendor(
    vendor_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.vendors.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VendorService(db)
    vendor = await service.get_vendor(vendor_id, organization_id)
    return VendorPublic.model_validate(vendor)


@router.patch("/{vendor_id}", response_model=VendorPublic)
async def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.vendors.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VendorService(db)
    vendor = await service.update_vendor(
        vendor_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return VendorPublic.model_validate(vendor)


@router.delete("/{vendor_id}", response_model=MessageResponse)
async def delete_vendor(
    vendor_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.vendors.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VendorService(db)
    await service.delete_vendor(vendor_id, organization_id)
    return MessageResponse(message="Vendor deleted successfully.")
