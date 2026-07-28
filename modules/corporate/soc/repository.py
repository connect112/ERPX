import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.soc.models import IncidentStatus, SOCIncident, SOCService, SOCServiceStatus


class SOCServiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> SOCService:
        service = SOCService(**fields)
        self.db.add(service)
        await self.db.flush()
        await self.db.refresh(service)
        return service

    async def get_by_id(self, soc_service_id: uuid.UUID) -> SOCService | None:
        result = await self.db.execute(select(SOCService).where(SOCService.id == soc_service_id))
        return result.scalar_one_or_none()

    async def list_for_client(self, client_id: uuid.UUID, status: SOCServiceStatus | None = None) -> list[SOCService]:
        conditions = [SOCService.client_id == client_id]
        if status is not None:
            conditions.append(SOCService.status == status)
        result = await self.db.execute(select(SOCService).where(*conditions).order_by(SOCService.start_date.desc()))
        return list(result.scalars().all())

    async def update(self, service: SOCService, **fields) -> SOCService:
        for key, value in fields.items():
            if value is not None:
                setattr(service, key, value)
        await self.db.flush()
        await self.db.refresh(service)
        return service


class SOCIncidentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> SOCIncident:
        incident = SOCIncident(**fields)
        self.db.add(incident)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def get_by_id(self, incident_id: uuid.UUID) -> SOCIncident | None:
        result = await self.db.execute(select(SOCIncident).where(SOCIncident.id == incident_id))
        return result.scalar_one_or_none()

    async def list_for_service(
        self, soc_service_id: uuid.UUID, status: IncidentStatus | None = None
    ) -> list[SOCIncident]:
        conditions = [SOCIncident.soc_service_id == soc_service_id]
        if status is not None:
            conditions.append(SOCIncident.status == status)
        result = await self.db.execute(
            select(SOCIncident).where(*conditions).order_by(SOCIncident.detected_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, incident: SOCIncident, **fields) -> SOCIncident:
        for key, value in fields.items():
            if value is not None:
                setattr(incident, key, value)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident
