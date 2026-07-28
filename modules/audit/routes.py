import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.audit.models import AuditAction
from modules.audit.schemas import AuditLogListResponse, AuditLogPublic
from modules.audit.service import AuditLogService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


def _to_public(row) -> AuditLogPublic:
    log, log_user = row
    return AuditLogPublic(
        id=log.id,
        organization_id=log.organization_id,
        user_id=log.user_id,
        user_email=log_user.email if log_user else None,
        user_full_name=log_user.full_name if log_user else None,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        changes=log.changes,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        request_id=log.request_id,
        created_at=log.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditLogService(db)
    rows, total = await service.list_logs(
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
    return AuditLogListResponse(items=[_to_public(row) for row in rows], total=total)


@router.get("/entity-types", response_model=list[str])
async def list_audit_entity_types(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditLogService(db)
    return await service.list_entity_types(organization_id)


@router.get("/{log_id}", response_model=AuditLogPublic)
async def get_audit_log(
    log_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditLogService(db)
    log = await service.get_log(log_id, organization_id)
    return _to_public((log, None))
