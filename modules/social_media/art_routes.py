"""Image library, artwork (design, render, remove, AI background, proofread) and the nine-post grid."""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.social_media.artwork import ArtworkService
from modules.social_media.assets import KINDS, MAX_UPLOAD_BYTES, AssetService
from modules.social_media.grid import GridService
from modules.social_media.schemas import AssetPublic, BackgroundRequest, Design, GridOut, PostPublic, ProofreadResult
from modules.social_media.service import PostService, SettingsService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

VIEW = "social_media.view"
MANAGE = "social_media.manage"


def _asset_out(service: AssetService, asset, logo_key: str | None) -> AssetPublic:
    out = AssetPublic.model_validate(asset)
    out.url = service.url(asset)
    out.is_logo = bool(logo_key and asset.storage_key == logo_key)
    return out


# ---------------- the image library ----------------


@router.get("/assets", response_model=list[AssetPublic])
async def list_assets(
    kind: str | None = Query(default=None, pattern=r"^(logo|photo|screenshot|background)$"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    settings = await SettingsService(db).get(organization_id)
    service = AssetService(db)
    logo_key = (settings.brand or {}).get("logo_key")
    result = [_asset_out(service, a, logo_key) for a in await service.list(organization_id, kind)]
    await db.commit()
    return result


@router.post("/assets", response_model=AssetPublic, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    kind: str = Form(...),
    alt_text: str = Form(default="", max_length=420),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Upload a logo, photo or screenshot. It is checked, re-encoded and stored under a name we choose."""
    from app.core.exceptions import ValidationError

    if kind not in KINDS or kind == "background":
        raise ValidationError("Choose what you are uploading: a logo, a photo or a screenshot.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    service = AssetService(db)
    asset = await service.create(organization_id, user.id, kind=kind, filename=file.filename or "image", raw=raw, alt_text=alt_text)
    settings = await SettingsService(db).get(organization_id)
    result = _asset_out(service, asset, (settings.brand or {}).get("logo_key"))
    await db.commit()
    return result


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.get(organization_id, asset_id)
    await service.delete(organization_id, asset, await SettingsService(db).get(organization_id))
    await db.commit()


@router.post("/assets/{asset_id}/use-as-logo", response_model=AssetPublic)
async def use_as_logo(
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Make an uploaded logo the approved logo that artwork uses. It is only ever scaled, never redrawn."""
    service = AssetService(db)
    asset = await service.get(organization_id, asset_id)
    settings = await SettingsService(db).get(organization_id)
    await service.use_as_logo(settings, asset)
    result = _asset_out(service, asset, asset.storage_key)
    await db.commit()
    return result


# ---------------- artwork ----------------


@router.put("/posts/{post_id}/design", response_model=PostPublic)
async def set_design(
    post_id: uuid.UUID,
    payload: Design,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Choose the template, picture and wording of the artwork (it is drawn by the next render)."""
    post = await PostService(db).get(post_id, organization_id)
    withdrawn = await ArtworkService(db).set_design(organization_id, post, payload)
    await db.refresh(post)
    result = PostService.public(post, approval_withdrawn=withdrawn)
    await db.commit()
    return result


@router.post("/posts/{post_id}/render", response_model=PostPublic)
async def render_artwork(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Draw the artwork from the post's words and design, check it, and store it."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    withdrawn = await ArtworkService(db).render(organization_id, post, settings)
    await db.refresh(post)
    result = PostService.public(post, approval_withdrawn=withdrawn)
    await db.commit()
    return result


@router.delete("/posts/{post_id}/artwork", response_model=PostPublic)
async def remove_artwork(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Reject the artwork: the rendered pictures are deleted; the design stays so it can be changed and drawn again."""
    post = await PostService(db).get(post_id, organization_id)
    withdrawn = await ArtworkService(db).remove(post)
    await db.refresh(post)
    result = PostService.public(post, approval_withdrawn=withdrawn)
    await db.commit()
    return result


@router.post("/posts/{post_id}/background", response_model=PostPublic)
async def new_background(
    post_id: uuid.UUID,
    payload: BackgroundRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Replace only the picture with a new AI-made background (Photo template), then draw again."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    withdrawn = await ArtworkService(db).new_background(organization_id, user.id, post, settings, payload.direction)
    await db.refresh(post)
    result = PostService.public(post, approval_withdrawn=withdrawn)
    await db.commit()
    return result


@router.post("/posts/{post_id}/proofread", response_model=ProofreadResult)
async def proofread_artwork(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Have the AI check the spelling and grammar of the words that are drawn on the artwork."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    result = await ArtworkService(db).proofread(organization_id, user.id, post, settings)
    await db.commit()
    return ProofreadResult(**result)


# ---------------- the grid ----------------


@router.get("/grid", response_model=GridOut)
async def grid_preview(
    post_id: uuid.UUID | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """The nine-post preview (this post first, if given) with what is repetitive, dense, inconsistent or abrupt."""
    settings = await SettingsService(db).get(organization_id)
    result = await GridService(db).build(organization_id, settings, post_id)
    await db.commit()
    return GridOut(**result)
