import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions, require_superuser
from modules.storage_manager import registry
from modules.storage_manager.schemas import (
    Analysis,
    DeletionLogResponse,
    DeletionPreviewRequest,
    DeletionPreviewResponse,
    DeletionRequest,
    DeletionResult,
    DuplicateGroup,
    FileListResponse,
    PreviewResponse,
    PurgeRequest,
    ServerResponse,
    TrashItem,
    TrashListResponse,
    UsageResponse,
)
from modules.storage_manager.service import StorageManagerService, Viewer
from modules.users.repository import UserProfileRepository

router = APIRouter()

# Everyone with `storage.view` (the Administrator role) can look at their own organization's files and storage use.
# Platform superusers additionally see every organization, the whole-server inspector, and are the only ones who can
# delete, restore or permanently remove anything. Business records are never changed by any of these routes.


async def get_viewer(user: User, db: AsyncSession) -> Viewer:
    profile = await UserProfileRepository(db).get_by_user_id(user.id)
    return Viewer(user_id=user.id, organization_id=profile.organization_id if profile else None,
                  is_superuser=bool(user.is_superuser))


def _split_path(path: str | None) -> list[str]:
    return [p for p in (path or "").split("/") if p]


@router.get("/files", response_model=FileListResponse)
async def list_files(
    path: str = Query(default="", description="Folder to open, segments separated by /"),
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    type_group: str | None = None,
    min_size: int | None = Query(default=None, ge=0),
    max_size: int | None = Query(default=None, ge=0),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    owner: str | None = None,
    large: bool | None = None,
    sort: str = Query(default="name", pattern="^(name|size|date|source|status|owner|type)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permissions("storage.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    inv = await service.inventory(viewer)
    segments = _split_path(path)
    items, folders, total, total_bytes, flat, subtree_count, subtree_bytes = service.browse(
        inv, path=segments, q=q, source=source, status=status, type_group=type_group, min_size=min_size,
        max_size=max_size, date_from=date_from, date_to=date_to, owner=owner, large=large, sort=sort, order=order,
        page=page, page_size=page_size,
    )
    return FileListResponse(items=items, folders=folders, path=segments, total=total, page=page, page_size=page_size,
                            total_bytes=total_bytes, flat=flat, subtree_count=subtree_count, subtree_bytes=subtree_bytes)


@router.get("/usage", response_model=UsageResponse)
async def usage(user: User = Depends(require_permissions("storage.view")), db: AsyncSession = Depends(get_db)):
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    inv = await service.inventory(viewer)
    return UsageResponse(generated_at=datetime.now(timezone.utc),
                         scope="platform" if viewer.is_superuser else "organization",
                         files=await service.usage(inv, viewer), can_delete=viewer.is_superuser)


@router.get("/duplicates", response_model=list[DuplicateGroup])
async def duplicates(user: User = Depends(require_permissions("storage.view")), db: AsyncSession = Depends(get_db)):
    service = StorageManagerService(db)
    inv = await service.inventory(await get_viewer(user, db))
    return await service.duplicates(inv)


@router.get("/server", response_model=ServerResponse)
async def server(user: User = Depends(require_superuser()), db: AsyncSession = Depends(get_db)):
    service = StorageManagerService(db)
    inv = await service.inventory(await get_viewer(user, db))
    return ServerResponse(generated_at=datetime.now(timezone.utc), **await service.server_status(inv))


@router.get("/analysis", response_model=Analysis)
async def analyze_file(
    id: str = Query(..., description="A file id from /files"),
    user: User = Depends(require_permissions("storage.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    return await service.analyze(await service.inventory(viewer), id, viewer)


@router.get("/preview", response_model=PreviewResponse)
async def preview(
    id: str = Query(...),
    download: bool = False,
    user: User = Depends(require_permissions("storage.view")),
    db: AsyncSession = Depends(get_db),
):
    """A short-lived link for a file in object storage, or the path of the authenticated content endpoint for a file
    kept inside the database. Only images, PDFs, video and plain text open inline; everything else is a download."""
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    inv = await service.inventory(viewer)
    item, key = await service.locate_for_content(inv, id)
    kind = registry.preview_kind(item.content_type)
    inline = bool(kind) and not download
    if key is not None:
        if item.status == "missing_object":
            return PreviewResponse(kind=kind, mode="none", url=None, content_type=item.content_type, expires_in=None,
                                   message="The file is no longer in storage.")
        url = service.store.presign(key, item.name, item.content_type, inline=inline)
        return PreviewResponse(kind=kind if inline else None, mode="url", url=url, content_type=item.content_type,
                               expires_in=300)
    return PreviewResponse(kind=kind if inline else None, mode="content", content_type=item.content_type,
                           url=f"/api/v1/storage-manager/content?id={id}&download={'true' if download or not kind else 'false'}",
                           expires_in=None)


@router.get("/content")
async def content(
    id: str = Query(...),
    download: bool = False,
    user: User = Depends(require_permissions("storage.view")),
    db: AsyncSession = Depends(get_db),
):
    """The bytes of a file kept inside the database, after the same organization check as every other route."""
    service = StorageManagerService(db)
    inv = await service.inventory(await get_viewer(user, db))
    item, key = await service.locate_for_content(inv, id)
    if key is not None:
        raise ValidationError("This file is in object storage: use /preview.")
    data, content_type = await service.database_file(item)
    kind = registry.preview_kind(content_type)
    disposition = "attachment" if (download or not kind) else "inline"
    from urllib.parse import quote

    return Response(
        content=data, media_type=content_type if kind or download else "application/octet-stream",
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(item.name)}",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/deletions/preview", response_model=DeletionPreviewResponse)
async def preview_deletion(
    payload: DeletionPreviewRequest,
    user: User = Depends(require_permissions("storage.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    inv = await service.inventory(viewer)
    analyses = await service.preview_deletion(inv, payload.ids, viewer)
    eligible = [a for a in analyses if a.can_delete]
    return DeletionPreviewResponse(
        items=analyses, eligible_count=len(eligible), blocked_count=len(analyses) - len(eligible),
        total_bytes=sum(a.item.size_bytes for a in eligible), confirm_text=service.confirm_text_for(len(analyses)),
    )


@router.post("/deletions", response_model=DeletionResult)
async def delete_files(payload: DeletionRequest, user: User = Depends(require_superuser()),
                       db: AsyncSession = Depends(get_db)):
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    rows = await service.delete(viewer, payload.ids, payload.reason, payload.confirm_text)
    items = [i for i in await service.list_trash(viewer) if i.id in {r.id for r in rows}]
    return DeletionResult(moved=items, total_bytes=sum(i.size_bytes for i in items))


@router.get("/trash", response_model=TrashListResponse)
async def trash(include_closed: bool = False, user: User = Depends(require_permissions("storage.view")),
                db: AsyncSession = Depends(get_db)):
    from app.core.config import settings

    service = StorageManagerService(db)
    items = await service.list_trash(await get_viewer(user, db), include_closed)
    open_items = [i for i in items if not i.restored_at and not i.purged_at]
    return TrashListResponse(items=items, total=len(items), total_bytes=sum(i.size_bytes for i in open_items),
                             min_days=settings.STORAGE_TRASH_MIN_DAYS)


@router.post("/trash/{trash_id}/restore", response_model=TrashItem)
async def restore(trash_id: uuid.UUID, user: User = Depends(require_superuser()), db: AsyncSession = Depends(get_db)):
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    row = await service.restore(viewer, trash_id)
    return next(i for i in await service.list_trash(viewer, include_closed=True) if i.id == row.id)


@router.post("/trash/purge", response_model=list[TrashItem])
async def purge(payload: PurgeRequest, user: User = Depends(require_superuser()), db: AsyncSession = Depends(get_db)):
    """Manual, confirmed, and only for items that have been in Trash for the minimum period. Nothing runs this
    automatically."""
    service = StorageManagerService(db)
    viewer = await get_viewer(user, db)
    rows = await service.purge(viewer, payload.ids, payload.confirm_text)
    ids = {r.id for r in rows}
    return [i for i in await service.list_trash(viewer, include_closed=True) if i.id in ids]


@router.get("/deletion-log", response_model=DeletionLogResponse)
async def deletion_log(skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
                       user: User = Depends(require_permissions("storage.view")), db: AsyncSession = Depends(get_db)):
    service = StorageManagerService(db)
    items, total = await service.deletion_log(await get_viewer(user, db), skip, limit)
    return DeletionLogResponse(items=items, total=total)
