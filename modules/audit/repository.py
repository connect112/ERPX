import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.audit.models import AuditAction, AuditLog
from modules.authentication.models import User


class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_organization(
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
        conditions = [AuditLog.organization_id == organization_id]
        if entity_type is not None:
            conditions.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            conditions.append(AuditLog.entity_id == entity_id)
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action is not None:
            conditions.append(AuditLog.action == action)
        if since is not None:
            conditions.append(AuditLog.created_at >= since)
        if until is not None:
            conditions.append(AuditLog.created_at <= until)

        count_result = await self.db.execute(
            select(func.count()).select_from(AuditLog).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AuditLog, User)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()], total

    async def get_by_id(self, log_id: uuid.UUID, organization_id: uuid.UUID) -> AuditLog | None:
        result = await self.db.execute(
            select(AuditLog).where(
                AuditLog.id == log_id, AuditLog.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_distinct_entity_types(self, organization_id: uuid.UUID) -> list[str]:
        result = await self.db.execute(
            select(AuditLog.entity_type)
            .where(AuditLog.organization_id == organization_id)
            .distinct()
            .order_by(AuditLog.entity_type)
        )
        return list(result.scalars().all())
