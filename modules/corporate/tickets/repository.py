import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.corporate.tickets.models import SupportTicket, TicketComment, TicketPriority, TicketStatus


class SupportTicketRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> SupportTicket:
        ticket = SupportTicket(**fields)
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def get_by_id(self, ticket_id: uuid.UUID, organization_id: uuid.UUID) -> SupportTicket | None:
        result = await self.db.execute(
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id, SupportTicket.organization_id == organization_id)
            .options(selectinload(SupportTicket.comments))
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, ticket_number: str) -> SupportTicket | None:
        result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.organization_id == organization_id, SupportTicket.ticket_number == ticket_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
        assigned_to_employee_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[SupportTicket], int]:
        conditions = [SupportTicket.organization_id == organization_id]
        if client_id is not None:
            conditions.append(SupportTicket.client_id == client_id)
        if priority is not None:
            conditions.append(SupportTicket.priority == priority)
        if status is not None:
            conditions.append(SupportTicket.status == status)
        if assigned_to_employee_id is not None:
            conditions.append(SupportTicket.assigned_to_employee_id == assigned_to_employee_id)

        count_result = await self.db.execute(select(func.count()).select_from(SupportTicket).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(SupportTicket)
            .where(*conditions)
            .order_by(SupportTicket.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_overdue(self, organization_id: uuid.UUID) -> list[SupportTicket]:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.organization_id == organization_id,
                SupportTicket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
                SupportTicket.sla_due_at.is_not(None),
                SupportTicket.sla_due_at < now,
            )
        )
        return list(result.scalars().all())

    async def update(self, ticket: SupportTicket, **fields) -> SupportTicket:
        for key, value in fields.items():
            if value is not None:
                setattr(ticket, key, value)
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket


class TicketCommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> TicketComment:
        comment = TicketComment(**fields)
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def list_for_ticket(self, ticket_id: uuid.UUID, include_internal: bool = True) -> list[TicketComment]:
        conditions = [TicketComment.ticket_id == ticket_id]
        if not include_internal:
            conditions.append(TicketComment.is_internal.is_(False))
        result = await self.db.execute(
            select(TicketComment).where(*conditions).order_by(TicketComment.created_at.asc())
        )
        return list(result.scalars().all())
