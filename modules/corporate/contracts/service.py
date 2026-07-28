import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.contracts.models import Contract, ContractStatus
from modules.corporate.contracts.repository import ContractRepository
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.quotations.repository import QuotationRepository

logger = get_logger(__name__)

_EDITABLE_STATUSES = {ContractStatus.DRAFT}
_TERMINAL_STATUSES = {ContractStatus.TERMINATED, ContractStatus.RENEWED}


class ContractService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ContractRepository(db)
        self.client_repo = ClientRepository(db)
        self.project_repo = ProjectRepository(db)
        self.quotation_repo = QuotationRepository(db)

    async def create_contract(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID,
        contract_number: str,
        project_id: uuid.UUID | None = None,
        quotation_id: uuid.UUID | None = None,
        **fields,
    ) -> Contract:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        if project_id is not None:
            project = await self.project_repo.get_by_id(project_id, organization_id)
            if not project:
                raise NotFoundError("Project", project_id)
        if quotation_id is not None:
            quotation = await self.quotation_repo.get_by_id(quotation_id, organization_id)
            if not quotation:
                raise NotFoundError("Quotation", quotation_id)

        existing = await self.repo.get_by_number(organization_id, contract_number)
        if existing:
            raise ConflictError(f"A contract with number '{contract_number}' already exists.")

        contract = await self.repo.create(
            organization_id=organization_id,
            client_id=client_id,
            project_id=project_id,
            quotation_id=quotation_id,
            contract_number=contract_number,
            **fields,
        )
        logger.info("contract_created", contract_id=str(contract.id), contract_number=contract_number)
        return contract

    async def get_contract(self, contract_id: uuid.UUID, organization_id: uuid.UUID) -> Contract:
        contract = await self.repo.get_by_id(contract_id, organization_id)
        if not contract:
            raise NotFoundError("Contract", contract_id)
        return contract

    async def list_contracts(self, organization_id: uuid.UUID, **filters) -> tuple[list[Contract], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_expiring_contracts(self, organization_id: uuid.UUID, within_days: int = 30) -> list[Contract]:
        return await self.repo.list_expiring(organization_id, within_days)

    async def update_contract(self, contract_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Contract:
        contract = await self.get_contract(contract_id, organization_id)
        if contract.status not in _EDITABLE_STATUSES:
            raise ValidationError("Only draft contracts can be edited.")
        updated = await self.repo.update(contract, **fields)
        logger.info("contract_updated", contract_id=str(contract_id))
        return updated

    async def activate_contract(self, contract_id: uuid.UUID, organization_id: uuid.UUID, signed_date) -> Contract:
        contract = await self.get_contract(contract_id, organization_id)
        if contract.status != ContractStatus.DRAFT:
            raise ValidationError(f"Only draft contracts can be activated (this one is '{contract.status.value}').")
        updated = await self.repo.update(contract, status=ContractStatus.ACTIVE, signed_date=signed_date)
        logger.info("contract_activated", contract_id=str(contract_id))
        return updated

    async def terminate_contract(self, contract_id: uuid.UUID, organization_id: uuid.UUID) -> Contract:
        contract = await self.get_contract(contract_id, organization_id)
        if contract.status != ContractStatus.ACTIVE:
            raise ValidationError("Only active contracts can be terminated.")
        updated = await self.repo.update(contract, status=ContractStatus.TERMINATED)
        logger.info("contract_terminated", contract_id=str(contract_id))
        return updated

    async def renew_contract(
        self, contract_id: uuid.UUID, organization_id: uuid.UUID, new_end_date, new_contract_value: float | None = None
    ) -> Contract:
        """Extends the existing contract in place rather than spawning a new row/number."""
        contract = await self.get_contract(contract_id, organization_id)
        if contract.status != ContractStatus.ACTIVE:
            raise ValidationError("Only active contracts can be renewed.")
        if new_end_date <= (contract.end_date or contract.start_date):
            raise ValidationError("The new end date must be after the contract's current end date.")

        fields = {"end_date": new_end_date}
        if new_contract_value is not None:
            fields["contract_value"] = new_contract_value
        updated = await self.repo.update(contract, **fields)
        logger.info("contract_renewed", contract_id=str(contract_id), new_end_date=str(new_end_date))
        return updated

    async def mark_expired(self, contract_id: uuid.UUID, organization_id: uuid.UUID) -> Contract:
        contract = await self.get_contract(contract_id, organization_id)
        if contract.status != ContractStatus.ACTIVE:
            raise ValidationError("Only active contracts can be marked expired.")
        updated = await self.repo.update(contract, status=ContractStatus.EXPIRED)
        logger.info("contract_expired", contract_id=str(contract_id))
        return updated
