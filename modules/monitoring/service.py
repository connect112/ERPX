"""
Monitoring module — live, read-only system health.

Every number here comes from a real check against the actual running
system (a real `SELECT 1` against the live DB connection pool, a real
MinIO bucket-exists call, a real Redis PING, real `COUNT(*)` queries) —
nothing is cached or synthesized. There's deliberately no persistence
layer: health is a snapshot of *right now*, not a history you'd want a
table for (that's what Prometheus/Grafana in `docker-compose.yml`'s
`monitoring` profile are for — this is the in-app "is everything up"
view an admin reaches for without needing that stack running).
"""

import time
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import engine
from modules.audit.models import AuditLog
from modules.authentication.models import User
from modules.organizations.models import Organization
from modules.students.models import Student
from packages.storage.client import get_storage_client

logger = get_logger(__name__)


class SystemHealthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_database(self) -> dict:
        start = time.monotonic()
        try:
            await self.db.execute(text("SELECT 1"))
            latency_ms = (time.monotonic() - start) * 1000
            pool = engine.pool
            return {
                "component": "database",
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "detail": f"pool: {pool.checkedout()}/{pool.size()} connections in use",
                "message": None,
            }
        except Exception as exc:
            logger.exception("monitoring_database_check_failed")
            return {
                "component": "database",
                "status": "unhealthy",
                "latency_ms": None,
                "detail": None,
                "message": str(exc)[:500],
            }

    async def check_storage(self) -> dict:
        start = time.monotonic()
        try:
            storage = get_storage_client()
            await storage.ensure_bucket()
            latency_ms = (time.monotonic() - start) * 1000
            return {
                "component": "storage",
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "detail": f"bucket: {storage.bucket}",
                "message": None,
            }
        except Exception as exc:
            logger.warning("monitoring_storage_check_failed", error=str(exc))
            return {
                "component": "storage",
                "status": "unhealthy",
                "latency_ms": None,
                "detail": None,
                "message": str(exc)[:500],
            }

    async def check_redis(self) -> dict:
        start = time.monotonic()
        client = redis_asyncio.from_url(
            settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
        )
        try:
            await client.ping()
            latency_ms = (time.monotonic() - start) * 1000
            return {
                "component": "redis",
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "detail": None,
                "message": None,
            }
        except Exception as exc:
            logger.warning("monitoring_redis_check_failed", error=str(exc))
            return {
                "component": "redis",
                "status": "unhealthy",
                "latency_ms": None,
                "detail": None,
                "message": str(exc)[:300],
            }
        finally:
            await client.aclose()

    async def get_all_checks(self) -> list[dict]:
        return [
            await self.check_database(),
            await self.check_storage(),
            await self.check_redis(),
        ]

    async def get_platform_stats(self) -> dict:
        org_count = (await self.db.execute(select(func.count()).select_from(Organization))).scalar_one()
        user_count = (await self.db.execute(select(func.count()).select_from(User))).scalar_one()
        student_count = (await self.db.execute(select(func.count()).select_from(Student))).scalar_one()

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_audit_count = (
            await self.db.execute(
                select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= since)
            )
        ).scalar_one()

        return {
            "organization_count": org_count,
            "user_count": user_count,
            "student_count": student_count,
            "audit_events_last_24h": recent_audit_count,
        }
