import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.pentrix.certifications.models import PentrixCertification
from modules.pentrix.certifications.repository import CertificationRepository
from modules.pentrix.certifications.schemas import CertificationVerificationResponse
from modules.pentrix.leaderboard.service import LeaderboardService
from modules.students.models import Student
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


def _generate_certificate_number() -> str:
    return f"ERPX-PENTRIX-{secrets.token_hex(6).upper()}"


class CertificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CertificationRepository(db)
        self.student_repo = StudentRepository(db)
        self.leaderboard_service = LeaderboardService(db)

    async def issue_certification(
        self,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        track_name: str,
        minimum_points: int,
        force: bool,
    ) -> PentrixCertification:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.repo.get_by_student_and_track(student_id, track_name)
        if existing:
            raise ConflictError(
                f"A certification for track '{track_name}' already exists for this student."
            )

        leaderboard = await self.leaderboard_service.get_leaderboard(organization_id, limit=10_000)
        entry = next((e for e in leaderboard if e.student_id == student_id), None)
        current_points = entry.net_score if entry else 0

        if not force and current_points < minimum_points:
            raise ValidationError(
                f"Student has {current_points} net points, below the required {minimum_points} "
                f"for '{track_name}' (or pass force=true)."
            )

        cert = await self.repo.create(
            student_id=student_id,
            track_name=track_name,
            certificate_number=_generate_certificate_number(),
            points_at_issuance=current_points,
        )
        logger.info("pentrix_certification_issued", certificate_id=str(cert.id))
        return cert

    async def list_for_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[PentrixCertification]:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.repo.list_for_student(student_id)

    async def verify(self, certificate_number: str) -> CertificationVerificationResponse:
        """Public verification — no organization scoping, same as LMS certificates."""
        cert = await self.repo.get_by_number(certificate_number)
        if not cert:
            return CertificationVerificationResponse(valid=False, certificate_number=certificate_number)

        student_result = await self.db.execute(select(Student).where(Student.id == cert.student_id))
        student = student_result.scalar_one_or_none()

        return CertificationVerificationResponse(
            valid=True,
            certificate_number=cert.certificate_number,
            student_name=student.full_name if student else None,
            track_name=cert.track_name,
            points_at_issuance=cert.points_at_issuance,
            issued_at=cert.issued_at,
        )
