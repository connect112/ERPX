"""
Bulk downloads: one service for every module's documents.

The request side checks the user may download from the scope, fixes the list of document ids, validates the naming, and
records a job. The work side (the Celery task, or straight away for a small selection) checks the permission again with
the same user, loads only the ids it was given that are still in that scope and organization, writes each document into a
ZIP on local disk, uploads the ZIP to object storage under ``bulk-exports/`` and records it. The ZIP is offered through a
link signed for a few minutes, only to the person who asked for it, and is removed when it expires.

Nothing here changes a document: certificates are rendered with the number they were issued with, stored letters and
files are copied byte for byte.
"""

import os
import tempfile
import time
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, ERPXException, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import User, UserStatus
from modules.bulk_exports import filenames
from modules.bulk_exports.models import ACTIVE, BulkExportJob, ExportStatus
from modules.bulk_exports.sources import get_source
from modules.bulk_exports.sources.base import DocumentSource, ExportItem, Placeholder, Scope

logger = get_logger(__name__)

STORAGE_PREFIX = "bulk-exports/"
MAX_FAILURES_KEPT = 200
FAILURE_REPORT = "_failed_documents.txt"
PROGRESS_EVERY = 10
STALE_AFTER = timedelta(hours=2)
TEMP_PREFIX = "erpx-bulk-"

COMMON_PLACEHOLDERS = (
    Placeholder("document_type", "Document type", "Certificate"),
    Placeholder("index", "Number in this download", "007"),
    Placeholder("export_date", "Download date", "2026-10-30"),
)
ZIP_PLACEHOLDERS = (
    Placeholder("document_type", "Document type", "Certificate"),
    Placeholder("scope_name", "Exam, internship or run", "Cloud Basics Workshop"),
    Placeholder("export_date", "Download date", "2026-10-30"),
    Placeholder("count", "Number of documents", "120"),
)
DEFAULT_ZIP_TEMPLATE = "{{scope_name}}_{{document_type}}_{{export_date}}"

Checkpoint = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class Naming:
    file: filenames.ParsedTemplate
    folder: filenames.ParsedTemplate | None
    zip: filenames.ParsedTemplate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error_text(exc: Exception) -> str:
    if isinstance(exc, ERPXException):
        return exc.message[:300]
    return "The document could not be produced."


class BulkExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- what can be downloaded ----------------

    async def open(self, source_key: str, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> tuple[DocumentSource, Scope]:
        source = get_source(source_key)
        return source, await source.open_scope(self.db, user, organization_id, scope_id)

    @staticmethod
    async def all_placeholders(source: DocumentSource, scope: Scope, db: AsyncSession) -> list[Placeholder]:
        own = await source.placeholders(db, scope)
        keys = {p.key for p in own}
        return [*own, *(p for p in COMMON_PLACEHOLDERS if p.key not in keys)]

    async def describe(self, source: DocumentSource, scope: Scope) -> dict:
        status_options = scope.extra.get("types") or source.status_options
        return {
            "source": source.key,
            "label": source.label,
            "document_type": source.document_type,
            "scope_id": scope.id,
            "scope_label": scope.label,
            "extension": source.extension,
            "placeholders": await self.all_placeholders(source, scope, self.db),
            "zip_placeholders": list(ZIP_PLACEHOLDERS),
            "status_options": list(status_options),
            "presets": [{"label": label, "template": t} for label, t in source.presets],
            "folder_presets": [{"label": label, "template": t} for label, t in source.folder_presets],
            "default_zip_template": DEFAULT_ZIP_TEMPLATE,
            "max_items": settings.BULK_EXPORT_MAX_ITEMS,
        }

    async def list_items(
        self, source: DocumentSource, scope: Scope, search: str | None, status: str | None, page: int, page_size: int
    ) -> tuple[list[ExportItem], int]:
        items = await source.query(self.db, scope, search, status)
        start = (page - 1) * page_size
        return items[start : start + page_size], len(items)

    # ---------------- naming ----------------

    async def naming(self, source: DocumentSource, scope: Scope, options: dict) -> Naming:
        allowed = {p.key for p in await self.all_placeholders(source, scope, self.db)}
        file = filenames.parse(options.get("filename_template") or "", allowed)
        filenames.check_extension(file, source.extension)
        folder_text = (options.get("folder_template") or "").strip().strip("/")
        folder = filenames.parse(folder_text, allowed, what="folder format", allow_slash=True) if folder_text else None
        if folder is not None and folder.extension:
            # a folder named "x.pdf" is unusual but harmless; keep what was typed
            folder = filenames.ParsedTemplate(text=folder_text, keys=folder.keys, extension=None)
        if folder is not None and folder_text.count("/") >= filenames.MAX_FOLDER_DEPTH:
            raise filenames.TemplateError(f"Use at most {filenames.MAX_FOLDER_DEPTH} folder levels.")
        zip_template = (options.get("zip_template") or DEFAULT_ZIP_TEMPLATE).strip()
        if zip_template.lower().endswith(".zip"):
            zip_template = zip_template[:-4]
        zip_parsed = filenames.parse(zip_template, {p.key for p in ZIP_PLACEHOLDERS}, what="ZIP name")
        if zip_parsed.extension:
            raise filenames.TemplateError("The ZIP name always ends in .zip; leave any other extension off.")
        return Naming(file=file, folder=folder, zip=zip_parsed)

    @staticmethod
    def values_for(source: DocumentSource, item: ExportItem, position: int, total: int, today: date) -> dict[str, object]:
        return {
            "document_type": source.document_type,
            **item.values,
            "index": str(position).zfill(max(3, len(str(total)))),
            "export_date": today.isoformat(),
        }

    def zip_filename(self, source: DocumentSource, scope: Scope, naming: Naming, count: int, today: date) -> str:
        return filenames.zip_name(
            naming.zip,
            {"document_type": source.document_type, "scope_name": scope.label, "export_date": today.isoformat(), "count": count},
        )

    # ---------------- choosing the documents ----------------

    async def resolve(self, source: DocumentSource, scope: Scope, selection: dict) -> list[ExportItem]:
        mode = selection.get("mode")
        if mode == "selected":
            ids = list(dict.fromkeys(selection.get("ids") or []))
            if not ids:
                raise ValidationError("Choose at least one document.")
            if len(ids) > settings.BULK_EXPORT_MAX_ITEMS:
                raise ValidationError(f"One download can hold at most {settings.BULK_EXPORT_MAX_ITEMS} documents.")
            items = await source.load(self.db, scope, ids)
        elif mode == "filtered":
            excluded = set(selection.get("exclude_ids") or [])
            items = [
                i for i in await source.query(self.db, scope, selection.get("search"), selection.get("status")) if i.id not in excluded
            ]
        else:
            raise ValidationError("Unknown selection.")
        if not items:
            raise ValidationError("None of the chosen documents can be downloaded.")
        if len(items) > settings.BULK_EXPORT_MAX_ITEMS:
            raise ValidationError(
                f"That is {len(items)} documents; one download can hold at most {settings.BULK_EXPORT_MAX_ITEMS}. Narrow the filters."
            )
        return items

    async def preview(self, source: DocumentSource, scope: Scope, options: dict, selection: dict | None, limit: int = 8) -> dict:
        naming = await self.naming(source, scope, options)
        if selection:
            items = await self.resolve(source, scope, selection)
        else:
            items = await source.query(self.db, scope, None, None)
        today = _now().date()
        names = filenames.UniqueNames()
        files = []
        missing_counts: dict[str, int] = {}
        for position, item in enumerate(items, start=1):
            values = self.values_for(source, item, position, len(items), today)
            folder, gone_folder = filenames.folder_path(naming.folder, values)
            name, gone = filenames.file_name(naming.file, values, item.extension, f"{source.document_type}_{values['index']}")
            path = names.claim(folder, name)
            for key in {*gone, *gone_folder}:
                missing_counts[key] = missing_counts.get(key, 0) + 1
            if len(files) < limit:
                files.append({"id": item.id, "title": item.title, "path": path, "missing": sorted({*gone, *gone_folder})})
        warnings = [
            f"{{{{{key}}}}} is empty for {count} document{'s' if count != 1 else ''}; it is left out of their names."
            for key, count in sorted(missing_counts.items())
        ]
        if not naming.file.keys:
            warnings.append("The file name has no placeholder, so every file gets the same name plus a number.")
        return {
            "zip_filename": self.zip_filename(source, scope, naming, len(items), today),
            "total": len(items),
            "files": files,
            "warnings": warnings,
            "renamed_duplicates": names.renamed,
        }

    # ---------------- jobs ----------------

    async def create_job(self, user: User, organization_id: uuid.UUID, source_key: str, scope_id: uuid.UUID | None, selection: dict, options: dict) -> BulkExportJob:
        source, scope = await self.open(source_key, user, organization_id, scope_id)
        await self.naming(source, scope, options)
        active = (
            await self.db.execute(
                select(func.count()).where(BulkExportJob.requested_by_user_id == user.id, BulkExportJob.status.in_(ACTIVE))
            )
        ).scalar_one()
        if active >= settings.BULK_EXPORT_MAX_ACTIVE_PER_USER:
            raise ConflictError("You already have downloads being prepared. Wait for one to finish, or cancel it.")
        items = await self.resolve(source, scope, selection)
        job = BulkExportJob(
            organization_id=organization_id,
            requested_by_user_id=user.id,
            source=source.key,
            scope_id=scope.id,
            scope_label=scope.label[:255],
            status=ExportStatus.QUEUED.value,
            selection_mode=selection["mode"],
            filters={k: selection.get(k) for k in ("search", "status") if selection.get(k)},
            item_ids=[str(i.id) for i in items],
            options={
                "filename_template": options.get("filename_template"),
                "folder_template": options.get("folder_template") or "",
                "zip_template": options.get("zip_template") or DEFAULT_ZIP_TEMPLATE,
            },
            total_items=len(items),
        )
        self.db.add(job)
        await self.db.flush()
        logger.info("bulk_export_created", job_id=str(job.id), source=source.key, items=len(items))
        return job

    async def _job(self, organization_id: uuid.UUID, job_id: uuid.UUID, user: User) -> BulkExportJob:
        job = (
            await self.db.execute(
                select(BulkExportJob).where(BulkExportJob.id == job_id, BulkExportJob.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        # Only the person who asked for a download sees it; to anyone else it does not exist.
        if job is None or job.requested_by_user_id != user.id:
            raise NotFoundError("Download", job_id)
        return job

    async def get_job(self, user: User, organization_id: uuid.UUID, job_id: uuid.UUID) -> BulkExportJob:
        return await self._job(organization_id, job_id, user)

    async def list_jobs(self, user: User, organization_id: uuid.UUID, limit: int = 50) -> list[BulkExportJob]:
        rows = await self.db.execute(
            select(BulkExportJob)
            .where(BulkExportJob.organization_id == organization_id, BulkExportJob.requested_by_user_id == user.id)
            .order_by(BulkExportJob.created_at.desc())
            .limit(limit)
        )
        return list(rows.scalars())

    async def cancel(self, user: User, organization_id: uuid.UUID, job_id: uuid.UUID) -> BulkExportJob:
        job = await self._job(organization_id, job_id, user)
        if job.status not in ACTIVE:
            raise ConflictError("This download is no longer being prepared.")
        job.status = ExportStatus.CANCELLED.value
        job.finished_at = _now()
        await self.db.flush()
        return job

    async def discard(self, user: User, organization_id: uuid.UUID, job_id: uuid.UUID) -> BulkExportJob:
        """Remove the ZIP now instead of waiting for it to expire. The job stays as the record."""
        job = await self._job(organization_id, job_id, user)
        if job.status in ACTIVE:
            raise ConflictError("Cancel the download first.")
        await self._remove_zip(job)
        if job.status == ExportStatus.COMPLETED.value:
            job.status = ExportStatus.EXPIRED.value
        await self.db.flush()
        return job

    async def download_link(self, user: User, organization_id: uuid.UUID, job_id: uuid.UUID) -> tuple[str, BulkExportJob]:
        from packages.storage.client import get_storage_client

        job = await self._job(organization_id, job_id, user)
        if job.status == ExportStatus.EXPIRED.value or (job.expires_at and job.expires_at <= _now()):
            raise ConflictError("This download has expired. Start a new one.")
        if job.status != ExportStatus.COMPLETED.value or not job.storage_key:
            raise ConflictError("This download is not ready.")
        # The permission is checked again: someone who lost access since cannot collect the file.
        await self.open(job.source, user, organization_id, job.scope_id)
        url = get_storage_client().presigned_download_url(
            job.storage_key,
            expires=timedelta(minutes=settings.BULK_EXPORT_LINK_MINUTES),
            download_name=job.zip_filename or "documents.zip",
        )
        job.download_count += 1
        job.last_downloaded_at = _now()
        await self.db.flush()
        logger.info("bulk_export_downloaded", job_id=str(job.id), user_id=str(user.id))
        return url, job

    # ---------------- doing the work ----------------

    async def _still_wanted(self, job: BulkExportJob, commits: bool) -> bool:
        if commits:
            current = (await self.db.execute(select(BulkExportJob.status).where(BulkExportJob.id == job.id))).scalar_one_or_none()
            if current == ExportStatus.CANCELLED.value:
                job.status = current
                return False
        return job.status != ExportStatus.CANCELLED.value

    async def run(self, job: BulkExportJob, checkpoint: Checkpoint, *, commits: bool = False) -> BulkExportJob:
        """Build and store the ZIP. ``checkpoint`` makes progress visible (a commit in the worker, a flush inline).
        Never raises for a problem with the documents: the job ends failed with the reason instead."""
        if job.status != ExportStatus.QUEUED.value:
            return job
        job_id = job.id
        job.status = ExportStatus.RUNNING.value
        job.started_at = _now()
        await checkpoint()
        path: str | None = None
        try:
            user = await self.db.get(User, job.requested_by_user_id) if job.requested_by_user_id else None
            if user is None or user.status != UserStatus.ACTIVE:
                raise ValidationError("The person who asked for this download no longer has an active account.")
            source, scope = await self.open(job.source, user, job.organization_id, job.scope_id)
            naming = await self.naming(source, scope, job.options)
            ids = [uuid.UUID(i) for i in job.item_ids]
            items = await source.load(self.db, scope, ids)
            found = {i.id for i in items}
            failures = [{"id": str(i), "title": "", "error": "No longer available."} for i in ids if i not in found]
            today = _now().date()
            names = filenames.UniqueNames()
            written = 0
            total_bytes = 0
            deadline = time.monotonic() + settings.BULK_EXPORT_MAX_SECONDS
            fd, path = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=".zip")
            os.close(fd)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                for position, item in enumerate(items, start=1):
                    if time.monotonic() > deadline:
                        raise ValidationError(
                            "This download took too long to prepare in one go. Choose fewer documents and try again."
                        )
                    if position % PROGRESS_EVERY == 0:
                        if not await self._still_wanted(job, commits):
                            logger.info("bulk_export_cancelled", job_id=str(job.id))
                            return job
                        job.processed_items = written
                        job.failed_items = len(failures)
                        await checkpoint()
                    try:
                        data = await source.fetch(self.db, scope, item)
                    except Exception as exc:  # noqa: BLE001 - one bad document must not stop the others
                        logger.warning("bulk_export_item_failed", job_id=str(job.id), item_id=str(item.id), exc_info=True)
                        failures.append({"id": str(item.id), "title": item.title, "error": _error_text(exc)})
                        continue
                    total_bytes += len(data)
                    if total_bytes > settings.BULK_EXPORT_MAX_BYTES:
                        raise ValidationError("The documents add up to more than one download can hold. Choose fewer.")
                    values = self.values_for(source, item, position, len(items), today)
                    folder, _ = filenames.folder_path(naming.folder, values)
                    name, _ = filenames.file_name(naming.file, values, item.extension, f"{source.document_type}_{values['index']}")
                    entry = zipfile.ZipInfo(names.claim(folder, name), date_time=_now().timetuple()[:6])
                    entry.external_attr = 0o644 << 16
                    archive.writestr(entry, data, zipfile.ZIP_DEFLATED)
                    written += 1
                if failures:
                    report = "\n".join(f"{f['title'] or f['id']}: {f['error']}" for f in failures)
                    archive.writestr(names.claim("", FAILURE_REPORT), "These documents could not be added:\n" + report + "\n")
            job.processed_items = written
            job.failed_items = len(failures)
            job.failures = failures[:MAX_FAILURES_KEPT]
            if written == 0:
                raise ValidationError("None of the documents could be added.")
            if not await self._still_wanted(job, commits):
                return job
            await self._store(job, path, self.zip_filename(source, scope, naming, written, today))
        except Exception as exc:  # noqa: BLE001 - the job records the failure; the caller is never left hanging
            if not isinstance(exc, ERPXException):
                logger.exception("bulk_export_failed", job_id=str(job_id))
            if commits:
                # the session may be unusable after a database error: start clean and load the job again
                await self.db.rollback()
                job = await self.db.get(BulkExportJob, job_id, populate_existing=True)
            job.status = ExportStatus.FAILED.value
            job.error = (exc.message if isinstance(exc, ERPXException) else "The download could not be prepared.")[:500]
            job.finished_at = _now()
        finally:
            if path and os.path.exists(path):
                os.unlink(path)
        await checkpoint()
        return job

    async def _store(self, job: BulkExportJob, path: str, zip_filename: str) -> None:
        from packages.storage.client import get_storage_client

        key = f"{STORAGE_PREFIX}{job.organization_id}/{job.id}.zip"
        await get_storage_client().upload_file(key, path, "application/zip")
        job.storage_key = key
        job.zip_filename = zip_filename
        job.size_bytes = os.path.getsize(path)
        job.status = ExportStatus.COMPLETED.value
        job.finished_at = _now()
        job.expires_at = job.finished_at + timedelta(hours=settings.BULK_EXPORT_RETENTION_HOURS)
        logger.info("bulk_export_completed", job_id=str(job.id), items=job.processed_items, bytes=job.size_bytes)

    async def _remove_zip(self, job: BulkExportJob) -> None:
        from packages.storage.client import get_storage_client

        if job.storage_key:
            if not job.storage_key.startswith(STORAGE_PREFIX):  # never touch anything but our own ZIPs
                raise ValidationError("Unexpected storage location.")
            await get_storage_client().delete_object(job.storage_key)
            job.storage_key = None

    async def cleanup(self) -> dict[str, int]:
        """Remove expired ZIPs, and end jobs a crashed worker left behind."""
        now = _now()
        expired = (
            await self.db.execute(
                select(BulkExportJob).where(BulkExportJob.status == ExportStatus.COMPLETED.value, BulkExportJob.expires_at <= now)
            )
        ).scalars().all()
        removed = 0
        for job in expired:
            try:
                await self._remove_zip(job)
            except Exception:  # noqa: BLE001 - try again on the next run
                logger.warning("bulk_export_cleanup_failed", job_id=str(job.id), exc_info=True)
                continue
            job.status = ExportStatus.EXPIRED.value
            removed += 1
        stale = (
            await self.db.execute(
                select(BulkExportJob).where(BulkExportJob.status.in_(ACTIVE), BulkExportJob.created_at <= now - STALE_AFTER)
            )
        ).scalars().all()
        for job in stale:
            job.status = ExportStatus.FAILED.value
            job.error = "The download stopped before it finished. Please start it again."
            job.finished_at = now
        await self.db.flush()
        return {"expired": removed, "stale": len(stale), "temp_files": self.sweep_temp_files()}

    @staticmethod
    def sweep_temp_files(older_than: timedelta = STALE_AFTER) -> int:
        """Delete half-built ZIPs a killed worker left in its temporary folder (normally ``run`` always removes its own)."""
        cutoff = time.time() - older_than.total_seconds()
        removed = 0
        folder = tempfile.gettempdir()
        for name in os.listdir(folder):
            if not (name.startswith(TEMP_PREFIX) and name.endswith(".zip")):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.unlink(path)
                    removed += 1
            except OSError:
                continue
        return removed
