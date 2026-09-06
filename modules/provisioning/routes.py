"""
Provisioning module — routes.

Everything here is internal, service-to-service traffic (Pentrix-share ->
ERPX on payment success) — never part of the RBAC-authenticated API surface
a logged-in user's browser talks to. Auth is HMAC (see dependencies.py), not
a user JWT, and there is deliberately no `require_permissions(...)` on this
router.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.provisioning.dependencies import verify_internal_signature
from modules.provisioning.schemas import ProvisionStudentRequest, ProvisionStudentResponse
from modules.provisioning.service import ProvisioningService

router = APIRouter()


@router.post(
    "/students",
    response_model=ProvisionStudentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_internal_signature)],
)
async def provision_student(
    payload: ProvisionStudentRequest,
    db: AsyncSession = Depends(get_db),
):
    service = ProvisioningService(db)
    return await service.provision_student(payload)
