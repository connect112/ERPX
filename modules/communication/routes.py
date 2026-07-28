import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.communication.models import CommunicationChannel, CommunicationStatus
from modules.communication.schemas import (
    CommunicationLogListResponse,
    CommunicationLogPublic,
    SendCommunicationRequest,
)
from modules.communication.service import CommunicationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/send", response_model=CommunicationLogPublic, status_code=status.HTTP_201_CREATED)
async def send_communication(
    payload: SendCommunicationRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("communication.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CommunicationService(db)
    log = await service.send_and_log(
        organization_id,
        payload.channel,
        payload.recipient,
        payload.body,
        subject=payload.subject,
        sent_by_user_id=user.id,
    )
    return CommunicationLogPublic.model_validate(log)


@router.get("/logs", response_model=CommunicationLogListResponse)
async def list_logs(
    channel: CommunicationChannel | None = Query(default=None),
    status_filter: CommunicationStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("communication.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CommunicationService(db)
    logs, total = await service.list_logs(
        organization_id, channel=channel, status=status_filter, skip=skip, limit=limit
    )
    return CommunicationLogListResponse(
        items=[CommunicationLogPublic.model_validate(log) for log in logs], total=total
    )


@router.get("/logs/{log_id}", response_model=CommunicationLogPublic)
async def get_log(
    log_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("communication.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CommunicationService(db)
    log = await service.get_log(log_id, organization_id)
    return CommunicationLogPublic.model_validate(log)
