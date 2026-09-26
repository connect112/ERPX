"""
Keyword configuration for the job-aggregation pipeline.

Kept global (not per-organization) deliberately: the connectors' API
credentials in `app/core/config.py` are platform-wide secrets already, not
per-tenant, and letting each organization tune its own keyword list would
multiply external API calls per organization — which the pipeline is
explicitly designed to avoid (it fetches from every source once per run,
then fans the results out to every active organization; see
`aggregation_service.py`). Tuning the list is an ops-level `.env` change +
restart, exactly like every other integration setting in this codebase
(`AI_MODEL`, `SMTP_*`, etc.) — not a runtime/admin-UI concern.

If true per-organization keyword customization is ever wanted, `Organization
Setting` (already used for org-scoped config elsewhere, e.g. timezone/
currency) is the natural extension point — but that would conflict with the
single-fetch-per-run design this pipeline relies on to stay under Adzuna's
and Jooble's tight free-tier rate/lifetime budgets.
"""

from app.core.config import settings

DEFAULT_CYBERSECURITY_KEYWORDS: list[str] = [
    "cybersecurity",
    "infosec",
    "information security",
    "penetration tester",
    "security engineer",
    "SOC analyst",
    "incident response",
    "threat intelligence",
    "security analyst",
    "cloud security engineer",
    "application security",
    "GRC analyst",
    "CISO",
]


def get_aggregation_keywords() -> list[str]:
    raw = settings.PLACEMENTS_AGGREGATION_KEYWORDS.strip()
    if not raw:
        return list(DEFAULT_CYBERSECURITY_KEYWORDS)
    return [kw.strip() for kw in raw.split(",") if kw.strip()]
