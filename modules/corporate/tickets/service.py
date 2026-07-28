import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.tickets.models import SupportTicket, TicketComment, TicketPriority, TicketStatus
from modules.corporate.tickets.repository import SupportTicketRepository, TicketCommentRepository

logger = get_logger(__name__)

_RESOLVED_STATUSES = {TicketStatus.RESOLVED, TicketStatus.CLOSED}


class SupportTicketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SupportTicketRepository(db)
        self.client_repo = ClientRepository(db)
        self.project_repo = ProjectRepository(db)

    async def create_ticket(
        self, organization_id: uuid.UUID, client_id: uuid.UUID, ticket_number: str, project_id: uuid.UUID | None = None, **fields
    ) -> SupportTicket:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        if project_id is not None:
            project = await self.project_repo.get_by_id(project_id, organization_id)
            if not project:
                raise NotFoundError("Project", project_id)

        existing = await self.repo.get_by_number(organization_id, ticket_number)
        if existing:
            raise ConflictError(f"A ticket with number '{ticket_number}' already exists.")

        ticket = await self.repo.create(
            organization_id=organization_id, client_id=client_id, project_id=project_id, ticket_number=ticket_number, **fields
        )
        logger.info("support_ticket_created", ticket_id=str(ticket.id))
        return ticket

    async def create_client_ticket(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID,
        subject: str,
        description: str,
        priority: TicketPriority,
        project_id: uuid.UUID | None = None,
        raised_by_contact_name: str | None = None,
    ) -> SupportTicket:
        """
        Client-portal self-service ticket creation: unlike `create_ticket`
        (staff supply their own `ticket_number`), a client contact doesn't
        know the organization's numbering scheme, so this generates one
        and retries on the rare concurrent-insert collision — same
        approach as `StudentRepository._next_student_code`.
        """
        if project_id is not None:
            project = await self.project_repo.get_by_id(project_id, organization_id)
            if not project or project.client_id != client_id:
                raise NotFoundError("Project", project_id)

        last_error: Exception | None = None
        for _ in range(5):
            count = (await self.repo.list_for_organization(organization_id, skip=0, limit=1))[1]
            ticket_number = f"TKT-{count + 1:05d}"
            try:
                ticket = await self.repo.create(
                    organization_id=organization_id,
                    client_id=client_id,
                    project_id=project_id,
                    ticket_number=ticket_number,
                    subject=subject,
                    description=description,
                    priority=priority,
                    raised_by_contact_name=raised_by_contact_name,
                )
                logger.info("support_ticket_created", ticket_id=str(ticket.id), self_service=True)
                return ticket
            except IntegrityError as exc:
                await self.db.rollback()
                last_error = exc
                continue
        raise last_error or ConflictError("Could not generate a unique ticket number.")

    async def get_ticket(self, ticket_id: uuid.UUID, organization_id: uuid.UUID) -> SupportTicket:
        ticket = await self.repo.get_by_id(ticket_id, organization_id)
        if not ticket:
            raise NotFoundError("Support ticket", ticket_id)
        return ticket

    async def list_tickets(self, organization_id: uuid.UUID, **filters) -> tuple[list[SupportTicket], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_overdue_tickets(self, organization_id: uuid.UUID) -> list[SupportTicket]:
        return await self.repo.list_overdue(organization_id)

    async def update_ticket(self, ticket_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> SupportTicket:
        ticket = await self.get_ticket(ticket_id, organization_id)
        updated = await self.repo.update(ticket, **fields)
        logger.info("support_ticket_updated", ticket_id=str(ticket_id))
        return updated

    async def change_status(self, ticket_id: uuid.UUID, organization_id: uuid.UUID, status: TicketStatus) -> SupportTicket:
        ticket = await self.get_ticket(ticket_id, organization_id)
        fields = {"status": status}
        if status in _RESOLVED_STATUSES and ticket.resolved_at is None:
            fields["resolved_at"] = datetime.now(timezone.utc)
        updated = await self.repo.update(ticket, **fields)
        logger.info("support_ticket_status_changed", ticket_id=str(ticket_id), status=status.value)
        return updated


class TicketCommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TicketCommentRepository(db)
        self.ticket_service = SupportTicketService(db)

    async def add_comment(
        self, ticket_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID | None = None, **fields
    ) -> TicketComment:
        await self.ticket_service.get_ticket(ticket_id, organization_id)
        comment = await self.repo.create(ticket_id=ticket_id, created_by_user_id=created_by_user_id, **fields)
        logger.info("ticket_comment_added", comment_id=str(comment.id), ticket_id=str(ticket_id))
        return comment

    async def list_comments(
        self, ticket_id: uuid.UUID, organization_id: uuid.UUID, include_internal: bool = True
    ) -> list[TicketComment]:
        await self.ticket_service.get_ticket(ticket_id, organization_id)
        return await self.repo.list_for_ticket(ticket_id, include_internal)
