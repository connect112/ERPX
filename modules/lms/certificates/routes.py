import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.certificates.schemas import (
    CertificatePublic,
    CertificateVerificationResponse,
    IssueCertificateRequest,
)
from modules.lms.certificates.service import CertificateService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=CertificatePublic, status_code=status.HTTP_201_CREATED)
async def issue_certificate(
    payload: IssueCertificateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.certificates.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CertificateService(db)
    certificate = await service.issue_certificate(
        organization_id, payload.student_id, payload.course_id, payload.force
    )
    return CertificatePublic.model_validate(certificate)


@router.get("/by-student/{student_id}", response_model=list[CertificatePublic])
async def list_certificates_for_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.certificates.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CertificateService(db)
    certificates = await service.list_for_student(student_id, organization_id)
    return [CertificatePublic.model_validate(c) for c in certificates]


@router.get("/verify/{certificate_number}", response_model=CertificateVerificationResponse)
async def verify_certificate(certificate_number: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint — no authentication required, for third-party verification."""
    service = CertificateService(db)
    return await service.verify(certificate_number)
