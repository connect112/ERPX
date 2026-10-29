"""
Storage Manager service: the inventory of every stored file, dependency analysis, usage figures, Trash and deletion.

Safety rules enforced here, not only in the UI:
  * Only an unreferenced file in object storage can ever be moved to Trash, and only by a platform superuser.
  * Eligibility is re-checked on the server at the moment of deletion, with a scan of every table that could point at
    the file, not just the registry.
  * A deletion moves the file to `.trash/` (still in the bucket) and records it. Nothing is permanently removed except
    by a separate, manual purge of items that have sat in Trash for at least STORAGE_TRASH_MIN_DAYS.
  * Business records are never touched: no row is deleted or changed except this module's own trash and log rows.
"""

import asyncio
import base64
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import get_audit_context
from app.core.config import settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.storage_manager import registry
from modules.storage_manager.models import StorageDeletionLog, StorageTrash
from modules.storage_manager.schemas import (
    Analysis,
    DeletionLogItem,
    DuplicateGroup,
    Evidence,
    FileItem,
    FilesUsage,
    FolderItem,
    SourceUsage,
    TrashItem,
    TypeUsage,
)
from packages.storage.client import get_storage_client, public_url

logger = get_logger(__name__)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# Columns that could plausibly hold the key or URL of a stored file, in tables the registry does not know about.
REFERENCE_COLUMN_RE = re.compile(r"(key|path|url|file|avatar|logo|photo|image|attachment|media|asset|document|thumb)", re.I)
REFERENCE_SCAN_SKIP_TABLES = {"audit_logs", "storage_trash", "storage_deletion_log", "alembic_version"}
PREVIEW_URL_SECONDS = 300
MAX_CONTENT_BYTES = 100 * 1024 * 1024


@dataclass
class Viewer:
    """Who is asking: platform superusers see everything, everyone else only their own organization."""

    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    is_superuser: bool

    def can_see(self, organization_id: uuid.UUID | None) -> bool:
        if self.is_superuser:
            return True
        return organization_id is not None and organization_id == self.organization_id


@dataclass
class ObjectInfo:
    size: int
    etag: str | None
    modified: datetime | None


class ObjectStore:
    """The bucket, with the blocking MinIO SDK moved off the event loop."""

    def __init__(self) -> None:
        storage = get_storage_client()
        self._client = storage._client  # noqa: SLF001 - the shared client does not expose list/copy
        self.bucket = storage.bucket

    async def list_all(self, limit: int = 200_000) -> dict[str, ObjectInfo]:
        def _list() -> dict[str, ObjectInfo]:
            found: dict[str, ObjectInfo] = {}
            for obj in self._client.list_objects(self.bucket, recursive=True):
                if obj.is_dir:
                    continue
                found[obj.object_name] = ObjectInfo(obj.size or 0, (obj.etag or "").strip('"') or None, obj.last_modified)
                if len(found) >= limit:
                    break
            return found

        return await asyncio.to_thread(_list)

    async def stat(self, key: str):
        return await asyncio.to_thread(self._client.stat_object, self.bucket, key)

    async def exists(self, key: str) -> bool:
        try:
            await self.stat(key)
            return True
        except Exception:  # noqa: BLE001 - a missing object is the expected "no"
            return False

    async def copy(self, source_key: str, target_key: str) -> None:
        from minio.commonconfig import CopySource

        await asyncio.to_thread(self._client.copy_object, self.bucket, target_key, CopySource(self.bucket, source_key))

    async def remove(self, key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, self.bucket, key)

    async def read(self, key: str) -> bytes:
        def _read() -> bytes:
            response = self._client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(_read)

    def presign(self, key: str, filename: str, content_type: str | None, inline: bool) -> str:
        disposition = f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(filename or 'file')}"
        headers = {"response-content-disposition": disposition}
        if content_type:
            headers["response-content-type"] = content_type
        url = self._client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=PREVIEW_URL_SECONDS), response_headers=headers
        )
        return public_url(url)


