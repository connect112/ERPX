"""
Celery application instance.

Every module that needs background/scheduled work (email dispatch,
report generation, VM lifecycle in Pentrix, payroll runs, etc.) registers
its tasks under `modules/<module>/tasks.py` and imports `celery_app` from
here rather than creating a separate Celery instance.

`configure_logging()` is called here — not just from `app/main.py` — since
the K8s/Compose worker and beat entrypoints (`celery -A app.core.celery_app
worker/beat ...`) import only this module, never `app.main`. Previously
that meant Celery processes silently fell back to structlog's un-configured
default renderer (plain key=value text, no JSON, no schema fields) despite
using the identical `get_logger()` API every task module calls — a real,
verified inconsistency (see docs/logging-architecture-proposal.md Section 1).
`service_name="erpx-celery"` distinguishes worker/beat log lines from the
API's `erpx-api` in the unified `service` field.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging_config import configure_logging

configure_logging(service_name="erpx-celery")

celery_app = Celery(
    "erpx",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "accounting-mark-overdue-invoices": {
        "task": "accounting.mark_overdue_invoices",
        "schedule": crontab(hour=0, minute=30),
    },
    "reports-run-due-scheduled-reports": {
        "task": "reports.run_due_scheduled_reports",
        "schedule": crontab(minute="*/30"),
    },
    "backups-trigger-daily": {
        "task": "backups.trigger_daily_backup",
        "schedule": crontab(hour=2, minute=0),
    },
}

# Modules register their Celery task modules here as they are built, e.g.:
# celery_app.autodiscover_tasks(["modules.notifications", "modules.accounting"])
celery_app.autodiscover_tasks(
    packages=[
        "modules.authentication",
        "modules.accounting",
        "modules.reports",
        "modules.crm.followups",
        "modules.backups",
    ]
)
