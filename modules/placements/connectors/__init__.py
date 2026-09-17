"""
Connector registry/orchestrator. `fetch_all` calls every registered
connector and always returns a per-source dict, catching anything that
somehow escapes an individual connector's own internal error handling — a
defense-in-depth layer, not the primary safety net (each connector module's
own docstring/`base.py` spells out the "never raise" contract connectors are
expected to uphold themselves).

Adding a fifth source means adding one file under this package implementing
`fetch_postings(keywords, db) -> ConnectorResult` and one entry in
`_CONNECTORS` below — nothing else changes.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from modules.placements.connectors import adzuna, arbeitnow, jooble, reed
from modules.placements.connectors.base import ConnectorResult, RawPosting

logger = get_logger(__name__)

_CONNECTORS = {
    "adzuna": adzuna.fetch_postings,
    "jooble": jooble.fetch_postings,
    "reed": reed.fetch_postings,
    "arbeitnow": arbeitnow.fetch_postings,
}

# CyberSecJobs, InfoSec-Jobs.com, and ClearedJobs.net were researched and
# deliberately excluded: none has a documented public API for individual
# job listings (verified directly against each site's own docs/pages as of
# 2026-08-25). A related site, infosecjobboard.com, does have a free JSON
# API, but it publishes only aggregate counts/benchmarks, not raw postings —
# unusable for populating individual JobPosting rows. Revisit if any of
# these publishes a real listings API; adding one back is the same one-file
# +one-registry-entry process described above.


async def fetch_all(
    keywords: list[str], db: AsyncSession, sources: list[str] | None = None
) -> dict[str, ConnectorResult]:
    """Runs every connector in `sources` (default: all registered), each
    isolated so one source's failure can't block the others. Returns a
    dict keyed by source name."""
    target_sources = sources if sources is not None else list(_CONNECTORS.keys())
    results: dict[str, ConnectorResult] = {}

    for source in target_sources:
        fetch_fn = _CONNECTORS.get(source)
        if fetch_fn is None:
            logger.warning("aggregation_unknown_source_requested", source=source)
            continue
        try:
            results[source] = await fetch_fn(keywords, db)
        except Exception:
            # Defense-in-depth: every connector is documented to never raise,
            # but a run must never be lost to a single connector's bug.
            logger.exception("connector_raised_unexpectedly", source=source)
            results[source] = ConnectorResult(
                postings=[], request_count=0, status="error",
                error_message="Connector raised an unexpected exception.",
            )

    return results


__all__ = ["fetch_all", "ConnectorResult", "RawPosting"]
