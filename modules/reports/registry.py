"""
Report catalog + dispatch.

Every entry in `REPORT_CATALOG` describes one report available across
the platform; `dispatch_report` runs it. Most dispatchers call an
existing module's own report service (Accounting's `ReportService`,
Corporate's `CorporateReportService`, Marketing's
`MarketingAnalyticsService`) rather than recomputing anything — this
module's job is cataloging, running-on-demand-or-schedule, exporting,
and auditing, not owning report logic that already lives correctly in
its domain module. A handful of reports (CRM pipeline, HR attendance,
Inventory low stock) have no existing "report service" to call, so
their aggregation lives here directly, kept intentionally thin.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError


@dataclass
class ReportResult:
    title: str
    columns: list[str]
    rows: list[dict]


@dataclass
class ReportDefinition:
    key: str
    name: str
    module: str
    description: str
    required_parameters: list[str] = field(default_factory=list)


def _require(parameters: dict, name: str):
    if name not in parameters or parameters[name] in (None, ""):
        raise ValidationError(f"Missing required parameter '{name}' for this report.")
    return parameters[name]


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


async def _accounting_trial_balance(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.accounting.reports.service import ReportService

    as_of_date = _parse_date(_require(parameters, "as_of_date"))
    result = await ReportService(db).trial_balance(organization_id, as_of_date)
    columns = ["code", "name", "account_type", "debit_balance", "credit_balance"]
    rows = [
        {
            "code": line["code"],
            "name": line["name"],
            "account_type": line["account_type"].value,
            "debit_balance": line["debit_balance"],
            "credit_balance": line["credit_balance"],
        }
        for line in result["lines"]
    ]
    return ReportResult(title=f"Trial Balance as of {as_of_date}", columns=columns, rows=rows)


async def _accounting_profit_and_loss(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.accounting.reports.service import ReportService

    period_from = _parse_date(_require(parameters, "period_from"))
    period_to = _parse_date(_require(parameters, "period_to"))
    result = await ReportService(db).profit_and_loss(organization_id, period_from, period_to)
    columns = ["section", "code", "name", "amount"]
    rows = [
        {"section": "income", "code": l["code"], "name": l["name"], "amount": l["credit_balance"]}
        for l in result["income_lines"]
    ] + [
        {"section": "expense", "code": l["code"], "name": l["name"], "amount": l["debit_balance"]}
        for l in result["expense_lines"]
    ]
    rows.append({"section": "summary", "code": "", "name": "Net Profit", "amount": result["net_profit"]})
    return ReportResult(title=f"Profit & Loss: {period_from} to {period_to}", columns=columns, rows=rows)


async def _accounting_balance_sheet(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.accounting.reports.service import ReportService

    as_of_date = _parse_date(_require(parameters, "as_of_date"))
    result = await ReportService(db).balance_sheet(organization_id, as_of_date)
    columns = ["section", "code", "name", "amount"]
    rows = (
        [{"section": "asset", "code": l["code"], "name": l["name"], "amount": l["debit_balance"]} for l in result["asset_lines"]]
        + [{"section": "liability", "code": l["code"], "name": l["name"], "amount": l["credit_balance"]} for l in result["liability_lines"]]
        + [{"section": "equity", "code": l["code"], "name": l["name"], "amount": l["credit_balance"]} for l in result["equity_lines"]]
        + [{"section": "summary", "code": "", "name": "Retained Earnings", "amount": result["retained_earnings"]}]
    )
    return ReportResult(title=f"Balance Sheet as of {as_of_date}", columns=columns, rows=rows)


async def _accounting_ar_aging(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.accounting.reports.service import ReportService

    as_of_date = _parse_date(_require(parameters, "as_of_date"))
    result = await ReportService(db).accounts_receivable_aging(organization_id, as_of_date)
    columns = ["party_name", "document_number", "due_date", "outstanding_amount", "days_overdue", "bucket"]
    rows = [{k: item[k] for k in columns} for item in result["items"]]
    return ReportResult(title=f"Accounts Receivable Aging as of {as_of_date}", columns=columns, rows=rows)


async def _accounting_ap_aging(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.accounting.reports.service import ReportService

    as_of_date = _parse_date(_require(parameters, "as_of_date"))
    result = await ReportService(db).accounts_payable_aging(organization_id, as_of_date)
    columns = ["party_name", "document_number", "due_date", "outstanding_amount", "days_overdue", "bucket"]
    rows = [{k: item[k] for k in columns} for item in result["items"]]
    return ReportResult(title=f"Accounts Payable Aging as of {as_of_date}", columns=columns, rows=rows)


async def _corporate_client_summary(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.corporate.reports.service import CorporateReportService

    client_id = _parse_uuid(_require(parameters, "client_id"))
    result = await CorporateReportService(db).client_summary(client_id, organization_id)
    columns = list(result.keys())
    return ReportResult(title="Corporate Client Summary", columns=columns, rows=[result])


async def _corporate_vapt_portfolio(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.corporate.reports.service import CorporateReportService

    as_of_date = _parse_date(parameters.get("as_of_date") or date.today().isoformat())
    result = await CorporateReportService(db).vapt_portfolio_summary(organization_id, as_of_date)
    row = {**result, "findings_by_severity": str(result["findings_by_severity"])}
    columns = list(row.keys())
    return ReportResult(title="VAPT Portfolio Summary", columns=columns, rows=[row])


async def _corporate_ticket_sla(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.corporate.reports.service import CorporateReportService

    result = await CorporateReportService(db).ticket_sla_summary(organization_id)
    row = {**result, "by_priority": str(result["by_priority"])}
    columns = list(row.keys())
    return ReportResult(title="Ticket SLA Summary", columns=columns, rows=[row])


async def _marketing_campaign_performance(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.marketing.analytics.service import MarketingAnalyticsService

    campaign_id = _parse_uuid(_require(parameters, "campaign_id"))
    result = await MarketingAnalyticsService(db).campaign_performance(campaign_id, organization_id)
    columns = list(result.keys())
    return ReportResult(title="Campaign Performance", columns=columns, rows=[result])


async def _marketing_overview(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.marketing.analytics.service import MarketingAnalyticsService

    result = await MarketingAnalyticsService(db).marketing_overview(organization_id)
    columns = list(result.keys())
    return ReportResult(title="Marketing Overview", columns=columns, rows=[result])


async def _crm_leads_pipeline(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.crm.leads.repository import LeadRepository

    leads, total = await LeadRepository(db).list_for_organization(organization_id, skip=0, limit=10_000)
    by_status: dict[str, int] = {}
    for lead in leads:
        by_status[lead.status.value] = by_status.get(lead.status.value, 0) + 1
    columns = ["status", "count"]
    rows = [{"status": status, "count": count} for status, count in sorted(by_status.items())]
    rows.append({"status": "TOTAL", "count": total})
    return ReportResult(title="CRM Leads Pipeline", columns=columns, rows=rows)


async def _hr_attendance_summary(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.attendance.repository import AttendanceRepository

    date_from = _parse_date(_require(parameters, "date_from"))
    date_to = _parse_date(_require(parameters, "date_to"))
    records, total = await AttendanceRepository(db).list_for_organization(organization_id, skip=0, limit=10_000)
    in_range = [r for r in records if date_from <= r.attendance_date <= date_to]
    by_status: dict[str, int] = {}
    for record in in_range:
        by_status[record.status.value] = by_status.get(record.status.value, 0) + 1
    columns = ["status", "count"]
    rows = [{"status": status, "count": count} for status, count in sorted(by_status.items())]
    return ReportResult(title=f"Attendance Summary: {date_from} to {date_to}", columns=columns, rows=rows)


async def _payroll_run_payslips(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.payroll.service import PayrollService

    run_id = _parse_uuid(_require(parameters, "run_id"))
    payslips = await PayrollService(db).list_payslips(run_id, organization_id)
    columns = ["employee_id", "days_in_month", "paid_days", "lop_days", "gross_amount", "total_deductions", "net_amount"]
    rows = [
        {
            "employee_id": str(p.employee_id),
            "days_in_month": p.days_in_month,
            "paid_days": float(p.paid_days),
            "lop_days": float(p.lop_days),
            "gross_amount": float(p.gross_amount),
            "total_deductions": float(p.total_deductions),
            "net_amount": float(p.net_amount),
        }
        for p in payslips
    ]
    return ReportResult(title="Payroll Run Payslips", columns=columns, rows=rows)


async def _inventory_low_stock(db: AsyncSession, organization_id: uuid.UUID, parameters: dict) -> ReportResult:
    from modules.inventory.service import StockService

    low_stock = await StockService(db).list_low_stock_items(organization_id)
    columns = ["sku", "name", "reorder_level", "quantity_on_hand"]
    return ReportResult(title="Low Stock Items", columns=columns, rows=low_stock)


_DISPATCHERS: dict[str, Callable[[AsyncSession, uuid.UUID, dict], Awaitable[ReportResult]]] = {
    "accounting.trial_balance": _accounting_trial_balance,
    "accounting.profit_and_loss": _accounting_profit_and_loss,
    "accounting.balance_sheet": _accounting_balance_sheet,
    "accounting.ar_aging": _accounting_ar_aging,
    "accounting.ap_aging": _accounting_ap_aging,
    "corporate.client_summary": _corporate_client_summary,
    "corporate.vapt_portfolio_summary": _corporate_vapt_portfolio,
    "corporate.ticket_sla_summary": _corporate_ticket_sla,
    "marketing.campaign_performance": _marketing_campaign_performance,
    "marketing.overview": _marketing_overview,
    "crm.leads_pipeline": _crm_leads_pipeline,
    "hr.attendance_summary": _hr_attendance_summary,
    "payroll.run_payslips": _payroll_run_payslips,
    "inventory.low_stock": _inventory_low_stock,
}


REPORT_CATALOG: list[ReportDefinition] = [
    ReportDefinition("accounting.trial_balance", "Trial Balance", "accounting", "All account balances as of a date.", ["as_of_date"]),
    ReportDefinition("accounting.profit_and_loss", "Profit & Loss", "accounting", "Income vs. expense for a period.", ["period_from", "period_to"]),
    ReportDefinition("accounting.balance_sheet", "Balance Sheet", "accounting", "Assets, liabilities, and equity as of a date.", ["as_of_date"]),
    ReportDefinition("accounting.ar_aging", "Accounts Receivable Aging", "accounting", "Outstanding invoices bucketed by age.", ["as_of_date"]),
    ReportDefinition("accounting.ap_aging", "Accounts Payable Aging", "accounting", "Outstanding expenses bucketed by age.", ["as_of_date"]),
    ReportDefinition("corporate.client_summary", "Client Summary", "corporate", "Projects, tickets, AMC, and SOC status for one client.", ["client_id"]),
    ReportDefinition("corporate.vapt_portfolio_summary", "VAPT Portfolio Summary", "corporate", "Findings across all VAPT engagements.", []),
    ReportDefinition("corporate.ticket_sla_summary", "Ticket SLA Summary", "corporate", "Open and overdue support tickets by priority.", []),
    ReportDefinition("marketing.campaign_performance", "Campaign Performance", "marketing", "Leads, views, and coupon usage for one campaign.", ["campaign_id"]),
    ReportDefinition("marketing.overview", "Marketing Overview", "marketing", "Org-wide campaign, coupon, and referral totals.", []),
    ReportDefinition("crm.leads_pipeline", "CRM Leads Pipeline", "crm", "Lead counts by status.", []),
    ReportDefinition("hr.attendance_summary", "Attendance Summary", "hr", "Attendance record counts by status for a date range.", ["date_from", "date_to"]),
    ReportDefinition("payroll.run_payslips", "Payroll Run Payslips", "payroll", "All payslips for one payroll run.", ["run_id"]),
    ReportDefinition("inventory.low_stock", "Low Stock Items", "inventory", "Items at or below their reorder level.", []),
]

_CATALOG_BY_KEY = {entry.key: entry for entry in REPORT_CATALOG}


def get_report_definition(report_key: str) -> ReportDefinition:
    definition = _CATALOG_BY_KEY.get(report_key)
    if definition is None:
        raise ValidationError(f"Unknown report_key '{report_key}'.")
    return definition


async def dispatch_report(
    db: AsyncSession, organization_id: uuid.UUID, report_key: str, parameters: dict
) -> ReportResult:
    get_report_definition(report_key)  # validates report_key, raises if unknown
    dispatcher = _DISPATCHERS[report_key]
    return await dispatcher(db, organization_id, parameters or {})
