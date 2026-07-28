import calendar
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.reports.models import ExportFormat, ReportExecution, ReportExecutionStatus, ScheduledReport, ScheduleFrequency
from modules.reports.registry import ReportResult, dispatch_report, get_report_definition
from modules.reports.repository import ReportExecutionRepository, ScheduledReportRepository
from packages.reports.exporters import to_csv_bytes, to_excel_bytes, to_pdf_bytes

logger = get_logger(__name__)


def _next_occurrence(current: datetime, frequency: ScheduleFrequency) -> datetime:
    if frequency == ScheduleFrequency.DAILY:
        return current + timedelta(days=1)
    if frequency == ScheduleFrequency.WEEKLY:
        return current + timedelta(days=7)

    month = current.month + 1
    year = current.year
    if month > 12:
        month = 1
        year += 1
    day = min(current.day, calendar.monthrange(year, month)[1])
    return current.replace(year=year, month=month, day=day)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.execution_repo = ReportExecutionRepository(db)

    async def run_report(
        self,
        organization_id: uuid.UUID,
        report_key: str,
        parameters: dict,
        export_format: ExportFormat,
        executed_by_user_id: uuid.UUID | None = None,
        scheduled_report_id: uuid.UUID | None = None,
    ) -> tuple[ReportExecution, ReportResult | None, bytes | None]:
        get_report_definition(report_key)  # raises ValidationError if unknown, before we start timing
        started_at = time.monotonic()

        try:
            result = await dispatch_report(self.db, organization_id, report_key, parameters)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            execution = await self.execution_repo.create(
                organization_id=organization_id,
                executed_by_user_id=executed_by_user_id,
                scheduled_report_id=scheduled_report_id,
                report_key=report_key,
                parameters=parameters,
                export_format=export_format,
                status=ReportExecutionStatus.FAILED,
                execution_time_ms=elapsed_ms,
                error_message=str(exc),
            )
            logger.warning("report_execution_failed", report_key=report_key, error=str(exc))
            raise

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        execution = await self.execution_repo.create(
            organization_id=organization_id,
            executed_by_user_id=executed_by_user_id,
            scheduled_report_id=scheduled_report_id,
            report_key=report_key,
            parameters=parameters,
            export_format=export_format,
            status=ReportExecutionStatus.SUCCESS,
            row_count=len(result.rows),
            execution_time_ms=elapsed_ms,
        )

        file_bytes = None
        if export_format == ExportFormat.CSV:
            file_bytes = to_csv_bytes(result.columns, result.rows)
        elif export_format == ExportFormat.EXCEL:
            file_bytes = to_excel_bytes(result.columns, result.rows, sheet_name=result.title[:31])
        elif export_format == ExportFormat.PDF:
            file_bytes = to_pdf_bytes(result.title, result.columns, result.rows)

        logger.info("report_executed", report_key=report_key, rows=len(result.rows), ms=elapsed_ms)
        return execution, result, file_bytes

    async def get_execution(self, execution_id: uuid.UUID, organization_id: uuid.UUID) -> ReportExecution:
        execution = await self.execution_repo.get_by_id(execution_id, organization_id)
        if not execution:
            raise NotFoundError("Report execution", execution_id)
        return execution

    async def list_executions(self, organization_id: uuid.UUID, **filters):
        return await self.execution_repo.list_for_organization(organization_id, **filters)


class ScheduledReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ScheduledReportRepository(db)

    async def create_schedule(
        self,
        organization_id: uuid.UUID,
        report_key: str,
        frequency: ScheduleFrequency,
        created_by_user_id: uuid.UUID | None = None,
        **fields,
    ) -> ScheduledReport:
        get_report_definition(report_key)  # validates existence
        now = datetime.now(timezone.utc)
        schedule = await self.repo.create(
            organization_id=organization_id,
            report_key=report_key,
            frequency=frequency,
            created_by_user_id=created_by_user_id,
            next_run_at=_next_occurrence(now, frequency),
            **fields,
        )
        logger.info("scheduled_report_created", schedule_id=str(schedule.id), report_key=report_key)
        return schedule

    async def get_schedule(self, schedule_id: uuid.UUID, organization_id: uuid.UUID) -> ScheduledReport:
        schedule = await self.repo.get_by_id(schedule_id, organization_id)
        if not schedule:
            raise NotFoundError("Scheduled report", schedule_id)
        return schedule

    async def list_schedules(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_schedule(self, schedule_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> ScheduledReport:
        schedule = await self.get_schedule(schedule_id, organization_id)
        if fields.get("report_key") is not None:
            get_report_definition(fields["report_key"])
        if fields.get("frequency") is not None:
            fields["next_run_at"] = _next_occurrence(datetime.now(timezone.utc), fields["frequency"])
        updated = await self.repo.update(schedule, **fields)
        logger.info("scheduled_report_updated", schedule_id=str(schedule_id))
        return updated

    async def deactivate_schedule(self, schedule_id: uuid.UUID, organization_id: uuid.UUID) -> ScheduledReport:
        schedule = await self.get_schedule(schedule_id, organization_id)
        return await self.repo.update(schedule, is_active=False)

    async def list_due(self, as_of: datetime | None = None) -> list[ScheduledReport]:
        return await self.repo.list_due(as_of or datetime.now(timezone.utc))

    async def mark_run(self, schedule: ScheduledReport) -> ScheduledReport:
        now = datetime.now(timezone.utc)
        return await self.repo.update(
            schedule, last_run_at=now, next_run_at=_next_occurrence(now, schedule.frequency)
        )
