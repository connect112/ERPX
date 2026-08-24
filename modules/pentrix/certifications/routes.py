import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.certifications.schemas import (
    CertificationPublic,
    CertificationVerificationResponse,
    IssueCertificationRequest,
)
from modules.pentrix.certifications.service import CertificationService
from modules.pentrix.common.dependencies import enforce_own_student_or_staff
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=CertificationPublic, status_code=status.HTTP_201_CREATED)
async def issue_certification(
    payload: IssueCertificationRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.certifications.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CertificationService(db)
    cert = await service.issue_certification(
        organization_id,
        payload.student_id,
        payload.track_name,
        payload.minimum_points,
        payload.force,
    )
    return CertificationPublic.model_validate(cert)


@router.get("/students/{student_id}", response_model=list[CertificationPublic])
async def list_certifications_for_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.certifications.view")),
    _ownership: None = Depends(enforce_own_student_or_staff),
    db: AsyncSession = Depends(get_db),
):
    service = CertificationService(db)
    certs = await service.list_for_student(student_id, organization_id)
    return [CertificationPublic.model_validate(c) for c in certs]


@router.get("/verify/{certificate_number}", response_model=CertificationVerificationResponse)
async def verify_certification(certificate_number: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint — no authentication required, for third-party verification."""
    service = CertificationService(db)
    return await service.verify(certificate_number)
