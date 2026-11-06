"""
Receipt designs and their images: saving, resolving which design applies, templates, and read-only previews.

* Which design a new document gets: the internship's own, else the organization's default, else the built-in one. The choice and the
  design itself are copied into the document's ``details`` when it is issued (see ``financial.issue``), so a later change only ever
  affects documents issued after it.
* Saving a design never touches a document, a payment or the ledger. Images are immutable (a replacement is a new row).
* Preview builds the PDF in memory from the draft design: it takes no document number, writes nothing, sends nothing.
"""

import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import undefer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.authentication.models import User
from modules.internship_onboarding.models import ReceiptAsset, ReceiptDesignRecord, ReceiptDesignVersion
from modules.internship_onboarding.receipt_design import ASSET_KINDS, ReceiptDesign, default_design, dump, first_error, parse_design
from modules.internship_onboarding.receipt_pdf import Image_
from modules.internship_onboarding.service import FINANCE_MANAGE, FINANCE_VIEW, has, require
from modules.our_internships.models import OurInternship

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 25_000_000  # refuses a decompression bomb before it is decoded
MAX_EDGE_PX = {"logo": 900, "signature": 700, "stamp": 600}
MAX_TEMPLATES = 50
SOURCES = ("internship", "organization", "default")


class AssetError(ValidationError):
    """An uploaded image that cannot be used; the message is shown to the administrator."""


@dataclass
class Resolved:
    design: ReceiptDesign
    source: str  # internship | organization | default
    design_id: uuid.UUID | None
    version: int


def now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ images


