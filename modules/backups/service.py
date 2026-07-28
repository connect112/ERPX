import asyncio
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.backups.models import BackupJob, BackupStatus
from modules.backups.repository import BackupJobRepository
from packages.storage.client import get_storage_client

logger = get_logger(__name__)


class BackupService:
    """
    Runs a real `pg_dump` of the whole database and uploads the result to
    object storage — no mock, no placeholder file. Executed inline within
    the request rather than dispatched to a Celery worker: this platform's
    Celery broker (Redis) isn't guaranteed to be reachable in every
    deployment of this codebase, and a synchronous `pg_dump` of a
    reasonably-sized database completes in well under the request timeout.
    A production deployment with a large database should move this to a
    background job instead.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BackupJobRepository(db)
        self.storage = get_storage_client()

    async def trigger_backup(self, triggered_by_user_id: uuid.UUID | None) -> BackupJob:
        job = await self.repo.create(
            triggered_by_user_id=triggered_by_user_id,
            status=BackupStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        tmp_path = None
        try:
            parsed = urlparse(settings.DATABASE_URL.replace("+asyncpg", ""))
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password

            fd, tmp_path = tempfile.mkstemp(suffix=".sql")
            os.close(fd)

            # asyncio.create_subprocess_exec requires ProactorEventLoop on
            # Windows (SelectorEventLoop, used by this test/uvicorn setup,
            # raises NotImplementedError for subprocesses) — a thread-
            # dispatched blocking subprocess.run works identically on every
            # platform without depending on which loop is active.
            def _run_pg_dump() -> subprocess.CompletedProcess:
                return subprocess.run(
                    [
                        settings.PG_DUMP_PATH,
                        "-h", parsed.hostname or "localhost",
                        "-p", str(parsed.port or 5432),
                        "-U", parsed.username or "",
                        "-d", (parsed.path or "").lstrip("/"),
                        "-f", tmp_path,
                        "--no-owner",
                        "--no-privileges",
                    ],
                    env=env,
                    capture_output=True,
                )

            result = await asyncio.to_thread(_run_pg_dump)

            if result.returncode != 0:
                raise RuntimeError(
                    f"pg_dump exited with code {result.returncode}: {result.stderr.decode(errors='replace')[:2000]}"
                )

            size_bytes = os.path.getsize(tmp_path)
            storage_key = f"backups/{job.id}.sql"
            await self.storage.ensure_bucket()
            await self.storage.upload_file(storage_key, tmp_path, content_type="application/sql")

            job = await self.repo.update(
                job,
                status=BackupStatus.COMPLETED,
                storage_key=storage_key,
                size_bytes=size_bytes,
                completed_at=datetime.now(timezone.utc),
            )
            logger.info("backup_completed", job_id=str(job.id), size_bytes=size_bytes)
        except Exception as exc:
            logger.exception("backup_failed", job_id=str(job.id))
            job.status = BackupStatus.FAILED
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(job)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        return job

    async def get_job(self, job_id: uuid.UUID) -> BackupJob:
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Backup job", job_id)
        return job

    async def list_jobs(self, **filters):
        return await self.repo.list_all(**filters)

    async def get_download_url(self, job_id: uuid.UUID) -> str:
        job = await self.get_job(job_id)
        if job.status != BackupStatus.COMPLETED or not job.storage_key:
            raise NotFoundError("Completed backup", job_id)
        return self.storage.presigned_download_url(job.storage_key)
