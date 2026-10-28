"""
Brand profiles, signatures, reusable components and uploaded images for Email Studio.

Images are served from a public link (email clients cannot sign in), so only real images of a few types are accepted, they are
size-limited, and they are served with headers that stop a browser from treating them as anything else. A signature image only
appears in emails after an administrator has approved it; nothing here draws or alters a signature.
"""

import io
import secrets
import uuid
from datetime import datetime, timezone

from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.email_studio.engine import asset_url
from modules.email_studio.models import (
    EmailAsset,
    EmailBrandProfile,
    EmailComponent,
    EmailSignature,
    EmailStudioTemplate,
    EmailStudioVersion,
)
from modules.email_studio.sanitize import sanitize_fragment
from modules.email_studio.schemas import AssetOut, BrandOut, BrandPayload, ComponentOut, ComponentPayload, SignatureOut, SignaturePayload

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
_IMAGE_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp"}
_ATTACHMENT_TYPES = {"application/pdf"}


def detect(data: bytes, purpose: str) -> str:
    """The content type of an upload by what it contains, or a ValidationError."""
    if not data:
        raise ValidationError("The file is empty.")
    if purpose == "image":
        if len(data) > MAX_IMAGE_BYTES:
            raise ValidationError("Images can be at most 2 MB.")
        try:
            with PILImage.open(io.BytesIO(data)) as img:
                fmt = (img.format or "").upper()
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise ValidationError("That file is not an image. Upload a PNG, JPG, GIF or WebP.") from exc
        if fmt not in _IMAGE_FORMATS:
            raise ValidationError("Email clients cannot show that image type. Upload a PNG, JPG, GIF or WebP.")
        return _IMAGE_FORMATS[fmt]
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValidationError("Attachments can be at most 5 MB.")
    if data.lstrip().startswith(b"%PDF"):
        return "application/pdf"
    raise ValidationError("Only PDF files can be attached.")