def normalize_image(data: bytes, kind: str) -> tuple[bytes, int, int]:
    """(PNG bytes, width, height). Only real PNG or JPEG pictures are accepted (SVG and anything else is refused); the picture is
    decoded, shrunk to a sensible size and saved again as a PNG, which drops any metadata (location, camera, embedded scripts)."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if kind not in ASSET_KINDS:
        raise AssetError("Choose logo, signature or stamp.")
    if not data:
        raise AssetError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise AssetError("The image is larger than 2 MB.")
    if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")):
        raise AssetError("Upload a PNG or JPG image.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ("PNG", "JPEG"):
                raise AssetError("Upload a PNG or JPG image.")
            if probe.width * probe.height > MAX_PIXELS:
                raise AssetError("That image is too large. Upload one under 25 megapixels.")
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img.load()
            limit = MAX_EDGE_PX[kind]
            img.thumbnail((limit, limit))
            out = io.BytesIO()
            img.convert("RGBA").save(out, "PNG", optimize=True)
            width, height = img.size
    except AssetError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise AssetError("That file is not a usable PNG or JPG image.") from exc
    if width < 16 or height < 16:
        raise AssetError("That image is too small to use.")
    return out.getvalue(), width, height


def to_image(asset: ReceiptAsset) -> Image_:
    return Image_(data=asset.data, content_type=asset.content_type)


class ReceiptDesignService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------------- reading

    async def _record(self, organization_id: uuid.UUID, scope: str, internship_id: uuid.UUID | None = None) -> ReceiptDesignRecord | None:
        query = select(ReceiptDesignRecord).where(ReceiptDesignRecord.organization_id == organization_id, ReceiptDesignRecord.scope == scope)
        if scope == "internship":
            query = query.where(ReceiptDesignRecord.internship_id == internship_id)
        return (await self.db.execute(query)).scalar_one_or_none()

    @staticmethod
    def _parse(record: ReceiptDesignRecord) -> ReceiptDesign:
        try:
            return parse_design(record.design)
        except PydanticValidationError:  # a stored design that no longer validates never blocks a payment document
            return default_design()

    async def resolve(self, organization_id: uuid.UUID, internship_id: uuid.UUID) -> Resolved:
        """The design a document issued now gets."""
        own = await self._record(organization_id, "internship", internship_id)
        if own is not None:
            return Resolved(self._parse(own), "internship", own.id, own.version)
        org = await self._record(organization_id, "organization")
        if org is not None:
            return Resolved(self._parse(org), "organization", org.id, org.version)
        return Resolved(default_design(), "default", None, 0)

    async def images_for(self, organization_id: uuid.UUID, design: ReceiptDesign) -> dict[str, Image_]:
        """The pictures a design refers to (only those of this organization; a missing or archived one is simply left out)."""
        wanted = {slot: s.asset_id for slot, s in design.slots().items() if s.asset_id is not None and s.show}
        if not wanted:
            return {}
        rows = (
            await self.db.execute(
                select(ReceiptAsset).options(undefer(ReceiptAsset.data))
                .where(ReceiptAsset.organization_id == organization_id, ReceiptAsset.id.in_(set(wanted.values())))
            )
        ).scalars().all()
        by_id = {a.id: a for a in rows}
        return {slot: to_image(by_id[aid]) for slot, aid in wanted.items() if aid in by_id and by_id[aid].kind == slot}

    async def asset_fingerprints(self, organization_id: uuid.UUID, design: ReceiptDesign) -> dict[str, dict]:
        wanted = {slot: s.asset_id for slot, s in design.slots().items() if s.asset_id is not None and s.show}
        if not wanted:
            return {}
        rows = (
            await self.db.execute(select(ReceiptAsset.id, ReceiptAsset.kind, ReceiptAsset.sha256).where(ReceiptAsset.organization_id == organization_id, ReceiptAsset.id.in_(set(wanted.values()))))
        ).all()
        by_id = {r.id: r for r in rows}
        return {slot: {"id": str(aid), "sha256": by_id[aid].sha256} for slot, aid in wanted.items() if aid in by_id and by_id[aid].kind == slot}

    async def snapshot(self, organization_id: uuid.UUID, resolved: Resolved) -> dict:
        """What is written into an issued document: which design it was made with, exactly, and the images' checksums."""
        return {
            "source": resolved.source, "design_id": str(resolved.design_id) if resolved.design_id else None, "version": resolved.version,
            "design": dump(resolved.design), "assets": await self.asset_fingerprints(organization_id, resolved.design),
        }  # fmt: skip

    # ---------------------------------------------------------------- the designer's screen

    async def view(self, internship: OurInternship, user: User) -> dict:
        await self._need_view(user)
        org = internship.organization_id
        own = await self._record(org, "internship", internship.id)
        default = await self._record(org, "organization")
        resolved = await self.resolve(org, internship.id)
        templates = (
            await self.db.execute(
                select(ReceiptDesignRecord).where(ReceiptDesignRecord.organization_id == org, ReceiptDesignRecord.scope == "template", ReceiptDesignRecord.archived.is_(False))
                .order_by(ReceiptDesignRecord.name)
            )
        ).scalars().all()  # fmt: skip
        return {
            "effective": {"design": dump(resolved.design), "source": resolved.source, "version": resolved.version},
            "internship_design": {"design": own.design, "version": own.version} if own else None,
            "organization_design": {"design": default.design, "version": default.version} if default else None,
            "built_in": dump(default_design()),
            "templates": [{"id": t.id, "name": t.name, "description": t.description, "version": t.version, "design": t.design} for t in templates],
            "assets": [await self._asset_out(a) for a in await self.assets(org)],
            "can_edit": await has(self.db, user, FINANCE_MANAGE),
        }

    @staticmethod
    async def _asset_out(a: ReceiptAsset) -> dict:
        return {"id": a.id, "kind": a.kind, "filename": a.filename, "width_px": a.width_px, "height_px": a.height_px, "size_bytes": a.size_bytes, "created_at": a.created_at}

    async def _need_view(self, user: User) -> None:
        if not (await has(self.db, user, FINANCE_VIEW) or await has(self.db, user, FINANCE_MANAGE)):
            await require(self.db, user, FINANCE_VIEW)

    async def _need_manage(self, user: User) -> None:
        await require(self.db, user, FINANCE_MANAGE)

    # ---------------------------------------------------------------- saving

    async def check(self, organization_id: uuid.UUID, data: dict) -> ReceiptDesign:
        """A design as submitted: valid, and every image it names is one of this organization's own, of the right kind."""
        try:
            design = parse_design(data)
        except PydanticValidationError as exc:
            raise ValidationError(first_error(exc)) from None
        for slot, s in design.slots().items():
            if s.asset_id is None:
                continue
            asset = await self.db.get(ReceiptAsset, s.asset_id)
            if asset is None or asset.organization_id != organization_id or asset.kind != slot or asset.archived_at is not None:
                raise ValidationError(f"The {slot} image is not available. Upload it again.")
        return design

    async def save(self, internship: OurInternship, user: User, scope: str, data: dict, base_version: int | None = None) -> ReceiptDesignRecord:
        await self._need_manage(user)
        if scope not in ("internship", "organization"):
            raise ValidationError("Choose the internship or the organization.")
        org = internship.organization_id
        design = await self.check(org, data)
        record = await self._record(org, scope, internship.id if scope == "internship" else None)
        if record is not None and base_version is not None and record.version != base_version:
            raise ConflictError("Someone else saved this design meanwhile. Reload it and apply your changes again.")
        if record is not None and record.design == dump(design):
            return record  # nothing changed: no new version
        if record is None:
            record = ReceiptDesignRecord(
                organization_id=org, scope=scope, internship_id=internship.id if scope == "internship" else None, design=dump(design),
                version=1, updated_by_user_id=user.id,
            )  # fmt: skip
        else:
            record.design, record.version, record.updated_by_user_id = dump(design), record.version + 1, user.id
        await self._persist(record, "That design was saved at the same moment by someone else. Reload and try again.")
        self.db.add(ReceiptDesignVersion(organization_id=org, design_id=record.id, version=record.version, design=dump(design), created_by_user_id=user.id))
        await self.db.flush()
        return record

    async def _persist(self, record, conflict: str) -> None:
        """Add and flush inside a savepoint: a unique-index clash (two saves at once, a repeated template name) is reported as a conflict and
        leaves the session usable."""
        try:
            async with self.db.begin_nested():
                self.db.add(record)
                await self.db.flush()
        except IntegrityError:
            raise ConflictError(conflict) from None

    async def reset(self, internship: OurInternship, user: User, scope: str) -> None:
        """Back to the default: an internship's own design is removed (it then follows the organization's); the organization's design is
        removed too (documents then use the built-in design). Documents already issued are untouched."""
        await self._need_manage(user)
        if scope not in ("internship", "organization"):
            raise ValidationError("Choose the internship or the organization.")
        record = await self._record(internship.organization_id, scope, internship.id if scope == "internship" else None)
        if record is None:
            return
        await self.db.delete(record)
        await self.db.flush()

    # ---------------------------------------------------------------- templates

    async def template(self, organization_id: uuid.UUID, template_id: uuid.UUID) -> ReceiptDesignRecord:
        record = await self.db.get(ReceiptDesignRecord, template_id)
        if record is None or record.organization_id != organization_id or record.scope != "template" or record.archived:
            raise NotFoundError("Receipt template", template_id)
        return record

    async def create_template(self, internship: OurInternship, user: User, name: str, description: str | None, data: dict) -> ReceiptDesignRecord:
        await self._need_manage(user)
        name = " ".join((name or "").split())
        if not name or len(name) > 120:
            raise ValidationError("Give the template a name of up to 120 characters.")
        org = internship.organization_id
        count = (await self.db.execute(select(func.count(ReceiptDesignRecord.id)).where(ReceiptDesignRecord.organization_id == org, ReceiptDesignRecord.scope == "template", ReceiptDesignRecord.archived.is_(False)))).scalar_one()
        if count >= MAX_TEMPLATES:
            raise ConflictError("There are too many templates. Archive one first.")
        design = await self.check(org, data)
        record = ReceiptDesignRecord(organization_id=org, scope="template", name=name, description=(description or "").strip()[:500] or None, design=dump(design), version=1, updated_by_user_id=user.id)
        await self._persist(record, "A template with that name already exists.")
        return record

    async def apply_template(self, internship: OurInternship, user: User, template_id: uuid.UUID, scope: str) -> ReceiptDesignRecord:
        await self._need_manage(user)
        template = await self.template(internship.organization_id, template_id)
        return await self.save(internship, user, scope, template.design)

    async def archive_template(self, internship: OurInternship, user: User, template_id: uuid.UUID) -> None:
        await self._need_manage(user)
        template = await self.template(internship.organization_id, template_id)
        template.archived = True
        await self.db.flush()

    # ---------------------------------------------------------------- images

    async def assets(self, organization_id: uuid.UUID) -> list[ReceiptAsset]:
        rows = await self.db.execute(
            select(ReceiptAsset).where(ReceiptAsset.organization_id == organization_id, ReceiptAsset.archived_at.is_(None)).order_by(ReceiptAsset.created_at.desc()).limit(100)
        )
        return list(rows.scalars())

    async def upload(self, internship: OurInternship, user: User, kind: str, filename: str, data: bytes) -> dict:
        await self._need_manage(user)
        png, width, height = normalize_image(data, kind)
        from modules.internship_learning.files import safe_filename

        asset = ReceiptAsset(
            organization_id=internship.organization_id, kind=kind, filename=safe_filename(filename or "image.png")[:160], content_type="image/png",
            size_bytes=len(png), width_px=width, height_px=height, sha256=hashlib.sha256(png).hexdigest(), data=png, uploaded_by_user_id=user.id,
        )  # fmt: skip
        self.db.add(asset)
        await self.db.flush()
        return await self._asset_out(asset)

    async def asset(self, internship: OurInternship, user: User, asset_id: uuid.UUID) -> ReceiptAsset:
        await self._need_view(user)
        asset = (await self.db.execute(select(ReceiptAsset).options(undefer(ReceiptAsset.data)).where(ReceiptAsset.id == asset_id))).scalar_one_or_none()
        if asset is None or asset.organization_id != internship.organization_id or asset.archived_at is not None:
            raise NotFoundError("Image", asset_id)
        return asset

    async def archive_asset(self, internship: OurInternship, user: User, asset_id: uuid.UUID) -> None:
        """Remove an image from the library. An image a saved design still uses is kept (documents issued with it are traced to it)."""
        await self._need_manage(user)
        asset = await self.asset(internship, user, asset_id)
        designs = (await self.db.execute(select(ReceiptDesignRecord).where(ReceiptDesignRecord.organization_id == internship.organization_id, ReceiptDesignRecord.archived.is_(False)))).scalars().all()
        for record in designs:
            try:
                if asset_id in parse_design(record.design).asset_ids():
                    raise ConflictError("This image is used by a saved design or template. Change that design first.")
            except PydanticValidationError:
                continue
        asset.archived_at = now()
        await self.db.flush()


    # ---------------------------------------------------------------- preview (read-only)

    async def preview(
        self, internship: OurInternship, user: User, design_data: dict | None, kind: str, source: str, transaction_id: uuid.UUID | None,
    ) -> tuple[bytes, int, str]:  # fmt: skip
        """(PDF, pages, watermark) of a document as the draft design would draw it. Read-only: no document number is taken, nothing is
        stored or sent, no payment or ledger record is touched, and every page is marked as a sample or preview."""
        from decimal import Decimal

        from modules.internship_onboarding import financial
        from modules.internship_onboarding.models import OnboardingApplication, PaymentTransaction
        from modules.internship_onboarding.receipt_pdf import build_receipt_pdf

        await self._need_view(user)
        org = internship.organization_id
        design = await self.check(org, design_data) if design_data is not None else (await self.resolve(org, internship.id)).design
        images = await self.images_for(org, design)
        stub = {"design": dump(design)}
        if source == "transaction":
            if transaction_id is None:
                raise ValidationError("Choose a payment to preview.")
            tx = (
                await self.db.execute(
                    select(PaymentTransaction).join(OnboardingApplication, OnboardingApplication.id == PaymentTransaction.application_id)
                    .where(PaymentTransaction.id == transaction_id, OnboardingApplication.internship_id == internship.id, PaymentTransaction.organization_id == org)
                )
            ).scalar_one_or_none()  # fmt: skip
            if tx is None:
                raise NotFoundError("Payment", transaction_id)
            if tx.status != "confirmed" or tx.kind not in ("payment", "refund"):
                raise ConflictError("Only a confirmed payment or refund has a document to preview.")
            ctx = await financial.load_context(self.db, tx)
            kind = financial.kind_for(tx, ctx.config)
            issued_doc = (await self.db.execute(select(financial.FinancialDocument).where(financial.FinancialDocument.transaction_id == tx.id))).scalar_one_or_none()
            details = financial.build_details(ctx, tx, kind, issued_doc.issued_at if issued_doc else now(), await financial._against(self.db, tx), design=stub)
            number, watermark = "PREVIEW", "PREVIEW - NOT AN OFFICIAL COPY"
        else:
            if kind not in financial.TITLES:
                raise ValidationError("Choose receipt, tax invoice or credit note.")
            _, config = await financial.config_of(self.db, internship)
            rate, label = config.fees.tax_rate_percent, config.fees.tax_label
            if config.fees.tax_mode == "none" or rate <= 0:
                rate, label = Decimal("18"), "GST"
            amount = Decimal("5900.00")
            issuer = config.issuer
            details = {
                "kind": kind,
                "issuer": {"name": issuer.legal_name or "Your organization", "address": issuer.address or "Sample address, City, State 000000",
                           "gstin": issuer.gstin or ("22AAAAA0000A1Z5" if kind == "tax_invoice" else None)},  # fmt: skip
                "student": {"name": "Sample Student", "email": "student@example.com", **({"phone": "98765 43210"} if design.sections.student_mobile else {})},
                "application_reference": "ERPX-INT-2026-000001", "internship": internship.title, "description": config.fees.description,
                "method": "Online (Cashfree)", "transaction_reference": "SAMPLE-1234567890", "paid_on": now().date().isoformat(),
                "issued_on": now().date().isoformat(), "currency": config.fees.currency, "amount": str(amount),
                "tax": financial.tax_lines(amount, {"tax_mode": "inclusive", "tax_rate_percent": str(rate), "tax_label": label}) if kind == "tax_invoice" else None,
                "against": "Receipt SAMPLE-0001" if kind == "credit_note" else None, "footer": issuer.footer,
            }  # fmt: skip
            number, watermark = "SAMPLE-0001", "SAMPLE - NOT A VALID RECEIPT"
        pdf, pages = build_receipt_pdf(kind, number, details, design, images, watermark)
        return pdf, pages, watermark
