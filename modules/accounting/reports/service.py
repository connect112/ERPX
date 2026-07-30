import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.ledger.models import DEBIT_NORMAL_TYPES, AccountType
from modules.accounting.reports.repository import ReportsRepository

_AGING_BUCKETS = [
    (0, 0, "current"),
    (1, 30, "1-30"),
    (31, 60, "31-60"),
    (61, 90, "61-90"),
    (91, None, "90+"),
]


def _bucket_for(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    for low, high, label in _AGING_BUCKETS:
        if label == "current":
            continue
        if high is None or days_overdue <= high:
            if days_overdue >= low:
                return label
    return "90+"


def _end_of_day_utc(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


def _start_of_day_utc(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReportsRepository(db)

    async def _merged_lines(
        self,
        organization_id: uuid.UUID,
        account_types: list[AccountType],
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict]:
        accounts = await self.repo.all_accounts(organization_id, account_types)
        activity = await self.repo.account_activity(organization_id, account_types, date_from, date_to)
        activity_by_id = {row["account_id"]: row for row in activity}

        lines = []
        for account in accounts:
            row = activity_by_id.get(account.id)
            total_debit = row["total_debit"] if row else 0.0
            total_credit = row["total_credit"] if row else 0.0
            opening = float(account.opening_balance) if date_from is None else 0.0

            if account.account_type in DEBIT_NORMAL_TYPES:
                net = opening + total_debit - total_credit
                debit_balance = max(net, 0.0)
                credit_balance = max(-net, 0.0)
            else:
                net = opening + total_credit - total_debit
                credit_balance = max(net, 0.0)
                debit_balance = max(-net, 0.0)

            if debit_balance == 0 and credit_balance == 0 and row is None and float(account.opening_balance) == 0:
                continue

            lines.append(
                {
                    "account_id": account.id,
                    "code": account.code,
                    "name": account.name,
                    "account_type": account.account_type,
                    "debit_balance": round(debit_balance, 2),
                    "credit_balance": round(credit_balance, 2),
                }
            )
        return lines

    async def trial_balance(self, organization_id: uuid.UUID, as_of_date: date) -> dict:
        lines = await self._merged_lines(
            organization_id,
            [AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY, AccountType.INCOME, AccountType.EXPENSE],
            None,
            _end_of_day_utc(as_of_date),
        )
        total_debit = round(sum(l["debit_balance"] for l in lines), 2)
        total_credit = round(sum(l["credit_balance"] for l in lines), 2)
        return {
            "as_of_date": as_of_date,
            "lines": lines,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "is_balanced": abs(total_debit - total_credit) < 0.01,
        }

    async def profit_and_loss(self, organization_id: uuid.UUID, period_from: date, period_to: date) -> dict:
        income_lines = await self._merged_lines(
            organization_id, [AccountType.INCOME], _start_of_day_utc(period_from), _end_of_day_utc(period_to)
        )
        expense_lines = await self._merged_lines(
            organization_id, [AccountType.EXPENSE], _start_of_day_utc(period_from), _end_of_day_utc(period_to)
        )
        total_income = round(sum(l["credit_balance"] for l in income_lines), 2)
        total_expense = round(sum(l["debit_balance"] for l in expense_lines), 2)
        return {
            "period_from": period_from,
            "period_to": period_to,
            "income_lines": income_lines,
            "expense_lines": expense_lines,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_profit": round(total_income - total_expense, 2),
        }

    async def balance_sheet(self, organization_id: uuid.UUID, as_of_date: date) -> dict:
        asset_lines = await self._merged_lines(
            organization_id, [AccountType.ASSET], None, _end_of_day_utc(as_of_date)
        )
        liability_lines = await self._merged_lines(
            organization_id, [AccountType.LIABILITY], None, _end_of_day_utc(as_of_date)
        )
        equity_lines = await self._merged_lines(
            organization_id, [AccountType.EQUITY], None, _end_of_day_utc(as_of_date)
        )

        # Retained earnings since inception = cumulative net profit up to as_of_date.
        pnl = await self.profit_and_loss(organization_id, date(2000, 1, 1), as_of_date)

        total_assets = round(sum(l["debit_balance"] for l in asset_lines), 2)
        total_liabilities = round(sum(l["credit_balance"] for l in liability_lines), 2)
        total_equity = round(sum(l["credit_balance"] for l in equity_lines), 2)
        retained_earnings = pnl["net_profit"]
        total_liabilities_and_equity = round(total_liabilities + total_equity + retained_earnings, 2)

        return {
            "as_of_date": as_of_date,
            "asset_lines": asset_lines,
            "liability_lines": liability_lines,
            "equity_lines": equity_lines,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "retained_earnings": retained_earnings,
            "total_liabilities_and_equity": total_liabilities_and_equity,
            "is_balanced": abs(total_assets - total_liabilities_and_equity) < 0.01,
        }

    async def accounts_receivable_aging(self, organization_id: uuid.UUID, as_of_date: date) -> dict:
        # One JOINed query (invoice + customer name) instead of a per-invoice
        # customer lookup — see ReportsRepository.outstanding_receivables_with_customer.
        invoices = await self.repo.outstanding_receivables_with_customer(organization_id)
        items = []
        bucket_totals: dict[str, float] = {}
        cutoff = _end_of_day_utc(as_of_date)

        for invoice, customer_name in invoices:
            outstanding = invoice.outstanding_amount
            if outstanding <= 0:
                continue
            days_overdue = max((cutoff.date() - invoice.due_date.date()).days, 0)
            bucket = _bucket_for(days_overdue)
            bucket_totals[bucket] = round(bucket_totals.get(bucket, 0) + outstanding, 2)
            items.append(
                {
                    "party_id": invoice.customer_id,
                    "party_name": customer_name if customer_name else "Unknown",
                    "document_number": invoice.invoice_number,
                    "document_date": invoice.invoice_date.date(),
                    "due_date": invoice.due_date.date(),
                    "outstanding_amount": round(outstanding, 2),
                    "days_overdue": days_overdue,
                    "bucket": bucket,
                }
            )

        return {
            "as_of_date": as_of_date,
            "items": items,
            "total_outstanding": round(sum(i["outstanding_amount"] for i in items), 2),
            "bucket_totals": bucket_totals,
        }

    async def accounts_payable_aging(self, organization_id: uuid.UUID, as_of_date: date) -> dict:
        # One JOINed query (expense + vendor name) instead of a per-expense
        # vendor lookup — see ReportsRepository.outstanding_payables_with_vendor.
        expenses = await self.repo.outstanding_payables_with_vendor(organization_id)
        items = []
        bucket_totals: dict[str, float] = {}
        cutoff = _end_of_day_utc(as_of_date)

        for expense, vendor_name in expenses:
            outstanding = expense.outstanding_amount
            if outstanding <= 0:
                continue
            due_date = expense.approved_at or expense.expense_date
            days_overdue = max((cutoff.date() - due_date.date()).days, 0)
            bucket = _bucket_for(days_overdue)
            bucket_totals[bucket] = round(bucket_totals.get(bucket, 0) + outstanding, 2)
            items.append(
                {
                    "party_id": expense.vendor_id,
                    "party_name": vendor_name if vendor_name else "Unknown",
                    "document_number": expense.expense_number,
                    "document_date": expense.expense_date.date(),
                    "due_date": due_date.date(),
                    "outstanding_amount": round(outstanding, 2),
                    "days_overdue": days_overdue,
                    "bucket": bucket,
                }
            )

        return {
            "as_of_date": as_of_date,
            "items": items,
            "total_outstanding": round(sum(i["outstanding_amount"] for i in items), 2),
            "bucket_totals": bucket_totals,
        }
