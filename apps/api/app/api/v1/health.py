"""
Health, readiness, and liveness endpoints.

Dependency classification
--------------------------
Not every dependency the platform talks to is required to serve traffic.
Kubernetes's readiness probe (`infrastructure/kubernetes/api-deployment.yaml`)
uses this endpoint's HTTP status code to decide whether to route traffic to a
pod, so only a dependency whose absence would break the *majority* of
requests should be allowed to fail readiness. Marking every integration
"critical" means a single non-essential dependency going down takes the
*entire* platform out of rotation — a worse outcome than that dependency
alone being degraded.

  * Critical — required for most requests to function at all.
    - database (PostgreSQL): auth, RBAC, and virtually every endpoint reads
      or writes it.

  * Optional — required only for specific features, not the platform as a
    whole; still reported here (with `critical: false`) so operators see a
    degraded-but-serving pod at a glance, but a failure here never fails
    readiness.
    - redis: the Celery broker. Two request-time `.delay()` calls in
      `modules.authentication.service` (registration / password-reset
      verification emails) touch it synchronously, and scheduled/background
      jobs (`modules/reports/tasks.py`, `modules/accounting/invoices/tasks.py`,
      `modules/crm/followups/tasks.py`) depend on it — but no other endpoint's
      request/response cycle does. `modules/backups/service.py` already
      documents that Redis "isn't guaranteed to be reachable in every
      deployment of this codebase" and designs around that.
    - storage (MinIO): only document/media upload-download and backup
      download features use it.
    - search (Elasticsearch): nothing in the codebase queries it yet
      (`packages/search/` is empty) — there is no feature to break.

/health       — liveness: no dependency calls, just "is the process up".
/health/ready — readiness: fails (503) only if a CRITICAL dependency is
                unhealthy; every dependency's status and classification is
                always reported in the body regardless of outcome.
"""

import redis.asyncio as aioredis
from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from minio import Minio
from pydantic import BaseModel

from app.core.config import settings
from app.db.session import check_db_connection

router = APIRouter(tags=["Health"])


class DependencyCheck(BaseModel):
    healthy: bool
    critical: bool


async def check_database() -> bool:
    return await check_db_connection()


async def check_redis() -> bool:
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL)
        try:
            return bool(await redis_client.ping())
        finally:
            await redis_client.aclose()
    except Exception:
        return False


async def check_storage() -> bool:
    try:
        minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        # Previously `... or True`, which made this check always report
        # healthy regardless of the real result — fixed while touching this
        # function for the readiness-gate change below.
        return bool(minio_client.bucket_exists(settings.MINIO_BUCKET))
    except Exception:
        return False


async def check_search() -> bool:
    try:
        es_client = AsyncElasticsearch(hosts=[settings.ELASTICSEARCH_URL])
        try:
            return bool(await es_client.ping())
        finally:
            await es_client.close()
    except Exception:
        return False


# name -> (checker function's attribute name, is_critical). Stored as a
# name string and resolved via `globals()` inside `readiness()` below —
# rather than the function object directly — so that tests can
# `monkeypatch.setattr(health_module, "check_database", fake)` and have
# `readiness()` actually call the replacement. A dict built with direct
# function references would freeze in the *original* functions at import
# time and silently ignore any later monkeypatch of the module attribute.
#
# Order here is the order dependencies are checked and reported in the
# response body.
DEPENDENCY_CHECKS: dict[str, tuple[str, bool]] = {
    "database": ("check_database", True),
    "redis": ("check_redis", False),
    "storage": ("check_storage", False),
    "search": ("check_search", False),
}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    checks: dict[str, DependencyCheck] = {}
    for name, (checker_name, critical) in DEPENDENCY_CHECKS.items():
        checker = globals()[checker_name]
        checks[name] = DependencyCheck(healthy=await checker(), critical=critical)

    critical_failures = [name for name, check in checks.items() if check.critical and not check.healthy]
    ready = not critical_failures

    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if ready else "not_ready",
            "live": True,
            "ready": ready,
            "checks": {name: check.model_dump() for name, check in checks.items()},
        },
    )