def encode_orphan_id(key: str) -> str:
    return "o:" + base64.urlsafe_b64encode(key.encode()).decode().rstrip("=")


def decode_orphan_id(item_id: str) -> str:
    raw = item_id[2:]
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()


def _directories(key: str, org_names: dict[str, str]) -> list[str]:
    parts = key.split("/")[:-1]
    return [org_names.get(part, part) if UUID_RE.match(part) else part for part in parts]


def _as_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class Inventory:
    def __init__(self, items: list[FileItem], listing: dict[str, ObjectInfo], org_names: dict[str, str]):
        self.items = items
        self.by_id = {item.id: item for item in items}
        self.listing = listing
        self.org_names = org_names


class StorageManagerService:
    def __init__(self, db: AsyncSession, store: ObjectStore | None = None):
        self.db = db
        self.store = store or ObjectStore()

    # ---- inventory -----------------------------------------------------------------------------------------

    async def inventory(self, viewer: Viewer) -> Inventory:
        org_rows = (await self.db.execute(text("select id::text, name from organizations"))).all()
        org_names = {row[0]: row[1] for row in org_rows}
        listing = await self.store.list_all()
        items: list[FileItem] = []
        referenced: set[str] = set()

        for source in registry.OBJECT_SOURCES:
            owner_join = f"left join users u on u.id = t.{source.owner_col}" if source.owner_col else ""
            sql = (
                f"select t.id::text, {'t.' + source.org_col if source.org_col else 'null'}, t.{source.name_col}, "
                f"coalesce(t.{source.size_col}, 0)::bigint, {'t.' + source.type_col if source.type_col else 'null'}, "
                f"t.{source.key_col}, t.created_at, {'u.email' if source.owner_col else 'null'}, "
                f"{'t.' + source.status_col + '::text' if source.status_col else 'null'} "
                f"from {source.table} t {owner_join} where t.{source.key_col} is not null"
            )
            for rid, org, name, size, ctype, key, created, owner, status_value in (await self.db.execute(text(sql))).all():
                referenced.add(key)
                info = listing.get(key)
                organization_id = _as_uuid(org)
                protected = bool(source.protected_reason) or registry.is_protected_key(key)
                if info is None:
                    status = "missing_object"
                elif protected:
                    status = "protected"
                elif status_value == "pending":
                    status = "pending"
                else:
                    status = "in_use"
                display = os.path.basename(name) if source.key == "backups" else name
                items.append(
                    FileItem(
                        id=f"m:{source.key}:{rid}", source=source.key, source_label=source.label, module=source.module,
                        backend="object_storage", name=display,
                        path=["Object storage", source.label, *_directories(key, org_names)],
                        size_bytes=int(size or (info.size if info else 0)), content_type=ctype,
                        type_group=registry.type_group(ctype or ("application/sql" if key.endswith(".sql") else None)),
                        created_at=created, owner=owner, organization_id=organization_id,
                        organization_name=org_names.get(str(organization_id)) if organization_id else None,
                        location=f"object storage: {self.store.bucket}/{key}", status=status, protected=protected,
                        protected_reason=source.protected_reason or ("Under a protected folder." if protected else None),
                        fingerprint=(f"{info.etag}:{info.size}" if info and info.etag else None),
                        is_large=int(size or 0) >= registry.LARGE_FILE_BYTES,
                        previewable=registry.preview_kind(ctype),
                    )
                )

        for key, info in sorted(listing.items()):
            if key in referenced or key.startswith(registry.TRASH_PREFIX):
                continue
            first = key.split("/", 1)[0]
            organization_id = uuid.UUID(first) if UUID_RE.match(first) and first in org_names else None
            protected = registry.is_protected_key(key)
            ctype = _guess_type(key)
            items.append(
                FileItem(
                    id=encode_orphan_id(key), source="orphans", source_label="Unreferenced files", module="storage",
                    backend="object_storage", name=os.path.basename(key),
                    path=["Object storage", "Unreferenced files", *_directories(key, org_names)],
                    size_bytes=info.size, content_type=ctype, type_group=registry.type_group(ctype),
                    created_at=info.modified, owner=None, organization_id=organization_id,
                    organization_name=org_names.get(str(organization_id)) if organization_id else None,
                    location=f"object storage: {self.store.bucket}/{key}",
                    status="protected" if protected else "orphan", protected=protected,
                    protected_reason="Under a protected folder (database backups)." if protected else None,
                    fingerprint=(f"{info.etag}:{info.size}" if info.etag else None),
                    is_large=info.size >= registry.LARGE_FILE_BYTES, previewable=registry.preview_kind(ctype),
                )
            )

        for source in registry.DATABASE_SOURCES:
            owner_join = f"left join users u on u.id = t.{source.owner_col}" if source.owner_col else ""
            # Names and types can be expressions over the table's own columns, so they are evaluated in the query.
            sql = (
                f"select t.id::text, {'t.' + source.org_col if source.org_col else 'null'}, {source.name_expr}, "
                f"({source.size_expr})::bigint, ({source.type_expr}), t.created_at, "
                f"{'u.email' if source.owner_col else 'null'} from {source.table} t {owner_join} where {source.where}"
            )
            for rid, org, name, size, ctype, created, owner in (await self.db.execute(text(sql))).all():
                organization_id = _as_uuid(org)
                items.append(
                    FileItem(
                        id=f"d:{source.key}:{rid}", source=source.key, source_label=source.label, module=source.module,
                        backend="database", name=name, path=["Database files", source.label], size_bytes=int(size or 0),
                        content_type=ctype, type_group=registry.type_group(ctype), created_at=created, owner=owner,
                        organization_id=organization_id,
                        organization_name=org_names.get(str(organization_id)) if organization_id else None,
                        location=f"database: {source.table}.{source.data_col} (row {rid})", status="protected",
                        protected=True, protected_reason=source.protected_reason,
                        is_large=int(size or 0) >= registry.LARGE_FILE_BYTES, previewable=registry.preview_kind(ctype),
                    )
                )

        visible = [item for item in items if viewer.can_see(item.organization_id)]
        return Inventory(visible, listing, org_names)

    # ---- browsing ------------------------------------------------------------------------------------------

    def browse(
        self,
        inv: Inventory,
        *,
        path: list[str],
        q: str | None = None,
        source: str | None = None,
        status: str | None = None,
        type_group: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        owner: str | None = None,
        large: bool | None = None,
        sort: str = "name",
        order: str = "asc",
        page: int = 1,
        page_size: int = 50,
    ):
        def matches(item: FileItem) -> bool:
            if source and item.source != source:
                return False
            if status and item.status != status:
                return False
            if type_group and item.type_group != type_group:
                return False
            if min_size is not None and item.size_bytes < min_size:
                return False
            if max_size is not None and item.size_bytes > max_size:
                return False
            if date_from and (item.created_at is None or item.created_at < date_from):
                return False
            if date_to and (item.created_at is None or item.created_at > date_to):
                return False
            if owner and owner.lower() not in (item.owner or "").lower():
                return False
            if large is not None and item.is_large != large:
                return False
            if q:
                needle = q.lower()
                haystack = f"{item.name} {item.location} {item.source_label} {item.owner or ''}".lower()
                if needle not in haystack:
                    return False
            return True

        flat = bool(q or source or status or type_group or min_size is not None or max_size is not None
                    or date_from or date_to or owner or large is not None)
        # A search or filter looks across all storage and lists matches as one flat list; without one, the folder
        # at `path` is shown with its direct files and sub-folders.
        in_subtree = [i for i in inv.items if matches(i)] if flat else [i for i in inv.items if i.path[: len(path)] == path]
        subtree_count = len(in_subtree)
        subtree_bytes = sum(i.size_bytes for i in in_subtree)
        if flat:
            files, folders = in_subtree, []
        else:
            files = [i for i in in_subtree if len(i.path) == len(path)]
            buckets: dict[str, list[FileItem]] = {}
            for item in in_subtree:
                if len(item.path) > len(path):
                    buckets.setdefault(item.path[len(path)], []).append(item)
            folders = [
                FolderItem(name=name, path=[*path, name], file_count=len(members),
                           total_bytes=sum(m.size_bytes for m in members))
                for name, members in sorted(buckets.items())
            ]

        keys = {
            "name": lambda i: i.name.lower(), "size": lambda i: i.size_bytes,
            "date": lambda i: i.created_at or datetime.min.replace(tzinfo=timezone.utc),
            "source": lambda i: i.source_label.lower(), "status": lambda i: i.status,
            "owner": lambda i: (i.owner or "").lower(), "type": lambda i: i.type_group,
        }
        files = sorted(files, key=keys.get(sort, keys["name"]), reverse=(order == "desc"))
        total_bytes = sum(f.size_bytes for f in files)
        start = (max(page, 1) - 1) * page_size
        return files[start:start + page_size], folders, len(files), total_bytes, flat, subtree_count, subtree_bytes

    # ---- dependency analysis -------------------------------------------------------------------------------

    async def find_references(self, key: str) -> list[Evidence]:
        """Every table column that mentions this file's key or URL, beyond the registry's own sources."""
        columns = (await self.db.execute(text(
            "select table_name, column_name, data_type from information_schema.columns "
            "where table_schema = 'public' and data_type in ('character varying', 'text', 'jsonb')"
        ))).all()
        pattern = "%" + key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        found: list[Evidence] = []
        for table, column, _ in columns:
            if table in REFERENCE_SCAN_SKIP_TABLES or not REFERENCE_COLUMN_RE.search(column):
                continue
            count = (await self.db.execute(
                text(f'select count(*) from "{table}" where "{column}"::text like :p escape \'\\\''), {"p": pattern}
            )).scalar_one()
            if count:
                found.append(Evidence(kind="reference", module=table,
                                      text=f"{count} row(s) in {table}.{column} mention this file."))
        return found

    async def analyze(self, inv: Inventory, item_id: str, viewer: Viewer) -> Analysis:
        item = inv.by_id.get(item_id)
        if item is None:
            raise NotFoundError("Stored file", item_id)
        evidence: list[Evidence] = []
        reasons: list[str] = []
        if item.protected:
            reasons.append(item.protected_reason or "Protected.")
            evidence.append(Evidence(kind="protected", text=item.protected_reason or "Protected.", module=item.module))
            verdict = "protected"
        elif item.status == "missing_object":
            rid = item.id.split(":")[-1]
            reasons.append("The record points to a file that is no longer in storage. There is nothing to delete.")
            evidence.append(Evidence(kind="record", module=item.module, record_id=rid,
                                     text=f"{item.source_label} record {rid} points to a missing file."))
            verdict = "missing"
        elif item.status in ("in_use", "pending"):
            rid = item.id.split(":")[-1]
            reasons.append(f"Still used by a {item.source_label} record.")
            evidence.append(Evidence(kind="record", module=item.module, record_id=rid,
                                     text=f"Used by {item.source_label} record {rid}"
                                          + (f" (owner {item.owner})" if item.owner else "") + "."))
            verdict = "in_use"
        else:  # an unreferenced object: check every table that could still point at it
            key = decode_orphan_id(item.id)
            references = await self.find_references(key)
            if references:
                evidence.extend(references)
                reasons.append("Other tables still mention this file, so it is treated as in use.")
                verdict = "in_use"
            else:
                evidence.append(Evidence(kind="note", text="No record in any registered source or any file-like "
                                                           "column mentions this file."))
                verdict = "eligible"
        can_delete = verdict == "eligible" and viewer.is_superuser
        if verdict == "eligible" and not viewer.is_superuser:
            reasons.append("Only platform superusers can delete files.")
        return Analysis(item=item, verdict=verdict, can_delete=can_delete, reasons=reasons, evidence=evidence)

    async def fingerprint_database_files(self, inv: Inventory) -> None:
        """Content fingerprints for files kept inside the database, computed by Postgres (the bytes never leave it)."""
        for source in registry.DATABASE_SOURCES:
            rows = (await self.db.execute(text(
                f"select id::text, md5({source.data_col}) from {source.table} t where {source.where}"
            ))).all()
            for rid, digest in rows:
                item = inv.by_id.get(f"d:{source.key}:{rid}")
                if item is not None:
                    item.fingerprint = f"md5:{digest}:{item.size_bytes}"

    async def duplicates(self, inv: Inventory) -> list[DuplicateGroup]:
        await self.fingerprint_database_files(inv)
        groups: dict[str, list[FileItem]] = {}
        for item in inv.items:
            if item.fingerprint and item.size_bytes > 0:
                groups.setdefault(item.fingerprint, []).append(item)
        result = [
            DuplicateGroup(fingerprint=fp, size_bytes=members[0].size_bytes, count=len(members),
                           wasted_bytes=members[0].size_bytes * (len(members) - 1), files=members)
            for fp, members in groups.items() if len(members) > 1
        ]
        return sorted(result, key=lambda g: g.wasted_bytes, reverse=True)

    # ---- usage ---------------------------------------------------------------------------------------------

    async def usage(self, inv: Inventory, viewer: Viewer) -> FilesUsage:
        by_source: dict[str, SourceUsage] = {}
        by_type: dict[str, TypeUsage] = {}
        for item in inv.items:
            s = by_source.setdefault(item.source, SourceUsage(key=item.source, label=item.source_label,
                                                              backend=item.backend, count=0, bytes=0, protected=item.protected))
            s.count += 1
            s.bytes += item.size_bytes
            t = by_type.setdefault(item.type_group, TypeUsage(type_group=item.type_group, count=0, bytes=0))
            t.count += 1
            t.bytes += item.size_bytes
        orphans = [i for i in inv.items if i.status == "orphan"]
        large = [i for i in inv.items if i.is_large]
        protected = [i for i in inv.items if i.protected]
        duplicates = await self.duplicates(inv)
        trash_rows = await self._trash_query(viewer, include_closed=False)
        return FilesUsage(
            total_count=len(inv.items), total_bytes=sum(i.size_bytes for i in inv.items),
            by_source=sorted(by_source.values(), key=lambda s: s.bytes, reverse=True),
            by_type=sorted(by_type.values(), key=lambda t: t.bytes, reverse=True),
            orphan_count=len(orphans), orphan_bytes=sum(i.size_bytes for i in orphans),
            large_count=len(large), large_bytes=sum(i.size_bytes for i in large),
            duplicate_groups=len(duplicates), duplicate_wasted_bytes=sum(g.wasted_bytes for g in duplicates),
            protected_count=len(protected), protected_bytes=sum(i.size_bytes for i in protected),
            trash_count=len(trash_rows), trash_bytes=sum(r.size_bytes for r in trash_rows),
        )

    async def server_status(self, inv: Inventory) -> dict:
        """Read-only. Database and object-storage figures come from queries; host figures (disk, Docker, off-server
        backups) come from the file the host's monitor writes, mounted read-only. Nothing here runs a command."""
        database_rows = (await self.db.execute(text(
            "select pg_database_size(current_database()), current_database()"))).one()
        tables = (await self.db.execute(text(
            "select relname, pg_total_relation_size(c.oid) from pg_class c join pg_namespace n on n.oid = c.relnamespace "
            "where n.nspname = 'public' and c.relkind = 'r' order by 2 desc limit 15"))).all()
        listing = inv.listing
        total = sum(o.size for o in listing.values())
        backups = sum(o.size for k, o in listing.items() if registry.is_protected_key(k))
        trash = sum(o.size for k, o in listing.items() if k.startswith(registry.TRASH_PREFIX))
        return {
            "database": {"name": database_rows[1], "total_bytes": int(database_rows[0]),
                         "top_tables": [{"table": name, "bytes": int(size)} for name, size in tables]},
            "object_storage": {"bucket": self.store.bucket, "object_count": len(listing), "total_bytes": total,
                               "in_app_backups_bytes": backups, "trash_bytes": trash},
            "host": read_host_status(),
        }

    # ---- previews and downloads ----------------------------------------------------------------------------

    async def locate_for_content(self, inv: Inventory, item_id: str) -> tuple[FileItem, str | None]:
        """(item, object key) for an object-storage file, (item, None) for one inside the database."""
        item = inv.by_id.get(item_id)
        if item is None:
            raise NotFoundError("Stored file", item_id)
        if item.backend == "object_storage":
            key = decode_orphan_id(item_id) if item_id.startswith("o:") else await self._record_key(item)
            return item, key
        return item, None

    async def _record_key(self, item: FileItem) -> str:
        source = registry.OBJECT_SOURCES_BY_KEY[item.source]
        rid = item.id.split(":")[-1]
        key = (await self.db.execute(
            text(f"select {source.key_col} from {source.table} where id = cast(:i as uuid)"), {"i": rid}
        )).scalar_one_or_none()
        if key is None:
            raise NotFoundError("Stored file", item.id)
        return key

    async def database_file(self, item: FileItem) -> tuple[bytes, str]:
        source = registry.DATABASE_SOURCES_BY_KEY[item.source]
        if item.size_bytes > MAX_CONTENT_BYTES:
            raise ValidationError("This file is too large to open here.")
        rid = item.id.split(":")[-1]
        row = (await self.db.execute(
            text(f"select {source.data_col}, ({source.type_expr}) from {source.table} t where id = cast(:i as uuid)"),
            {"i": rid},
        )).one_or_none()
        if row is None or row[0] is None:
            raise NotFoundError("Stored file", item.id)
        return bytes(row[0]), row[1] or "application/octet-stream"

    # ---- trash and deletion --------------------------------------------------------------------------------

    def confirm_text_for(self, count: int) -> str:
        return f"DELETE {count}"

    async def preview_deletion(self, inv: Inventory, ids: list[str], viewer: Viewer) -> list[Analysis]:
        return [await self.analyze(inv, item_id, viewer) for item_id in dict.fromkeys(ids)]

    async def delete(self, viewer: Viewer, ids: list[str], reason: str, confirm_text: str) -> list[StorageTrash]:
        if not viewer.is_superuser:
            raise AuthorizationError("Only platform superusers can delete files.")
        ids = list(dict.fromkeys(ids))
        if confirm_text.strip() != self.confirm_text_for(len(ids)):
            raise ValidationError(f"Type {self.confirm_text_for(len(ids))} to confirm.")
        inv = await self.inventory(viewer)
        analyses = [await self.analyze(inv, item_id, viewer) for item_id in ids]
        blocked = [a for a in analyses if not a.can_delete]
        if blocked:
            # The request fails, so a database row for the refusal would be rolled back with it; log it instead.
            for a in blocked:
                logger.warning("storage_delete_refused", file=a.item.name, verdict=a.verdict, user_id=str(viewer.user_id))
            detail = "; ".join(f"{a.item.name}: {' '.join(a.reasons) or a.verdict}" for a in blocked[:5])
            raise ConflictError(f"{len(blocked)} of the selected files cannot be deleted, so nothing was deleted. {detail}")

        now = datetime.now(timezone.utc)
        moved: list[tuple[StorageTrash, str]] = []
        try:
            for analysis in analyses:
                item = analysis.item
                key = decode_orphan_id(item.id)
                info = inv.listing[key]
                trash_id = uuid.uuid4()
                trash_key = f"{registry.TRASH_PREFIX}{now:%Y%m%dT%H%M%SZ}/{trash_id}/{key}"
                await self.store.copy(key, trash_key)
                try:
                    await self.store.remove(key)
                except Exception:
                    await self.store.remove(trash_key)  # the original stayed, so the copy is not needed
                    raise
                row = StorageTrash(
                    id=trash_id, organization_id=item.organization_id, source=item.source, original_key=key,
                    trash_key=trash_key, filename=item.name[:255], content_type=item.content_type,
                    size_bytes=item.size_bytes, etag=info.etag, evidence=[e.model_dump() for e in analysis.evidence],
                    reason=reason, deleted_by_user_id=viewer.user_id, deleted_at=now,
                )
                self.db.add(row)
                moved.append((row, key))
                await self._log(viewer, "trash", item.source, key, item.name, item.size_bytes, analysis.evidence,
                                reason, trash_id)
            await self.db.flush()
        except Exception:
            for row, key in reversed(moved):  # put back anything already moved, so no file is left only in .trash
                try:
                    await self.store.copy(row.trash_key, key)
                    await self.store.remove(row.trash_key)
                except Exception:  # noqa: BLE001
                    logger.exception("storage_trash_rollback_failed", key=key)
            raise
        return [row for row, _ in moved]

    async def restore(self, viewer: Viewer, trash_id: uuid.UUID) -> StorageTrash:
        if not viewer.is_superuser:
            raise AuthorizationError("Only platform superusers can restore files.")
        row = await self.db.get(StorageTrash, trash_id)
        if row is None or row.restored_at or row.purged_at:
            raise NotFoundError("Trash item", trash_id)
        if await self.store.exists(row.original_key):
            raise ConflictError("A file already exists at the original location, so this was not restored.")
        await self.store.copy(row.trash_key, row.original_key)
        await self.store.remove(row.trash_key)
        row.restored_at = datetime.now(timezone.utc)
        await self._log(viewer, "restore", row.source, row.original_key, row.filename, row.size_bytes,
                        [Evidence(**e) for e in row.evidence], None, row.id)
        await self.db.flush()
        return row

    async def purge(self, viewer: Viewer, ids: list[uuid.UUID], confirm_text: str) -> list[StorageTrash]:
        """Permanent removal, manual only, and only for items that have sat in Trash for the minimum period."""
        if not viewer.is_superuser:
            raise AuthorizationError("Only platform superusers can permanently delete files.")
        ids = list(dict.fromkeys(ids))
        if confirm_text.strip() != f"PURGE {len(ids)}":
            raise ValidationError(f"Type PURGE {len(ids)} to confirm.")
        rows = []
        for trash_id in ids:
            row = await self.db.get(StorageTrash, trash_id)
            if row is None or row.restored_at or row.purged_at:
                raise NotFoundError("Trash item", trash_id)
            allowed = row.deleted_at + timedelta(days=settings.STORAGE_TRASH_MIN_DAYS)
            if datetime.now(timezone.utc) < allowed:
                raise ConflictError(
                    f"{row.filename} cannot be permanently deleted before {allowed:%Y-%m-%d} "
                    f"({settings.STORAGE_TRASH_MIN_DAYS} days in Trash)."
                )
            rows.append(row)
        for row in rows:
            await self.store.remove(row.trash_key)
            row.purged_at = datetime.now(timezone.utc)
            await self._log(viewer, "purge", row.source, row.original_key, row.filename, row.size_bytes,
                            [Evidence(**e) for e in row.evidence], None, row.id)
        await self.db.flush()
        return rows

    async def _trash_query(self, viewer: Viewer, include_closed: bool) -> list[StorageTrash]:
        query = select(StorageTrash).order_by(StorageTrash.deleted_at.desc())
        if not include_closed:
            query = query.where(StorageTrash.restored_at.is_(None), StorageTrash.purged_at.is_(None))
        if not viewer.is_superuser:
            query = query.where(StorageTrash.organization_id == viewer.organization_id)
        return list((await self.db.execute(query)).scalars().all())

    async def list_trash(self, viewer: Viewer, include_closed: bool = False) -> list[TrashItem]:
        rows = await self._trash_query(viewer, include_closed)
        emails = await self._emails({r.deleted_by_user_id for r in rows if r.deleted_by_user_id})
        now = datetime.now(timezone.utc)
        items = []
        for r in rows:
            allowed = r.deleted_at + timedelta(days=settings.STORAGE_TRASH_MIN_DAYS)
            items.append(TrashItem(
                id=r.id, organization_id=r.organization_id, source=r.source, original_key=r.original_key,
                filename=r.filename, content_type=r.content_type, size_bytes=r.size_bytes, reason=r.reason,
                deleted_by=emails.get(r.deleted_by_user_id), deleted_at=r.deleted_at, purge_allowed_at=allowed,
                can_purge=viewer.is_superuser and now >= allowed and not r.restored_at and not r.purged_at,
                restored_at=r.restored_at, purged_at=r.purged_at, evidence=[Evidence(**e) for e in r.evidence],
            ))
        return items

    async def deletion_log(self, viewer: Viewer, skip: int, limit: int) -> tuple[list[DeletionLogItem], int]:
        base = select(StorageDeletionLog)
        if not viewer.is_superuser:
            base = base.where(StorageDeletionLog.organization_id == viewer.organization_id)
        total = len((await self.db.execute(base.with_only_columns(StorageDeletionLog.id))).all())
        rows = list((await self.db.execute(
            base.order_by(StorageDeletionLog.created_at.desc()).offset(skip).limit(limit))).scalars().all())
        emails = await self._emails({r.user_id for r in rows if r.user_id})
        return [
            DeletionLogItem(id=r.id, created_at=r.created_at, action=r.action, source=r.source, object_key=r.object_key,
                            filename=r.filename, size_bytes=r.size_bytes, user_email=emails.get(r.user_id),
                            reason=r.reason, ip_address=r.ip_address, trash_id=r.trash_id,
                            evidence=[Evidence(**e) for e in r.evidence])
            for r in rows
        ], total

    async def _emails(self, user_ids: set) -> dict:
        if not user_ids:
            return {}
        rows = (await self.db.execute(text("select id, email from users where id = any(:ids)"),
                                      {"ids": list(user_ids)})).all()
        return {row[0]: row[1] for row in rows}

    async def _log(self, viewer: Viewer, action: str, source: str, key: str, filename: str | None, size: int | None,
                   evidence: list[Evidence], reason: str | None, trash_id: uuid.UUID | None) -> None:
        ctx = get_audit_context()
        self.db.add(StorageDeletionLog(
            organization_id=viewer.organization_id, user_id=viewer.user_id, action=action, source=source,
            object_key=key[:800], filename=(filename or "")[:255] or None, size_bytes=size, trash_id=trash_id,
            evidence=[e.model_dump() for e in evidence], reason=reason, ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
        ))


# Fixed, so a file is previewed the same way on every operating system (Windows maps .csv to Excel, for one).
_TYPES = {
    "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
    "webp": "image/webp", "svg": "image/svg+xml", "mp4": "video/mp4", "webm": "video/webm", "txt": "text/plain",
    "csv": "text/csv", "json": "application/json", "html": "text/html", "htm": "text/html", "sql": "application/sql",
    "dump": "application/octet-stream", "zip": "application/zip",
}


def _guess_type(key: str) -> str | None:
    import mimetypes

    extension = key.rsplit(".", 1)[-1].lower() if "." in key.rsplit("/", 1)[-1] else ""
    return _TYPES.get(extension) or mimetypes.guess_type(key)[0]


def read_host_status() -> dict:
    """The host's monitor writes this file; it is mounted into the API container read-only."""
    path = settings.STORAGE_HOST_STATUS_PATH
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {"available": False, "reason": "The host status file is not mounted into this container."}
    except (OSError, ValueError) as exc:
        return {"available": False, "reason": f"The host status file could not be read: {exc}"}
    return {"available": True, **data}
