import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.crm.enquiries.schemas import (
    EnquiryCreateRequest,
    EnquiryPublic,
    EnquiryUpdateRequest,
    MessageResponse,
)
from modules.crm.enquiries.service import EnquiryService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post(
    "/leads/{lead_id}/enquiries", response_model=EnquiryPublic, status_code=status.HTTP_201_CREATED
)
async def create_enquiry(
    lead_id: uuid.UUID,
    payload: EnquiryCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.enquiries.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EnquiryService(db)
    enquiry = await service.create_enquiry(lead_id, organization_id, **payload.model_dump())
    return EnquiryPublic.model_validate(enquiry)


@router.get("/leads/{lead_id}/enquiries", response_model=list[EnquiryPublic])
async def list_enquiries(
    lead_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.enquiries.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EnquiryService(db)
    enquiries = await service.list_enquiries(lead_id, organization_id)
    return [EnquiryPublic.model_validate(e) for e in enquiries]


@router.get("/leads/{lead_id}/enquiries/{enquiry_id}", response_model=EnquiryPublic)
async def get_enquiry(
    lead_id: uuid.UUID,
    enquiry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.enquiries.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EnquiryService(db)
    enquiry = await service.get_enquiry(enquiry_id, lead_id, organization_id)
    return EnquiryPublic.model_validate(enquiry)


@router.patch("/leads/{lead_id}/enquiries/{enquiry_id}", response_model=EnquiryPublic)
async def update_enquiry(
    lead_id: uuid.UUID,
    enquiry_id: uuid.UUID,
    payload: EnquiryUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.enquiries.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EnquiryService(db)
    enquiry = await service.update_enquiry(
        enquiry_id, lead_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return EnquiryPublic.model_validate(enquiry)


@router.delete("/leads/{lead_id}/enquiries/{enquiry_id}", response_model=MessageResponse)
async def delete_enquiry(
    lead_id: uuid.UUID,
    enquiry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.enquiries.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EnquiryService(db)
    await service.delete_enquiry(enquiry_id, lead_id, organization_id)
    return MessageResponse(message="Enquiry deleted successfully.")
