import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.audit.models import AuditAction, AuditLog
from modules.audit.repository import AuditLogRepository
from modules.authentication.models import User


class AuditLogService:
    """
    Read-only by design: `AuditLog` rows are written exclusively by
    `modules.audit.hooks`'s SQLAlchemy event listeners, never through this
    service — an audit trail that application code could also write to
    directly wouldn't be trustworthy as one.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuditLogRepository(db)

    async def list_logs(
        self,
        organization_id: uuid.UUID,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        action: AuditAction | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[AuditLog, User | None]], int]:
        return await self.repo.list_for_organization(
            organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            action=action,
            since=since,
            until=until,
            skip=skip,
            limit=limit,
        )

    async def get_log(self, log_id: uuid.UUID, organization_id: uuid.UUID) -> AuditLog:
        log = await self.repo.get_by_id(log_id, organization_id)
        if not log:
            raise NotFoundError("Audit log entry", log_id)
        return log

    async def list_entity_types(self, organization_id: uuid.UUID) -> list[str]:
        return await self.repo.list_distinct_entity_types(organization_id)
