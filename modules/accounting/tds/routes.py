import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.tds.schemas import (
    MessageResponse,
    TDSDeductionPublic,
    TDSSectionCreateRequest,
    TDSSectionPublic,
    TDSSectionUpdateRequest,
)
from modules.accounting.tds.service import TDSService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/sections", response_model=TDSSectionPublic, status_code=status.HTTP_201_CREATED)
async def create_tds_section(
    payload: TDSSectionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.tds.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TDSService(db)
    section = await service.create_section(organization_id, **payload.model_dump())
    return TDSSectionPublic.model_validate(section)


@router.get("/sections", response_model=list[TDSSectionPublic])
async def list_tds_sections(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.tds.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TDSService(db)
    sections = await service.list_sections(organization_id, is_active)
    return [TDSSectionPublic.model_validate(s) for s in sections]


@router.patch("/sections/{section_id}", response_model=TDSSectionPublic)
async def update_tds_section(
    section_id: uuid.UUID,
    payload: TDSSectionUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.tds.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TDSService(db)
    section = await service.update_section(
        section_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return TDSSectionPublic.model_validate(section)


@router.get("/deductions/by-vendor/{vendor_id}", response_model=list[TDSDeductionPublic])
async def list_deductions_for_vendor(
    vendor_id: uuid.UUID,
    financial_year: str | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.tds.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TDSService(db)
    deductions = await service.list_deductions_for_vendor(vendor_id, financial_year)
    return [TDSDeductionPublic.model_validate(d) for d in deductions]
