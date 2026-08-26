"""
Placements module — background tasks.

Two Celery beat entries (wired in `app/core/celery_app.py`):
  - `placements.run_aggregation` — hourly, all sources except Jooble.
  - `placements.run_jooble_aggregation` — weekly, Jooble only.

Split because Jooble's free tier is a 500-request *lifetime* cap (confirmed
against Jooble's own help-center docs), not a recurring quota — a true
hourly cadence would exhaust it in under 3 weeks. See
`modules/placements/connectors/jooble.py`'s module docstring for the full
reasoning. Both tasks share the same `AggregationService.run_aggregation`
pipeline (normalize/filter/dedup/upsert/absence-sweep identical either way)
via the `sources` parameter.

Follows `modules/reports/tasks.py`'s exact shape: a thin sync `@celery_app.
task` wrapper around `run_async(<coroutine>)`, with DB access inside the
coroutine going through `get_db_context()` (not the FastAPI `get_db`
dependency, which only exists inside a request).
"""

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.placements.aggregation_service import AggregationService

logger = get_logger(__name__)

_HOURLY_SOURCES = ["adzuna", "reed", "arbeitnow"]


async def _run_aggregation(triggered_by: str, sources: list[str] | None, run_id: str | None) -> str:
    async with get_db_context() as db:
        service = AggregationService(db)
        run = await service.run_aggregation(triggered_by=triggered_by, sources=sources, run_id=run_id)
        return str(run.id)


@celery_app.task(
    name="placements.run_aggregation",
    # Per-source failures are already caught and recorded inside
    # AggregationService (one AggregationRunSource row per connector), so an
    # exception escaping all the way here means something infra-level broke
    # (e.g. the DB was briefly unreachable). Retry the whole run with
    # backoff rather than losing this beat tick; the run is idempotent
    # (upsert on (organization, source, external_id) — a re-run creates no
    # duplicates).
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def run_aggregation_task(triggered_by: str = "schedule", run_id: str | None = None) -> None:
    """`run_id`, when given (the manual-trigger route always passes its
    pre-created `AggregationRun.id`), makes this task update THAT row
    rather than create a second, disconnected one — Celery task args are
    JSON, so the id has to travel as a plain string, an ORM object can't
    cross `.delay()`. The scheduled beat entry calls this with no `run_id`
    (there's no pre-created row for it to attach to), so the service
    creates one itself, same as always."""
    result_run_id = run_async(_run_aggregation(triggered_by, _HOURLY_SOURCES, run_id))
    logger.info("placements_aggregation_run_complete", run_id=result_run_id, sources=_HOURLY_SOURCES)


@celery_app.task(
    name="placements.run_jooble_aggregation",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def run_jooble_aggregation_task() -> None:
    result_run_id = run_async(_run_aggregation("schedule:jooble_weekly", ["jooble"], run_id=None))
    logger.info("placements_jooble_aggregation_run_complete", run_id=result_run_id)
