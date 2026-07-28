import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.gst.service import GSTService
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.quotations.models import Quotation, QuotationStatus
from modules.corporate.quotations.repository import QuotationRepository

logger = get_logger(__name__)


async def _build_lines(gst_service: GSTService, organization_id: uuid.UUID, raw_lines: list[dict]) -> list[dict]:
    computed = []
    for line in raw_lines:
        line_subtotal = round(float(line["quantity"]) * float(line["unit_price"]), 2)
        tax_amount = 0.0
        if line.get("gst_rate_id") is not None:
            tax_result = await gst_service.compute_tax(
                organization_id, line_subtotal, line["gst_rate_id"], is_interstate=False
            )
            tax_amount = tax_result["total_tax"]
        computed.append(
            {
                "gst_rate_id": line.get("gst_rate_id"),
                "description": line["description"],
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
                "line_subtotal": line_subtotal,
                "tax_amount": tax_amount,
                "line_total": round(line_subtotal + tax_amount, 2),
            }
        )
    return computed


class QuotationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = QuotationRepository(db)
        self.client_repo = ClientRepository(db)
        self.project_repo = ProjectRepository(db)
        self.gst_service = GSTService(db)

    async def create_quotation(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID,
        quotation_number: str,
        lines: list[dict],
        project_id: uuid.UUID | None = None,
        **fields,
    ) -> Quotation:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        if project_id is not None:
            project = await self.project_repo.get_by_id(project_id, organization_id)
            if not project:
                raise NotFoundError("Project", project_id)

        existing = await self.repo.get_by_number(organization_id, quotation_number)
        if existing:
            raise ConflictError(f"A quotation with number '{quotation_number}' already exists.")

        computed_lines = await _build_lines(self.gst_service, organization_id, lines)
        subtotal_amount = round(sum(l["line_subtotal"] for l in computed_lines), 2)
        tax_amount = round(sum(l["tax_amount"] for l in computed_lines), 2)

        quotation = await self.repo.create(
            lines=computed_lines,
            organization_id=organization_id,
            client_id=client_id,
            project_id=project_id,
            quotation_number=quotation_number,
            subtotal_amount=subtotal_amount,
            tax_amount=tax_amount,
            total_amount=round(subtotal_amount + tax_amount, 2),
            **fields,
        )
        logger.info("quotation_created", quotation_id=str(quotation.id), quotation_number=quotation_number)
        return quotation

    async def get_quotation(self, quotation_id: uuid.UUID, organization_id: uuid.UUID) -> Quotation:
        quotation = await self.repo.get_by_id(quotation_id, organization_id)
        if not quotation:
            raise NotFoundError("Quotation", quotation_id)
        return quotation

    async def list_quotations(self, organization_id: uuid.UUID, **filters) -> tuple[list[Quotation], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_quotation(
        self, quotation_id: uuid.UUID, organization_id: uuid.UUID, lines: list[dict] | None = None, **fields
    ) -> Quotation:
        quotation = await self.get_quotation(quotation_id, organization_id)
        if quotation.status != QuotationStatus.DRAFT:
            raise ValidationError("Only draft quotations can be edited.")

        if lines is not None:
            computed_lines = await _build_lines(self.gst_service, organization_id, lines)
            await self.repo.replace_lines(quotation, computed_lines)
            fields["subtotal_amount"] = round(sum(l["line_subtotal"] for l in computed_lines), 2)
            fields["tax_amount"] = round(sum(l["tax_amount"] for l in computed_lines), 2)
            fields["total_amount"] = round(fields["subtotal_amount"] + fields["tax_amount"], 2)

        updated = await self.repo.update(quotation, **fields)
        logger.info("quotation_updated", quotation_id=str(quotation_id))
        return updated

    async def send_quotation(self, quotation_id: uuid.UUID, organization_id: uuid.UUID) -> Quotation:
        quotation = await self.get_quotation(quotation_id, organization_id)
        if quotation.status != QuotationStatus.DRAFT:
            raise ValidationError(f"Only draft quotations can be sent (this one is '{quotation.status.value}').")
        updated = await self.repo.update(quotation, status=QuotationStatus.SENT)
        logger.info("quotation_sent", quotation_id=str(quotation_id))
        return updated

    async def accept_quotation(self, quotation_id: uuid.UUID, organization_id: uuid.UUID) -> Quotation:
        quotation = await self.get_quotation(quotation_id, organization_id)
        if quotation.status != QuotationStatus.SENT:
            raise ValidationError(f"Only sent quotations can be accepted (this one is '{quotation.status.value}').")
        if quotation.valid_until < date.today():
            raise ValidationError("This quotation has expired and cannot be accepted.")
        updated = await self.repo.update(quotation, status=QuotationStatus.ACCEPTED)
        logger.info("quotation_accepted", quotation_id=str(quotation_id))
        return updated

    async def reject_quotation(
        self, quotation_id: uuid.UUID, organization_id: uuid.UUID, rejection_reason: str | None
    ) -> Quotation:
        quotation = await self.get_quotation(quotation_id, organization_id)
        if quotation.status != QuotationStatus.SENT:
            raise ValidationError(f"Only sent quotations can be rejected (this one is '{quotation.status.value}').")
        updated = await self.repo.update(
            quotation, status=QuotationStatus.REJECTED, rejection_reason=rejection_reason
        )
        logger.info("quotation_rejected", quotation_id=str(quotation_id))
        return updated

    async def expire_stale_quotations(self, organization_id: uuid.UUID) -> int:
        """Flip SENT quotations past their valid_until to EXPIRED. Intended to run daily via Celery beat."""
        quotations, _ = await self.repo.list_for_organization(
            organization_id, status=QuotationStatus.SENT, skip=0, limit=10_000
        )
        count = 0
        today = date.today()
        for quotation in quotations:
            if quotation.valid_until < today:
                await self.repo.update(quotation, status=QuotationStatus.EXPIRED)
                count += 1
        return count
