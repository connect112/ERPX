"""
Unit tests: the two scheduled Celery tasks that previously had no retry
policy now retry transient failures with exponential backoff, matching the
resilience already present on `crm.followups.*`.

Config-level assertions (no broker/DB needed): if the retry options are
dropped from either decorator, these fail.
"""

import pytest

# Importing the task modules registers the tasks on the shared Celery app.
import modules.accounting.invoices.tasks  # noqa: F401
import modules.crm.followups.tasks  # noqa: F401
import modules.placements.tasks  # noqa: F401
import modules.reports.tasks  # noqa: F401
from app.core.celery_app import celery_app

pytestmark = pytest.mark.unit

_HARDENED_TASKS = [
    "accounting.mark_overdue_invoices",
    "reports.run_due_scheduled_reports",
    "placements.run_aggregation",
    "placements.run_jooble_aggregation",
]


@pytest.mark.parametrize("task_name", _HARDENED_TASKS)
def test_scheduled_task_has_retry_backoff(task_name):
    task = celery_app.tasks[task_name]
    assert task.max_retries == 3
    assert Exception in tuple(task.autoretry_for)
    assert task.retry_backoff  # exponential backoff enabled
    assert task.retry_jitter


def test_followup_tasks_still_retry():
    # Anchor: the pre-existing retry policy this change mirrors is intact.
    for name in ("crm.followups.send_whatsapp_reminder", "crm.followups.send_sms_reminder"):
        assert celery_app.tasks[name].max_retries == 3
