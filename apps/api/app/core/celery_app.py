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
from celery.signals import worker_process_init

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.observability import init_sentry
from app.core.tracing import init_tracing, instrument_celery

configure_logging(service_name="erpx-celery")
# Capture background task failures. No-op unless SENTRY_DSN is configured;
# Sentry's Celery integration auto-enables here since celery is imported.
init_sentry(service_name="erpx-celery")
# Distributed tracing for the worker: provider + shared-client spans, plus a
# span per Celery task. No-op unless OTEL_TRACING_ENABLED is set.
init_tracing(service_name="erpx-celery")
instrument_celery()

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

@worker_process_init.connect
def reset_db_engine_pool(**_kwargs) -> None:
    """Drop any inherited DB connection pool when a prefork worker child starts.

    Celery's prefork pool forks worker children from the parent process. Any
    asyncpg connection the parent opened would be inherited as a live socket
    shared across processes — unsafe to use. Dispose the async ``engine``'s pool
    synchronously here (no event loop is running at process-init time, so use
    the underlying ``sync_engine``) so each child lazily opens its own
    connections. Per-task loop churn is handled separately by
    ``app.db.session.run_async``, which disposes the pool at the start of every
    task's event loop.
    """
    from app.db.session import engine

    if hasattr(engine, "sync_engine"):
        engine.sync_engine.dispose()
    else:  # pragma: no cover - engine is always an AsyncEngine here
        engine.dispose()


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
    "placements-run-aggregation": {
        "task": "placements.run_aggregation",
        "schedule": crontab(minute=0),
    },
    # Jooble's free tier is a 500-request *lifetime* cap, not recurring —
    # see modules/placements/connectors/jooble.py. Its own weekly cadence,
    # separate from the hourly entry above.
    "placements-run-jooble-aggregation": {
        "task": "placements.run_jooble_aggregation",
        "schedule": crontab(day_of_week="mon", hour=3, minute=0),
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
        "modules.placements",
    ]
)