class BrandingService:
    def __init__(self, db: AsyncSession, organization_id: uuid.UUID):
        self.db = db
        self.organization_id = organization_id

    # ------------------------------------------------------------------ assets

    async def upload(self, filename: str, data: bytes, purpose: str, user_id: uuid.UUID) -> AssetOut:
        content_type = detect(data, purpose)
        row = EmailAsset(
            organization_id=self.organization_id, token=secrets.token_urlsafe(24), filename=" ".join(filename.split())[:255] or "file",
            content_type=content_type, size_bytes=len(data), data=data, uploaded_by_user_id=user_id,
        )
        self.db.add(row)
        await self.db.flush()
        return self._asset_out(row)

    @staticmethod
    def _asset_out(row: EmailAsset) -> AssetOut:
        return AssetOut(
            id=row.id, token=row.token, filename=row.filename, content_type=row.content_type, size_bytes=row.size_bytes,
            url=asset_url(row.token) if row.content_type.startswith("image/") else None,
        )

    async def asset(self, asset_id: uuid.UUID | None) -> EmailAsset | None:
        if asset_id is None:
            return None
        row = await self.db.get(EmailAsset, asset_id)
        if row is None or row.organization_id != self.organization_id:
            raise ValidationError("That image does not exist.")
        if not row.content_type.startswith("image/"):
            raise ValidationError("That file is not an image.")
        return row

    async def assets(self) -> list[AssetOut]:
        rows = (await self.db.execute(select(EmailAsset).where(EmailAsset.organization_id == self.organization_id).order_by(EmailAsset.created_at.desc()).limit(200))).scalars().all()
        return [self._asset_out(r) for r in rows]

    # ------------------------------------------------------------------ brand profiles

    async def _tokens(self, *ids: uuid.UUID | None) -> dict[uuid.UUID, str]:
        wanted = [i for i in ids if i]
        if not wanted:
            return {}
        return dict((await self.db.execute(select(EmailAsset.id, EmailAsset.token).where(EmailAsset.id.in_(wanted)))).all())

    async def _brand_out(self, b: EmailBrandProfile) -> BrandOut:
        tokens = await self._tokens(b.logo_asset_id)
        return BrandOut(
            id=b.id, name=b.name, company_name=b.company_name, logo_asset_id=b.logo_asset_id, primary_color=b.primary_color, secondary_color=b.secondary_color,
            accent_color=b.accent_color, background_color=b.background_color, text_color=b.text_color, website=b.website, contact_email=b.contact_email,
            phone=b.phone, address=b.address, tagline=b.tagline, social_links=list(b.social_links or []), from_name=b.from_name, reply_to=b.reply_to,
            is_default=b.is_default, logo_url=asset_url(tokens[b.logo_asset_id]) if b.logo_asset_id in tokens else None, updated_at=b.updated_at,
        )

    async def brands(self) -> list[BrandOut]:
        rows = (await self.db.execute(select(EmailBrandProfile).where(EmailBrandProfile.organization_id == self.organization_id).order_by(EmailBrandProfile.name))).scalars().all()
        return [await self._brand_out(b) for b in rows]

    async def brand(self, brand_id: uuid.UUID) -> EmailBrandProfile:
        row = await self.db.get(EmailBrandProfile, brand_id)
        if row is None or row.organization_id != self.organization_id:
            raise NotFoundError("Brand profile", brand_id)
        return row

    async def save_brand(self, payload: BrandPayload, user_id: uuid.UUID, brand_id: uuid.UUID | None = None) -> BrandOut:
        await self.asset(payload.logo_asset_id)
        row = await self.brand(brand_id) if brand_id else EmailBrandProfile(organization_id=self.organization_id)
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        row.updated_by_user_id = user_id
        if brand_id is None:
            first = (await self.db.execute(select(func.count()).select_from(EmailBrandProfile).where(EmailBrandProfile.organization_id == self.organization_id))).scalar_one() == 0
            row.is_default = row.is_default or first  # the first brand is the default
            self.db.add(row)
        await self.db.flush()
        if row.is_default:
            await self.db.execute(
                update(EmailBrandProfile).where(EmailBrandProfile.organization_id == self.organization_id, EmailBrandProfile.id != row.id).values(is_default=False)
            )
        await self.db.flush()
        await self.db.refresh(row)
        return await self._brand_out(row)

    async def delete_brand(self, brand_id: uuid.UUID) -> None:
        row = await self.brand(brand_id)
        used = (await self.db.execute(select(func.count()).select_from(EmailStudioVersion).where(EmailStudioVersion.brand_profile_id == brand_id, EmailStudioVersion.state != "superseded"))).scalar_one()
        if used:
            raise ConflictError("Templates are using this brand. Choose another brand for them first.")
        await self.db.delete(row)
        await self.db.flush()

    # ------------------------------------------------------------------ signatures

    async def _sig_out(self, s: EmailSignature) -> SignatureOut:
        tokens = await self._tokens(s.logo_asset_id, s.signature_asset_id)
        return SignatureOut(
            id=s.id, name=s.name, scope=s.scope, person_name=s.person_name, designation=s.designation, company_name=s.company_name, email=s.email, phone=s.phone,
            website=s.website, logo_asset_id=s.logo_asset_id, signature_asset_id=s.signature_asset_id, style=s.style or {}, is_default=s.is_default,
            signature_image_url=asset_url(tokens[s.signature_asset_id]) if s.signature_asset_id in tokens else None,
            logo_url=asset_url(tokens[s.logo_asset_id]) if s.logo_asset_id in tokens else None,
            signature_approved=bool(s.signature_asset_id and s.signature_approved_at), updated_at=s.updated_at,
        )

    async def signatures(self) -> list[SignatureOut]:
        rows = (await self.db.execute(select(EmailSignature).where(EmailSignature.organization_id == self.organization_id).order_by(EmailSignature.name))).scalars().all()
        return [await self._sig_out(s) for s in rows]

    async def signature(self, signature_id: uuid.UUID) -> EmailSignature:
        row = await self.db.get(EmailSignature, signature_id)
        if row is None or row.organization_id != self.organization_id:
            raise NotFoundError("Signature", signature_id)
        return row

    async def save_signature(self, payload: SignaturePayload, user_id: uuid.UUID, signature_id: uuid.UUID | None = None) -> SignatureOut:
        await self.asset(payload.logo_asset_id)
        await self.asset(payload.signature_asset_id)
        row = await self.signature(signature_id) if signature_id else EmailSignature(organization_id=self.organization_id)
        previous_image = row.signature_asset_id
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        if row.signature_asset_id != previous_image:
            row.signature_approved_at = None  # a different image has to be approved again
            row.signature_approved_by_user_id = None
        row.updated_by_user_id = user_id
        if signature_id is None:
            self.db.add(row)
        await self.db.flush()
        if row.is_default:
            await self.db.execute(update(EmailSignature).where(EmailSignature.organization_id == self.organization_id, EmailSignature.id != row.id).values(is_default=False))
        await self.db.flush()
        await self.db.refresh(row)
        return await self._sig_out(row)

    async def approve_signature(self, signature_id: uuid.UUID, approve: bool, user_id: uuid.UUID) -> SignatureOut:
        row = await self.signature(signature_id)
        if approve and row.signature_asset_id is None:
            raise ValidationError("Upload the signature image first.")
        row.signature_approved_at = datetime.now(timezone.utc) if approve else None
        row.signature_approved_by_user_id = user_id if approve else None
        await self.db.flush()
        await self.db.refresh(row)
        return await self._sig_out(row)

    async def delete_signature(self, signature_id: uuid.UUID) -> None:
        row = await self.signature(signature_id)
        used = (await self.db.execute(select(func.count()).select_from(EmailStudioVersion).where(EmailStudioVersion.signature_id == signature_id, EmailStudioVersion.state != "superseded"))).scalar_one()
        if used:
            raise ConflictError("Templates are using this signature. Choose another signature for them first.")
        await self.db.delete(row)
        await self.db.flush()

    # ------------------------------------------------------------------ components

    @staticmethod
    def _component_out(c: EmailComponent) -> ComponentOut:
        return ComponentOut(id=c.id, name=c.name, kind=c.kind, description=c.description, html=c.html, updated_at=c.updated_at)  # type: ignore[arg-type]

    async def components(self) -> list[ComponentOut]:
        rows = (await self.db.execute(select(EmailComponent).where(EmailComponent.organization_id == self.organization_id).order_by(EmailComponent.kind, EmailComponent.name))).scalars().all()
        return [self._component_out(c) for c in rows]

    async def _component(self, component_id: uuid.UUID) -> EmailComponent:
        row = await self.db.get(EmailComponent, component_id)
        if row is None or row.organization_id != self.organization_id:
            raise NotFoundError("Component", component_id)
        return row

    async def save_component(self, payload: ComponentPayload, user_id: uuid.UUID, component_id: uuid.UUID | None = None) -> ComponentOut:
        row = await self._component(component_id) if component_id else EmailComponent(organization_id=self.organization_id)
        row.name, row.kind, row.description = payload.name.strip(), payload.kind, payload.description.strip()
        row.html = sanitize_fragment(payload.html)  # a component is email HTML too, so it is cleaned the same way
        if not row.html.strip():
            raise ValidationError("The component has no content once unsafe parts are removed.")
        row.updated_by_user_id = user_id
        if component_id is None:
            self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return self._component_out(row)

    async def delete_component(self, component_id: uuid.UUID) -> None:
        await self.db.delete(await self._component(component_id))
        await self.db.flush()


async def templates_using_brand(db: AsyncSession, brand_id: uuid.UUID) -> list[str]:
    rows = (
        await db.execute(
            select(EmailStudioTemplate.name).join(EmailStudioVersion, EmailStudioVersion.template_id == EmailStudioTemplate.id).where(EmailStudioVersion.brand_profile_id == brand_id, EmailStudioTemplate.deleted_at.is_(None)).distinct()
        )
    ).scalars().all()
    return list(rows)
