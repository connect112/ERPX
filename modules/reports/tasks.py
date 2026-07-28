"""
Reports module — background tasks.

`run_due_scheduled_reports_task` is the only thing that ever creates a
`ReportExecution` on a schedule's behalf: it runs each due
`ScheduledReport`, emails the exported file to its recipients, and
advances `next_run_at`. Wire into Celery beat, e.g.:

    celery_app.conf.beat_schedule["reports-run-due-scheduled-reports"] = {
        "task": "reports.run_due_scheduled_reports",
        "schedule": crontab(minute="*/30"),
    }
"""

import asyncio

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context
from modules.reports.models import ExportFormat
from modules.reports.registry import get_report_definition
from modules.reports.service import ReportService, ScheduledReportService
from packages.email.service import EmailAttachment, email_service

logger = get_logger(__name__)

_MIME_TYPES = {
    ExportFormat.CSV: "text/csv",
    ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportFormat.PDF: "application/pdf",
}
_EXTENSIONS = {ExportFormat.CSV: "csv", ExportFormat.EXCEL: "xlsx", ExportFormat.PDF: "pdf"}


async def _run_due_scheduled_reports() -> tuple[int, int]:
    succeeded = 0
    failed = 0
    async with get_db_context() as db:
        scheduled_service = ScheduledReportService(db)
        report_service = ReportService(db)
        due_schedules = await scheduled_service.list_due()

        for schedule in due_schedules:
            try:
                export_format = schedule.export_format
                if export_format == ExportFormat.JSON:
                    export_format = ExportFormat.EXCEL  # a scheduled email needs an attachment, not raw JSON

                execution, result, file_bytes = await report_service.run_report(
                    schedule.organization_id,
                    schedule.report_key,
                    schedule.parameters,
                    export_format,
                    scheduled_report_id=schedule.id,
                )

                definition = get_report_definition(schedule.report_key)
                extension = _EXTENSIONS[export_format]
                attachment = EmailAttachment(
                    filename=f"{schedule.name.replace(' ', '_')}.{extension}",
                    content=file_bytes,
                    mime_type=_MIME_TYPES[export_format],
                )
                for recipient in schedule.recipient_emails:
                    await email_service.send(
                        to_email=recipient,
                        subject=f"ERPX Scheduled Report: {schedule.name}",
                        text_body=(
                            f"Your scheduled report '{schedule.name}' ({definition.name}) is attached.\n\n"
                            f"Rows: {execution.row_count}\nGenerated at: {execution.created_at.isoformat()}"
                        ),
                        attachments=[attachment],
                    )

                await scheduled_service.mark_run(schedule)
                succeeded += 1
            except Exception:
                logger.exception("scheduled_report_run_failed", schedule_id=str(schedule.id))
                failed += 1

    return succeeded, failed


@celery_app.task(name="reports.run_due_scheduled_reports")
def run_due_scheduled_reports_task() -> None:
    succeeded, failed = asyncio.run(_run_due_scheduled_reports())
    logger.info("scheduled_reports_run_complete", succeeded=succeeded, failed=failed)
