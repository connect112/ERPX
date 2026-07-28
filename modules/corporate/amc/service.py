import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.corporate.amc.models import AMCContract, AMCStatus, AMCVisit, AMCVisitStatus
from modules.corporate.amc.repository import AMCContractRepository, AMCVisitRepository
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.contracts.repository import ContractRepository

logger = get_logger(__name__)


class AMCContractService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AMCContractRepository(db)
        self.client_repo = ClientRepository(db)
        self.contract_repo = ContractRepository(db)

    async def create_amc_contract(
        self, organization_id: uuid.UUID, client_id: uuid.UUID, amc_number: str, contract_id: uuid.UUID | None = None, **fields
    ) -> AMCContract:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        if contract_id is not None:
            contract = await self.contract_repo.get_by_id(contract_id, organization_id)
            if not contract:
                raise NotFoundError("Contract", contract_id)

        existing = await self.repo.get_by_number(organization_id, amc_number)
        if existing:
            raise ConflictError(f"An AMC contract with number '{amc_number}' already exists.")

        amc = await self.repo.create(
            organization_id=organization_id, client_id=client_id, contract_id=contract_id, amc_number=amc_number, **fields
        )
        logger.info("amc_contract_created", amc_contract_id=str(amc.id))
        return amc

    async def get_amc_contract(self, amc_contract_id: uuid.UUID, organization_id: uuid.UUID) -> AMCContract:
        amc = await self.repo.get_by_id(amc_contract_id, organization_id)
        if not amc:
            raise NotFoundError("AMC contract", amc_contract_id)
        return amc

    async def list_amc_contracts(self, organization_id: uuid.UUID, **filters) -> tuple[list[AMCContract], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_due_for_renewal(self, organization_id: uuid.UUID) -> list[AMCContract]:
        return await self.repo.list_due_for_renewal(organization_id)

    async def update_amc_contract(
        self, amc_contract_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> AMCContract:
        amc = await self.get_amc_contract(amc_contract_id, organization_id)
        updated = await self.repo.update(amc, **fields)
        logger.info("amc_contract_updated", amc_contract_id=str(amc_contract_id))
        return updated


class AMCVisitService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AMCVisitRepository(db)
        self.contract_service = AMCContractService(db)

    async def schedule_visit(
        self, amc_contract_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> AMCVisit:
        await self.contract_service.get_amc_contract(amc_contract_id, organization_id)
        visit = await self.repo.create(amc_contract_id=amc_contract_id, **fields)
        logger.info("amc_visit_scheduled", visit_id=str(visit.id), amc_contract_id=str(amc_contract_id))
        return visit

    async def get_visit(self, visit_id: uuid.UUID) -> AMCVisit:
        visit = await self.repo.get_by_id(visit_id)
        if not visit:
            raise NotFoundError("AMC visit", visit_id)
        return visit

    async def list_visits(
        self, amc_contract_id: uuid.UUID, organization_id: uuid.UUID, status: AMCVisitStatus | None = None
    ) -> list[AMCVisit]:
        await self.contract_service.get_amc_contract(amc_contract_id, organization_id)
        return await self.repo.list_for_contract(amc_contract_id, status)

    async def complete_visit(self, visit_id: uuid.UUID, findings: str) -> AMCVisit:
        visit = await self.get_visit(visit_id)
        if visit.status != AMCVisitStatus.SCHEDULED:
            raise ValidationError(f"Only scheduled visits can be completed (this one is '{visit.status.value}').")
        updated = await self.repo.update(visit, status=AMCVisitStatus.COMPLETED, findings=findings)
        logger.info("amc_visit_completed", visit_id=str(visit_id))
        return updated

    async def cancel_visit(self, visit_id: uuid.UUID) -> AMCVisit:
        visit = await self.get_visit(visit_id)
        if visit.status != AMCVisitStatus.SCHEDULED:
            raise ValidationError(f"Only scheduled visits can be cancelled (this one is '{visit.status.value}').")
        updated = await self.repo.update(visit, status=AMCVisitStatus.CANCELLED)
        logger.info("amc_visit_cancelled", visit_id=str(visit_id))
        return updated
