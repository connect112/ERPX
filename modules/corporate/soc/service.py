import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.soc.models import IncidentStatus, SOCIncident, SOCService
from modules.corporate.soc.repository import SOCIncidentRepository, SOCServiceRepository

logger = get_logger(__name__)

_RESOLVED_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}


class SOCServiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SOCServiceRepository(db)
        self.client_repo = ClientRepository(db)
        self.project_repo = ProjectRepository(db)

    async def create_service(
        self, organization_id: uuid.UUID, client_id: uuid.UUID, project_id: uuid.UUID | None = None, **fields
    ) -> SOCService:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        if project_id is not None:
            project = await self.project_repo.get_by_id(project_id, organization_id)
            if not project:
                raise NotFoundError("Project", project_id)

        service = await self.repo.create(client_id=client_id, project_id=project_id, **fields)
        logger.info("soc_service_created", soc_service_id=str(service.id), client_id=str(client_id))
        return service

    async def get_service(self, soc_service_id: uuid.UUID, organization_id: uuid.UUID) -> SOCService:
        service = await self.repo.get_by_id(soc_service_id)
        if not service:
            raise NotFoundError("SOC service", soc_service_id)
        client = await self.client_repo.get_by_id(service.client_id, organization_id)
        if not client:
            raise NotFoundError("SOC service", soc_service_id)
        return service

    async def list_for_client(self, client_id: uuid.UUID, organization_id: uuid.UUID, **filters) -> list[SOCService]:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        return await self.repo.list_for_client(client_id, **filters)

    async def update_service(self, soc_service_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> SOCService:
        service = await self.get_service(soc_service_id, organization_id)
        updated = await self.repo.update(service, **fields)
        logger.info("soc_service_updated", soc_service_id=str(soc_service_id))
        return updated


class SOCIncidentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SOCIncidentRepository(db)
        self.service_service = SOCServiceService(db)

    async def create_incident(
        self, soc_service_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> SOCIncident:
        await self.service_service.get_service(soc_service_id, organization_id)
        incident = await self.repo.create(soc_service_id=soc_service_id, **fields)
        logger.info("soc_incident_created", incident_id=str(incident.id), soc_service_id=str(soc_service_id))
        return incident

    async def get_incident(self, incident_id: uuid.UUID) -> SOCIncident:
        incident = await self.repo.get_by_id(incident_id)
        if not incident:
            raise NotFoundError("SOC incident", incident_id)
        return incident

    async def list_incidents(
        self, soc_service_id: uuid.UUID, organization_id: uuid.UUID, status: IncidentStatus | None = None
    ) -> list[SOCIncident]:
        await self.service_service.get_service(soc_service_id, organization_id)
        return await self.repo.list_for_service(soc_service_id, status)

    async def update_incident(self, incident_id: uuid.UUID, **fields) -> SOCIncident:
        incident = await self.get_incident(incident_id)
        if fields.get("status") in _RESOLVED_STATUSES and fields.get("resolved_at") is None and incident.resolved_at is None:
            fields["resolved_at"] = datetime.now(timezone.utc)
        updated = await self.repo.update(incident, **fields)
        logger.info("soc_incident_updated", incident_id=str(incident_id))
        return updated
