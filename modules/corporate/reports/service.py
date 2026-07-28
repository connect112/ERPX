import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.corporate.amc.models import AMCStatus
from modules.corporate.amc.repository import AMCContractRepository
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.contracts.models import ContractStatus
from modules.corporate.contracts.repository import ContractRepository
from modules.corporate.projects.models import ProjectStatus
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.soc.models import SOCServiceStatus
from modules.corporate.soc.repository import SOCServiceRepository
from modules.corporate.tickets.models import TicketStatus
from modules.corporate.tickets.repository import SupportTicketRepository
from modules.corporate.vapt.models import FindingSeverity, FindingStatus
from modules.corporate.vapt.repository import VAPTEngagementRepository, VAPTFindingRepository

_OPEN_TICKET_STATUSES = {TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD}
_INACTIVE_PROJECT_STATUSES = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}
_OPEN_FINDING_STATUSES = {FindingStatus.OPEN, FindingStatus.RETESTING}


class CorporateReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client_repo = ClientRepository(db)
        self.project_repo = ProjectRepository(db)
        self.ticket_repo = SupportTicketRepository(db)
        self.amc_repo = AMCContractRepository(db)
        self.soc_repo = SOCServiceRepository(db)
        self.contract_repo = ContractRepository(db)
        self.engagement_repo = VAPTEngagementRepository(db)
        self.finding_repo = VAPTFindingRepository(db)

    async def client_summary(self, client_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)

        projects, total_projects = await self.project_repo.list_for_organization(
            organization_id, client_id=client_id, skip=0, limit=10_000
        )
        active_projects = sum(1 for p in projects if p.status not in _INACTIVE_PROJECT_STATUSES)

        tickets, _ = await self.ticket_repo.list_for_organization(
            organization_id, client_id=client_id, skip=0, limit=10_000
        )
        open_tickets = sum(1 for t in tickets if t.status in _OPEN_TICKET_STATUSES)

        amc_contracts, _ = await self.amc_repo.list_for_organization(
            organization_id, client_id=client_id, status=AMCStatus.ACTIVE, skip=0, limit=10_000
        )
        soc_services = await self.soc_repo.list_for_client(client_id, status=SOCServiceStatus.ACTIVE)

        contracts, _ = await self.contract_repo.list_for_organization(
            organization_id, client_id=client_id, status=ContractStatus.ACTIVE, skip=0, limit=10_000
        )
        active_contract_value = round(sum(float(c.contract_value) for c in contracts), 2)

        return {
            "client_id": client_id,
            "total_projects": total_projects,
            "active_projects": active_projects,
            "open_tickets": open_tickets,
            "active_amc_contracts": len(amc_contracts),
            "active_soc_services": len(soc_services),
            "active_contract_value": active_contract_value,
        }

    async def vapt_portfolio_summary(self, organization_id: uuid.UUID, as_of_date: date) -> dict:
        projects, _ = await self.project_repo.list_for_organization(organization_id, skip=0, limit=10_000)

        total_engagements = 0
        total_findings = 0
        open_findings = 0
        by_severity = {severity.value: 0 for severity in FindingSeverity}

        for project in projects:
            engagements = await self.engagement_repo.list_for_project(project.id)
            total_engagements += len(engagements)
            for engagement in engagements:
                findings = await self.finding_repo.list_for_engagement(engagement.id)
                total_findings += len(findings)
                for finding in findings:
                    by_severity[finding.severity.value] += 1
                    if finding.status in _OPEN_FINDING_STATUSES:
                        open_findings += 1

        return {
            "as_of_date": as_of_date,
            "total_engagements": total_engagements,
            "total_findings": total_findings,
            "open_findings": open_findings,
            "findings_by_severity": by_severity,
        }

    async def ticket_sla_summary(self, organization_id: uuid.UUID) -> dict:
        tickets, _ = await self.ticket_repo.list_for_organization(organization_id, skip=0, limit=10_000)
        open_tickets = [t for t in tickets if t.status in _OPEN_TICKET_STATUSES]
        overdue_tickets = await self.ticket_repo.list_overdue(organization_id)

        by_priority: dict[str, int] = {}
        for ticket in open_tickets:
            by_priority[ticket.priority.value] = by_priority.get(ticket.priority.value, 0) + 1

        return {
            "open_tickets": len(open_tickets),
            "overdue_tickets": len(overdue_tickets),
            "by_priority": by_priority,
        }
