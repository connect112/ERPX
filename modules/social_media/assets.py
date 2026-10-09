"""
Image assets: the approved logo, photos, lab screenshots and AI-made backgrounds.

Every upload is treated as untrusted: size-capped, decoded and re-encoded by us (so only pixels are kept: no embedded
scripts, metadata or odd container tricks), checked for dimensions and decompression bombs, and stored under a key we
choose. SVG is not accepted. The logo is re-encoded losslessly as PNG so it stays exactly as approved.
"""

import hashlib
import io
import re
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.social_media.models import SocialAsset, SocialPost, SocialSettings
from packages.storage.client import get_storage_client

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_SIDE = 6000
MIN_SIDE = 64
KINDS = ("logo", "photo", "screenshot", "background")
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
# A decoded image bigger than this is refused before it is loaded (decompression bomb guard).
Image.MAX_IMAGE_PIXELS = 36_000_000


def safe_filename(name: str) -> str:
    base = re.split(r"[\\/]", name or "image")[-1]
    base = re.sub(r"[^\w.\- ]", "", base).strip(" .") or "image"
    return base[:200]


def check_and_encode(raw: bytes, kind: str) -> tuple[bytes, str, str, int, int]:
    """(clean bytes, content type, extension, width, height) for an upload, or a ValidationError saying what's wrong."""
    if kind not in KINDS:
        raise ValidationError("Choose what the image is: logo, photo, screenshot or background.")
    if not raw:
        raise ValidationError("The file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"The image is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        probe.verify()
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError):
        raise ValidationError("That file isn't a usable image. Upload a PNG, JPEG or WebP (SVG isn't supported).") from None
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError("Upload a PNG, JPEG or WebP image (SVG and other formats aren't supported).")
    image = ImageOps.exif_transpose(image)
    width, height = image.size
    if min(width, height) < MIN_SIDE:
        raise ValidationError(f"The image is too small (at least {MIN_SIDE} pixels each way).")
    if max(width, height) > MAX_SIDE:
        raise ValidationError(f"The image is too large (at most {MAX_SIDE} pixels on a side).")
    out = io.BytesIO()
    if kind in ("logo", "screenshot") or "A" in image.mode:
        image.convert("RGBA" if kind == "logo" or "A" in image.mode else "RGB").save(out, format="PNG", optimize=True)
        return out.getvalue(), "image/png", "png", width, height
    image.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue(), "image/jpeg", "jpg", width, height


class AssetService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_client()

    async def create(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        *,
        kind: str,
        filename: str,
        raw: bytes,
        alt_text: str = "",
        synthetic: bool = False,
        provenance: dict | None = None,
    ) -> SocialAsset:
        data, content_type, ext, width, height = check_and_encode(raw, kind)
        key = f"social/{organization_id}/assets/{uuid.uuid4().hex}.{ext}"
        await self.storage.upload_bytes(key, data, content_type)
        asset = SocialAsset(
            organization_id=organization_id,
            uploaded_by_user_id=user_id,
            kind=kind,
            storage_key=key,
            filename=safe_filename(filename),
            content_type=content_type,
            width=width,
            height=height,
            bytes_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            alt_text=(alt_text or "").strip()[:420],
            synthetic=synthetic,
            provenance=provenance or {},
        )
        self.db.add(asset)
        await self.db.flush()
        return asset

    async def get(self, organization_id: uuid.UUID, asset_id: uuid.UUID | str | None) -> SocialAsset:
        try:
            ident = uuid.UUID(str(asset_id))
        except (ValueError, TypeError):
            raise NotFoundError("That image no longer exists.") from None
        asset = (
            await self.db.execute(select(SocialAsset).where(SocialAsset.id == ident, SocialAsset.organization_id == organization_id))
        ).scalar_one_or_none()
        if asset is None:
            raise NotFoundError("That image no longer exists.")
        return asset

    async def list(self, organization_id: uuid.UUID, kind: str | None = None) -> list[SocialAsset]:
        conditions = [SocialAsset.organization_id == organization_id]
        if kind:
            conditions.append(SocialAsset.kind == kind)
        rows = await self.db.execute(select(SocialAsset).where(*conditions).order_by(SocialAsset.created_at.desc()).limit(200))
        return list(rows.scalars())

    def url(self, asset: SocialAsset) -> str | None:
        try:
            return self.storage.presigned_download_url(asset.storage_key)
        except Exception:  # noqa: BLE001 - storage trouble must not break a listing
            return None

    async def read(self, asset: SocialAsset) -> bytes:
        return await self.storage.read_bytes(asset.storage_key)

    async def delete(self, organization_id: uuid.UUID, asset: SocialAsset, settings: SocialSettings) -> None:
        if (settings.brand or {}).get("logo_key") == asset.storage_key:
            raise ConflictError("This is the approved logo. Choose another logo first.")
        in_use = (
            await self.db.execute(
                select(SocialPost.id)
                .where(SocialPost.organization_id == organization_id, SocialPost.design["background_asset_id"].astext == str(asset.id))
                .limit(1)
            )
        ).first()
        if in_use:
            raise ConflictError("A post's artwork uses this image. Change that post first.")
        await self.storage.delete_object(asset.storage_key)
        await self.db.delete(asset)
        await self.db.flush()

    async def use_as_logo(self, settings: SocialSettings, asset: SocialAsset) -> None:
        if asset.kind != "logo":
            raise ValidationError("Only an image uploaded as a logo can be the approved logo.")
        brand = dict(settings.brand)
        brand["logo_key"] = asset.storage_key
        settings.brand = brand
        await self.db.flush()
