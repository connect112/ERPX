import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.documents.service import DocumentService
from modules.employees.repository import EmployeeRepository
from modules.expense_claims.models import ExpenseClaim, ExpenseClaimStatus
from modules.expense_claims.repository import ExpenseClaimRepository

logger = get_logger(__name__)


class ExpenseClaimService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ExpenseClaimRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.document_service = DocumentService(db)

    async def request_receipt_upload(
        self,
        organization_id: uuid.UUID,
        employee_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        filename: str,
        content_type: str,
    ) -> tuple[uuid.UUID, str]:
        """Delegates to the shared Documents module for the actual
        presigned-URL/storage mechanics (see modules/documents/service.py)
        -- this method's only job is exposing it to an employee for their
        own receipt without the documents.manage permission Documents'
        own routes require, since no employee holds that."""
        document, upload_url = await self.document_service.request_upload(
            organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            entity_type="expense_claim",
            entity_id=employee_id,
            filename=filename,
            content_type=content_type,
        )
        return document.id, upload_url

    async def confirm_receipt_upload(self, organization_id: uuid.UUID, document_id: uuid.UUID) -> uuid.UUID:
        document = await self.document_service.confirm_upload(document_id, organization_id)
        return document.id

    async def submit_claim(
        self,
        organization_id: uuid.UUID,
        employee_id: uuid.UUID,
        description: str,
        amount: float,
        receipt_document_id: uuid.UUID | None,
    ) -> ExpenseClaim:
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")

        today = date.today()
        claim = await self.repo.create(
            organization_id=organization_id,
            employee_id=employee_id,
            description=description,
            amount=amount,
            receipt_document_id=receipt_document_id,
            period_year=today.year,
            period_month=today.month,
        )
        logger.info("expense_claim_submitted", claim_id=str(claim.id), employee_id=str(employee_id))
        return claim

    async def get_claim(self, claim_id: uuid.UUID, organization_id: uuid.UUID) -> ExpenseClaim:
        claim = await self.repo.get_by_id(claim_id, organization_id)
        if not claim:
            raise NotFoundError("Expense claim", claim_id)
        return claim

    async def list_for_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        return await self.repo.list_for_employee(employee_id, **filters)

    async def list_for_organization(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def approve_claim(
        self, claim_id: uuid.UUID, organization_id: uuid.UUID, reviewed_by_user_id: uuid.UUID
    ) -> ExpenseClaim:
        claim = await self.get_claim(claim_id, organization_id)
        if claim.status != ExpenseClaimStatus.PENDING:
            raise ValidationError(f"Only pending expense claims can be approved (this one is '{claim.status.value}').")
        updated = await self.repo.update(
            claim,
            status=ExpenseClaimStatus.APPROVED,
            reviewed_by_user_id=reviewed_by_user_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        logger.info("expense_claim_approved", claim_id=str(claim_id))
        return updated

    async def reject_claim(
        self, claim_id: uuid.UUID, organization_id: uuid.UUID, reviewed_by_user_id: uuid.UUID, rejection_reason: str
    ) -> ExpenseClaim:
        claim = await self.get_claim(claim_id, organization_id)
        if claim.status != ExpenseClaimStatus.PENDING:
            raise ValidationError(f"Only pending expense claims can be rejected (this one is '{claim.status.value}').")
        updated = await self.repo.update(
            claim,
            status=ExpenseClaimStatus.REJECTED,
            rejection_reason=rejection_reason,
            reviewed_by_user_id=reviewed_by_user_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        logger.info("expense_claim_rejected", claim_id=str(claim_id))
        return updated
