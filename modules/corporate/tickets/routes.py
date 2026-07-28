import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.clients.dependencies import get_current_client
from modules.corporate.clients.models import Client
from modules.corporate.tickets.models import SupportTicket, TicketPriority, TicketStatus
from modules.corporate.tickets.schemas import (
    ClientTicketCommentCreateRequest,
    ClientTicketCreateRequest,
    MessageResponse,
    SupportTicketCreateRequest,
    SupportTicketPublic,
    SupportTicketStatusChangeRequest,
    SupportTicketUpdateRequest,
    TicketCommentCreateRequest,
    TicketCommentPublic,
)
from modules.corporate.tickets.service import SupportTicketService, TicketCommentService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


def _require_owns_ticket(ticket: SupportTicket, client: Client) -> None:
    if ticket.client_id != client.id:
        raise AuthorizationError("This ticket does not belong to your organization.")


@router.get("/me", response_model=list[SupportTicketPublic])
async def list_my_tickets(
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    tickets, _total = await service.list_tickets(
        client.organization_id, client_id=client.id, skip=0, limit=200
    )
    return [SupportTicketPublic.model_validate(t) for t in tickets]


@router.post("/me", response_model=SupportTicketPublic, status_code=status.HTTP_201_CREATED)
async def create_my_ticket(
    payload: ClientTicketCreateRequest,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    ticket = await service.create_client_ticket(client.organization_id, client.id, **payload.model_dump())
    return SupportTicketPublic.model_validate(ticket)


@router.get("/me/{ticket_id}", response_model=SupportTicketPublic)
async def get_my_ticket(
    ticket_id: uuid.UUID,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    ticket = await service.get_ticket(ticket_id, client.organization_id)
    _require_owns_ticket(ticket, client)
    return SupportTicketPublic.model_validate(ticket)


@router.get("/me/{ticket_id}/comments", response_model=list[TicketCommentPublic])
async def list_my_ticket_comments(
    ticket_id: uuid.UUID,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    ticket_service = SupportTicketService(db)
    ticket = await ticket_service.get_ticket(ticket_id, client.organization_id)
    _require_owns_ticket(ticket, client)
    comment_service = TicketCommentService(db)
    comments = await comment_service.list_comments(ticket_id, client.organization_id, include_internal=False)
    return [TicketCommentPublic.model_validate(c) for c in comments]


@router.post(
    "/me/{ticket_id}/comments", response_model=TicketCommentPublic, status_code=status.HTTP_201_CREATED
)
async def add_my_ticket_comment(
    ticket_id: uuid.UUID,
    payload: ClientTicketCommentCreateRequest,
    client: Client = Depends(get_current_client),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    ticket_service = SupportTicketService(db)
    ticket = await ticket_service.get_ticket(ticket_id, client.organization_id)
    _require_owns_ticket(ticket, client)
    comment_service = TicketCommentService(db)
    comment = await comment_service.add_comment(
        ticket_id,
        client.organization_id,
        created_by_user_id=user.id,
        comment_text=payload.comment_text,
        is_internal=False,
    )
    return TicketCommentPublic.model_validate(comment)


@router.post("", response_model=SupportTicketPublic, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: SupportTicketCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    ticket = await service.create_ticket(organization_id, **payload.model_dump())
    return SupportTicketPublic.model_validate(ticket)


@router.get("", response_model=dict)
async def list_tickets(
    client_id: uuid.UUID | None = None,
    priority: TicketPriority | None = None,
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    assigned_to_employee_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    tickets, total = await service.list_tickets(
        organization_id,
        client_id=client_id,
        priority=priority,
        status=status_filter,
        assigned_to_employee_id=assigned_to_employee_id,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [SupportTicketPublic.model_validate(t) for t in tickets],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/overdue", response_model=list[SupportTicketPublic])
async def list_overdue_tickets(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    tickets = await service.list_overdue_tickets(organization_id)
    return [SupportTicketPublic.model_validate(t) for t in tickets]


@router.get("/{ticket_id}", response_model=SupportTicketPublic)
async def get_ticket(
    ticket_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    ticket = await service.get_ticket(ticket_id, organization_id)
    return SupportTicketPublic.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=SupportTicketPublic)
async def update_ticket(
    ticket_id: uuid.UUID,
    payload: SupportTicketUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    ticket = await service.update_ticket(ticket_id, organization_id, **payload.model_dump(exclude_unset=True))
    return SupportTicketPublic.model_validate(ticket)


@router.post("/{ticket_id}/status", response_model=SupportTicketPublic)
async def change_ticket_status(
    ticket_id: uuid.UUID,
    payload: SupportTicketStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SupportTicketService(db)
    ticket = await service.change_status(ticket_id, organization_id, payload.status)
    return SupportTicketPublic.model_validate(ticket)


@router.post("/{ticket_id}/comments", response_model=TicketCommentPublic, status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_id: uuid.UUID,
    payload: TicketCommentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TicketCommentService(db)
    comment = await service.add_comment(ticket_id, organization_id, created_by_user_id=user.id, **payload.model_dump())
    return TicketCommentPublic.model_validate(comment)


@router.get("/{ticket_id}/comments", response_model=list[TicketCommentPublic])
async def list_comments(
    ticket_id: uuid.UUID,
    include_internal: bool = Query(default=True),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.tickets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TicketCommentService(db)
    comments = await service.list_comments(ticket_id, organization_id, include_internal)
    return [TicketCommentPublic.model_validate(c) for c in comments]
