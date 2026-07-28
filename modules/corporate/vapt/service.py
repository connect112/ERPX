import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.vapt.models import FindingSeverity, FindingStatus, VAPTEngagement, VAPTFinding
from modules.corporate.vapt.repository import VAPTEngagementRepository, VAPTFindingRepository

logger = get_logger(__name__)

_OPEN_FINDING_STATUSES = {FindingStatus.OPEN, FindingStatus.RETESTING}


class VAPTEngagementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = VAPTEngagementRepository(db)
        self.project_repo = ProjectRepository(db)

    async def create_engagement(self, organization_id: uuid.UUID, project_id: uuid.UUID, **fields) -> VAPTEngagement:
        project = await self.project_repo.get_by_id(project_id, organization_id)
        if not project:
            raise NotFoundError("Project", project_id)
        engagement = await self.repo.create(project_id=project_id, **fields)
        logger.info("vapt_engagement_created", engagement_id=str(engagement.id), project_id=str(project_id))
        return engagement

    async def get_engagement(self, engagement_id: uuid.UUID, organization_id: uuid.UUID) -> VAPTEngagement:
        engagement = await self.repo.get_by_id(engagement_id)
        if not engagement:
            raise NotFoundError("VAPT engagement", engagement_id)
        project = await self.project_repo.get_by_id(engagement.project_id, organization_id)
        if not project:
            raise NotFoundError("VAPT engagement", engagement_id)
        return engagement

    async def list_for_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> list[VAPTEngagement]:
        project = await self.project_repo.get_by_id(project_id, organization_id)
        if not project:
            raise NotFoundError("Project", project_id)
        return await self.repo.list_for_project(project_id)

    async def update_engagement(
        self, engagement_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> VAPTEngagement:
        engagement = await self.get_engagement(engagement_id, organization_id)
        updated = await self.repo.update(engagement, **fields)
        logger.info("vapt_engagement_updated", engagement_id=str(engagement_id))
        return updated


class VAPTFindingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = VAPTFindingRepository(db)
        self.engagement_service = VAPTEngagementService(db)

    async def create_finding(
        self, engagement_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> VAPTFinding:
        await self.engagement_service.get_engagement(engagement_id, organization_id)
        finding = await self.repo.create(engagement_id=engagement_id, **fields)
        logger.info("vapt_finding_created", finding_id=str(finding.id), engagement_id=str(engagement_id))
        return finding

    async def get_finding(self, finding_id: uuid.UUID) -> VAPTFinding:
        finding = await self.repo.get_by_id(finding_id)
        if not finding:
            raise NotFoundError("VAPT finding", finding_id)
        return finding

    async def list_findings(
        self, engagement_id: uuid.UUID, organization_id: uuid.UUID, status: FindingStatus | None = None
    ) -> list[VAPTFinding]:
        await self.engagement_service.get_engagement(engagement_id, organization_id)
        return await self.repo.list_for_engagement(engagement_id, status)

    async def update_finding(self, finding_id: uuid.UUID, **fields) -> VAPTFinding:
        finding = await self.get_finding(finding_id)
        if fields.get("status") in (FindingStatus.FIXED, FindingStatus.ACCEPTED_RISK, FindingStatus.FALSE_POSITIVE):
            if fields.get("closed_date") is None and finding.closed_date is None:
                raise ValidationError("A closed_date is required when closing a finding.")
        updated = await self.repo.update(finding, **fields)
        logger.info("vapt_finding_updated", finding_id=str(finding_id))
        return updated

    async def get_summary(self, engagement_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
        findings = await self.list_findings(engagement_id, organization_id)
        by_severity = {severity.value: 0 for severity in FindingSeverity}
        open_count = 0
        for finding in findings:
            by_severity[finding.severity.value] += 1
            if finding.status in _OPEN_FINDING_STATUSES:
                open_count += 1
        return {
            "engagement_id": engagement_id,
            "total_findings": len(findings),
            "open_findings": open_count,
            "by_severity": by_severity,
        }
