import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.crm.leads.models import LeadStatus
from modules.crm.leads.schemas import (
    LeadCreateRequest,
    LeadPublic,
    LeadStatusChangeRequest,
    LeadUpdateRequest,
    MessageResponse,
)
from modules.crm.leads.service import LeadService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=LeadPublic, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.leads.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    lead = await service.create_lead(organization_id, **payload.model_dump())
    return LeadPublic.model_validate(lead)


@router.get("", response_model=dict)
async def list_leads(
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    assigned_to_user_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.leads.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    leads, total = await service.list_leads(
        organization_id,
        status=status_filter,
        assigned_to_user_id=assigned_to_user_id,
        campaign_id=campaign_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [LeadPublic.model_validate(lead) for lead in leads],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{lead_id}", response_model=LeadPublic)
async def get_lead(
    lead_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.leads.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    lead = await service.get_lead(lead_id, organization_id)
    return LeadPublic.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadPublic)
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.leads.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    lead = await service.update_lead(
        lead_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return LeadPublic.model_validate(lead)


@router.post("/{lead_id}/status", response_model=LeadPublic)
async def change_lead_status(
    lead_id: uuid.UUID,
    payload: LeadStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.leads.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    lead = await service.change_status(
        lead_id, organization_id, payload.status, payload.lost_reason
    )
    return LeadPublic.model_validate(lead)


@router.delete("/{lead_id}", response_model=MessageResponse)
async def delete_lead(
    lead_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.leads.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    await service.delete_lead(lead_id, organization_id)
    return MessageResponse(message="Lead deleted successfully.")
