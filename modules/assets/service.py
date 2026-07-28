import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService
from modules.accounting.ledger.repository import AccountRepository
from modules.assets.models import (
    Asset,
    AssetCategory,
    AssetStatus,
    DepreciationEntry,
    DepreciationMethod,
    DepreciationRun,
    DepreciationRunStatus,
)
from modules.assets.repository import (
    AssetCategoryRepository,
    AssetRepository,
    DepreciationEntryRepository,
    DepreciationRunRepository,
)
from modules.employees.repository import EmployeeRepository

logger = get_logger(__name__)


class AssetCategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssetCategoryRepository(db)

    async def create_category(self, organization_id: uuid.UUID, code: str, **fields) -> AssetCategory:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"An asset category with code '{code}' already exists.")
        category = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("asset_category_created", category_id=str(category.id))
        return category

    async def get_category(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> AssetCategory:
        category = await self.repo.get_by_id(category_id, organization_id)
        if not category:
            raise NotFoundError("Asset category", category_id)
        return category

    async def list_categories(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[AssetCategory]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_category(self, category_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> AssetCategory:
        category = await self.get_category(category_id, organization_id)
        updated = await self.repo.update(category, **fields)
        logger.info("asset_category_updated", category_id=str(category_id))
        return updated


def _monthly_depreciation(
    method: DepreciationMethod,
    purchase_cost: float,
    salvage_value: float,
    useful_life_years: int,
    accumulated_so_far: float,
) -> float:
    depreciable_base = purchase_cost - salvage_value
    remaining = round(depreciable_base - accumulated_so_far, 2)
    if remaining <= 0:
        return 0.0

    if method == DepreciationMethod.STRAIGHT_LINE:
        monthly = depreciable_base / useful_life_years / 12
    else:  # DECLINING_BALANCE
        net_book_value_before = purchase_cost - accumulated_so_far
        annual_rate = 1 / useful_life_years
        monthly = net_book_value_before * (annual_rate / 12)

    return round(min(monthly, remaining), 2)


class AssetService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssetRepository(db)
        self.category_repo = AssetCategoryRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.account_repo = AccountRepository(db)
        self.entry_repo = DepreciationEntryRepository(db)

    async def _validate_accounts(self, organization_id: uuid.UUID, *account_ids: uuid.UUID) -> None:
        for account_id in account_ids:
            account = await self.account_repo.get_by_id(account_id, organization_id)
            if not account:
                raise NotFoundError("GL account", account_id)

    async def create_asset(
        self, organization_id: uuid.UUID, asset_code: str, category_id: uuid.UUID | None, **fields
    ) -> Asset:
        existing = await self.repo.get_by_code(organization_id, asset_code)
        if existing:
            raise ConflictError(f"An asset with code '{asset_code}' already exists.")
        if category_id is not None:
            category = await self.category_repo.get_by_id(category_id, organization_id)
            if not category:
                raise NotFoundError("Asset category", category_id)
        if fields.get("assigned_to_employee_id") is not None:
            employee = await self.employee_repo.get_by_id(fields["assigned_to_employee_id"], organization_id)
            if not employee:
                raise NotFoundError("Employee", fields["assigned_to_employee_id"])

        await self._validate_accounts(
            organization_id,
            fields["asset_account_id"],
            fields["accumulated_depreciation_account_id"],
            fields["depreciation_expense_account_id"],
        )

        asset = await self.repo.create(organization_id=organization_id, asset_code=asset_code, category_id=category_id, **fields)
        logger.info("asset_created", asset_id=str(asset.id), asset_code=asset_code)
        return asset

    async def get_asset(self, asset_id: uuid.UUID, organization_id: uuid.UUID) -> Asset:
        asset = await self.repo.get_by_id(asset_id, organization_id)
        if not asset:
            raise NotFoundError("Asset", asset_id)
        return asset

    async def list_assets(self, organization_id: uuid.UUID, **filters) -> tuple[list[Asset], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_asset(self, asset_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Asset:
        asset = await self.get_asset(asset_id, organization_id)
        if asset.status == AssetStatus.DISPOSED:
            raise ValidationError("A disposed asset cannot be edited.")
        updated = await self.repo.update(asset, **fields)
        logger.info("asset_updated", asset_id=str(asset_id))
        return updated

    async def get_net_book_value(
        self, asset_id: uuid.UUID, organization_id: uuid.UUID, as_of_date: date | None = None
    ) -> dict:
        asset = await self.get_asset(asset_id, organization_id)
        as_of = as_of_date or datetime.now(timezone.utc).date()
        accumulated = await self.entry_repo.sum_posted_for_asset(asset_id, as_of.year, as_of.month)
        return {
            "asset_id": asset_id,
            "as_of_date": as_of,
            "purchase_cost": float(asset.purchase_cost),
            "accumulated_depreciation": round(accumulated, 2),
            "net_book_value": round(float(asset.purchase_cost) - accumulated, 2),
        }


class DepreciationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.run_repo = DepreciationRunRepository(db)
        self.entry_repo = DepreciationEntryRepository(db)
        self.asset_repo = AssetRepository(db)
        self.journal_service = JournalService(db)

    async def generate_run(
        self,
        organization_id: uuid.UUID,
        period_year: int,
        period_month: int,
        run_date: date,
        created_by_user_id: uuid.UUID | None = None,
    ) -> tuple[DepreciationRun, int, list[uuid.UUID]]:
        existing = await self.run_repo.get_for_period(organization_id, period_year, period_month)
        if existing is not None:
            raise ConflictError(f"A depreciation run for {period_year}-{period_month:02d} already exists.")

        assets = await self.asset_repo.list_depreciable(organization_id)
        run = await self.run_repo.create(
            organization_id=organization_id,
            period_year=period_year,
            period_month=period_month,
            run_date=run_date,
            status=DepreciationRunStatus.DRAFT,
            created_by_user_id=created_by_user_id,
        )

        skipped: list[uuid.UUID] = []
        total_depreciation = 0.0
        for asset in assets:
            accumulated_so_far = await self.entry_repo.sum_posted_for_asset(asset.id)
            amount = _monthly_depreciation(
                asset.depreciation_method,
                float(asset.purchase_cost),
                float(asset.salvage_value),
                asset.useful_life_years,
                accumulated_so_far,
            )
            if amount <= 0:
                skipped.append(asset.id)
                continue

            accumulated_after = round(accumulated_so_far + amount, 2)
            await self.entry_repo.create(
                depreciation_run_id=run.id,
                asset_id=asset.id,
                depreciation_amount=amount,
                accumulated_depreciation=accumulated_after,
                net_book_value=round(float(asset.purchase_cost) - accumulated_after, 2),
            )
            total_depreciation += amount

        updated_run = await self.run_repo.update(run, total_depreciation_amount=round(total_depreciation, 2))
        logger.info(
            "depreciation_run_generated",
            run_id=str(run.id),
            assets_processed=len(assets) - len(skipped),
            assets_skipped=len(skipped),
        )
        return updated_run, len(assets) - len(skipped), skipped

    async def get_run(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> DepreciationRun:
        run = await self.run_repo.get_by_id(run_id, organization_id)
        if not run:
            raise NotFoundError("Depreciation run", run_id)
        return run

    async def list_runs(self, organization_id: uuid.UUID, **filters) -> tuple[list[DepreciationRun], int]:
        return await self.run_repo.list_for_organization(organization_id, **filters)

    async def list_entries(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> list[DepreciationEntry]:
        await self.get_run(run_id, organization_id)
        return await self.entry_repo.list_for_run(run_id)

    async def post_run(
        self, run_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID | None = None
    ) -> DepreciationRun:
        run = await self.get_run(run_id, organization_id)
        if run.status != DepreciationRunStatus.DRAFT:
            raise ValidationError(f"Only draft depreciation runs can be posted (this one is '{run.status.value}').")

        entries = await self.entry_repo.list_for_run(run_id)
        if not entries:
            raise ValidationError("This depreciation run has no entries to post.")

        gl_totals: dict[uuid.UUID, dict[str, float]] = {}
        for entry in entries:
            asset = await self.asset_repo.get_by_id(entry.asset_id, organization_id)
            expense_bucket = gl_totals.setdefault(asset.depreciation_expense_account_id, {"debit": 0.0, "credit": 0.0})
            expense_bucket["debit"] += float(entry.depreciation_amount)
            accum_bucket = gl_totals.setdefault(asset.accumulated_depreciation_account_id, {"debit": 0.0, "credit": 0.0})
            accum_bucket["credit"] += float(entry.depreciation_amount)

        journal_lines = []
        for account_id, totals in gl_totals.items():
            if totals["debit"] > 0:
                journal_lines.append({"account_id": account_id, "debit": round(totals["debit"], 2), "credit": 0})
            if totals["credit"] > 0:
                journal_lines.append({"account_id": account_id, "debit": 0, "credit": round(totals["credit"], 2)})

        entry_dt = datetime.combine(run.run_date, datetime.min.time(), tzinfo=timezone.utc)
        journal_entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=entry_dt,
            memo=f"Depreciation {run.period_year}-{run.period_month:02d}",
            source_module=JournalSourceModule.ASSETS,
            source_id=run.id,
            lines=journal_lines,
            created_by_user_id=created_by_user_id,
        )

        updated = await self.run_repo.update(
            run,
            status=DepreciationRunStatus.POSTED,
            journal_entry_id=journal_entry.id,
            posted_at=datetime.now(timezone.utc),
        )
        logger.info("depreciation_run_posted", run_id=str(run_id), journal_entry_id=str(journal_entry.id))
        return updated

    async def cancel_run(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> DepreciationRun:
        run = await self.get_run(run_id, organization_id)
        if run.status == DepreciationRunStatus.CANCELLED:
            raise ValidationError("This depreciation run is already cancelled.")

        if run.journal_entry_id is not None:
            await self.journal_service.reverse_entry(
                run.journal_entry_id,
                organization_id,
                memo=f"Cancellation of depreciation run {run.period_year}-{run.period_month:02d}",
            )

        updated = await self.run_repo.update(run, status=DepreciationRunStatus.CANCELLED)
        logger.info("depreciation_run_cancelled", run_id=str(run_id))
        return updated


class AssetDisposalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.asset_repo = AssetRepository(db)
        self.entry_repo = DepreciationEntryRepository(db)
        self.account_repo = AccountRepository(db)
        self.journal_service = JournalService(db)

    async def dispose_asset(
        self,
        asset_id: uuid.UUID,
        organization_id: uuid.UUID,
        disposal_date: date,
        disposal_amount: float,
        cash_account_id: uuid.UUID,
        gain_loss_account_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None = None,
    ) -> Asset:
        asset_repo_result = await self.asset_repo.get_by_id(asset_id, organization_id)
        if not asset_repo_result:
            raise NotFoundError("Asset", asset_id)
        asset = asset_repo_result
        if asset.status == AssetStatus.DISPOSED:
            raise ValidationError("This asset has already been disposed.")

        for account_id in (cash_account_id, gain_loss_account_id):
            account = await self.account_repo.get_by_id(account_id, organization_id)
            if not account:
                raise NotFoundError("GL account", account_id)

        accumulated_depreciation = await self.entry_repo.sum_posted_for_asset(
            asset_id, disposal_date.year, disposal_date.month
        )
        net_book_value = float(asset.purchase_cost) - accumulated_depreciation
        gain_loss = round(disposal_amount - net_book_value, 2)

        journal_lines = [
            {"account_id": asset.asset_account_id, "debit": 0, "credit": float(asset.purchase_cost)},
        ]
        if disposal_amount > 0:
            journal_lines.append({"account_id": cash_account_id, "debit": disposal_amount, "credit": 0})
        if accumulated_depreciation > 0:
            journal_lines.append(
                {"account_id": asset.accumulated_depreciation_account_id, "debit": round(accumulated_depreciation, 2), "credit": 0}
            )
        if gain_loss > 0:
            journal_lines.append({"account_id": gain_loss_account_id, "debit": 0, "credit": gain_loss})
        elif gain_loss < 0:
            journal_lines.append({"account_id": gain_loss_account_id, "debit": abs(gain_loss), "credit": 0})

        entry_dt = datetime.combine(disposal_date, datetime.min.time(), tzinfo=timezone.utc)
        journal_entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=entry_dt,
            memo=f"Disposal of asset {asset.asset_code}",
            source_module=JournalSourceModule.ASSETS,
            source_id=asset.id,
            lines=journal_lines,
            branch_id=asset.branch_id,
            created_by_user_id=created_by_user_id,
        )

        updated = await self.asset_repo.update(
            asset,
            status=AssetStatus.DISPOSED,
            disposal_date=disposal_date,
            disposal_amount=disposal_amount,
            disposal_journal_entry_id=journal_entry.id,
        )
        logger.info("asset_disposed", asset_id=str(asset_id), gain_loss=gain_loss)
        return updated
