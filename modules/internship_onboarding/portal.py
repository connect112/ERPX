"""
The student's side, reached only through their link. The token is hashed and looked up; nothing else identifies the
student, and every query is scoped to the one application it resolves to.

After the student's deadline the link is read-only: what they already did stays visible (and payment of an accepted
offer stays possible until the payment deadline), but nothing new can be submitted.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.institutions.models import Institution, InstitutionStudent
from modules.internship_onboarding import fees as fee_maths
from modules.internship_onboarding import forms, ledger, state
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.models import OnboardingApplication, OnboardingDocument
from modules.internship_onboarding.service import (
    ApplicationService,
    config_of,
    effective_deadline,
    event,
    hash_token,
    now,
    payment_deadline,
)
from modules.organizations.models import Organization
from modules.our_internships.models import InternshipSelection, OfferResponse, OurInternship

STEPS = ("welcome", "information", "form", "documents", "acceptance", "payment", "done")
SIGNATURES = {"pdf": (b"%PDF-",), "jpg": (b"\xff\xd8\xff",), "png": (b"\x89PNG\r\n\x1a\n",)}
CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}
GONE = "This onboarding link is not valid. It may have been replaced by a newer one; use the latest email you received."


@dataclass
class Context:
    application: OnboardingApplication
    selection: InternshipSelection
    student: InstitutionStudent
    internship: OurInternship
    config: OnboardingConfig
    deadline: datetime | None

    @property
    def open(self) -> bool:
        """May the student still submit (information, form, documents, acceptance)?"""
        c = self.config.deadlines
        if self.application.cancelled_at is not None:
            return False
        if self.application.deadline_override_at is None and c.opens_at and now() < c.opens_at:
            return False
        return self.deadline is None or now() <= self.deadline


def sniff(data: bytes) -> str | None:
    for kind, prefixes in SIGNATURES.items():
        if any(data.startswith(p) for p in prefixes):
            return kind
    return None


class PortalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.apps = ApplicationService(db)

    async def resolve(self, token: str) -> Context:
        if not token or len(token) > 200:
            raise NotFoundError("Onboarding link", "")
        application = (
            await self.db.execute(select(OnboardingApplication).where(OnboardingApplication.token_hash == hash_token(token)))
        ).scalar_one_or_none()
        if application is None or application.token_revoked_at is not None:
            raise NotFoundError("Onboarding link", "")
        selection = await self.db.get(InternshipSelection, application.selection_id)
        internship = await self.db.get(OurInternship, application.internship_id)
        if selection is None or internship is None or internship.organization_id != application.organization_id:
            raise NotFoundError("Onboarding link", "")
        student = await self.db.get(InstitutionStudent, selection.student_id)
        if student is None:
            raise NotFoundError("Onboarding link", "")
        _, config = await config_of(self.db, internship)
        if not config.modes.self_service:
            raise NotFoundError("Onboarding link", "")
        return Context(application, selection, student, internship, config, effective_deadline(application, config))

    def _touch(self, ctx: Context, step: str | None = None) -> None:
        ctx.application.last_activity_at = now()
        if ctx.application.started_at is None:
            ctx.application.started_at = now()
        if step and STEPS.index(step) > STEPS.index(ctx.application.current_step):
            ctx.application.current_step = step

    def _require_open(self, ctx: Context) -> None:
        if not ctx.open:
            raise ConflictError("Onboarding is closed for you. Contact the internship team if you need more time.")
        if ctx.selection.offer_response == OfferResponse.DECLINED:
            raise ConflictError("You declined this offer.")

    async def _info(self, ctx: Context) -> dict:
        institution = await self.db.get(Institution, ctx.student.institution_id)
        return {
            "name": ctx.student.name,
            "email": ctx.student.email,
            "phone": ctx.student.phone,
            "institution": institution.name if institution else None,
            "details": dict(ctx.student.details or {}),
        }

    # ---------------------------------------------------------------- reading

    async def view(self, ctx: Context) -> dict:
        app, cfg = ctx.application, ctx.config
        docs = await self.apps.documents(app.id)
        current_total = fee_maths.total_of(fee_maths.snapshot(cfg.fees))
        totals = await ledger.totals(self.db, app, current_total)
        f = await self.apps.facts(cfg, ctx.selection, app, docs, totals)
        org = await self.db.get(Organization, ctx.internship.organization_id)
        if not app.info_original:
            app.info_original = await self._info(ctx)
            await self.db.flush()
        latest: dict[str, OnboardingDocument] = {}
        for d in docs:
            if d.status != "superseded" and d.requirement_key not in latest:
                latest[d.requirement_key] = d
        overall = state.overall_status(f)
        completed = overall == "completed"
        accepted = state.offer_status(f) == "accepted"
        comms = cfg.communication
        show_whatsapp = bool(comms.whatsapp_link) and (completed or (accepted and comms.whatsapp_visibility == "after_acceptance"))
        pay_until = payment_deadline(app, cfg)
        payment_open = state.payment_open(f) and (pay_until is None or now() <= pay_until)
        return {
            "organization": org.name if org else "",
            "internship": {"title": ctx.internship.title, "description": ctx.internship.description},
            "student_name": ctx.student.name,
            "reference": app.reference,
            "deadline": ctx.deadline,
            "timezone": cfg.deadlines.timezone,
            "open": ctx.open,
            "current_step": app.current_step,
            "statuses": {
                "offer": state.offer_status(f), "documents": state.document_status(f),
                "payment": state.payment_status(f), "overall": overall,
            },
            "information": {
                "current": await self._info(ctx), "proposed": app.info_proposed, "review": app.info_review_status,
                "editable": cfg.modes.allow_info_edit,
            },
            "form": {
                "fields": [fld.model_dump(mode="json") for fld in cfg.form],
                "answers": app.form_responses,
            },
            "documents": [
                {
                    "key": r.key, "label": r.label, "instructions": r.instructions, "required": r.required, "types": r.types,
                    "max_mb": r.max_mb, "sensitive": r.sensitive,
                    "status": latest[r.key].status if r.key in latest else "not_submitted",
                    "filename": latest[r.key].filename if r.key in latest else None,
                    "note": latest[r.key].review_note if r.key in latest and latest[r.key].status == "rejected" else None,
                }
                for r in cfg.documents
            ] if cfg.modes.require_documents else [],
            "acceptance": {
                "declaration": cfg.declaration.text, "terms_version": cfg.declaration.terms_version,
                "terms_url": cfg.declaration.terms_url,
                "fees": app.fee_snapshot or (fee_maths.snapshot(cfg.fees) if cfg.modes.require_payment else None),
                "accepted_at": app.accepted_at, "declined_at": app.declined_at,
            },
            "payment": {
                "required": cfg.modes.require_payment,
                "open": payment_open,
                "payable": str(totals.payable), "paid": str(totals.paid - totals.refunded), "balance": str(totals.balance),
                "currency": cfg.fees.currency,
                "methods": cfg.fees.methods if payment_open else [],
                "bank": cfg.payment_accounts.bank.model_dump() if payment_open and cfg.payment_accounts.bank and "bank_transfer" in cfg.fees.methods else None,
                "upi": cfg.payment_accounts.upi.model_dump() if payment_open and cfg.payment_accounts.upi and "upi" in cfg.fees.methods else None,
                "deadline": pay_until,
            },
            "completion": {
                "completed": completed,
                "next_steps": cfg.communication.next_steps if completed else "",
                "whatsapp_link": comms.whatsapp_link if show_whatsapp else None,
                "lms_status": ctx.selection.lms_status.value,
            },
            "contact": {"email": comms.contact_email, "phone": comms.contact_phone},
        }  # fmt: skip

    # ---------------------------------------------------------------- drafts

    async def save(self, ctx: Context, step: str | None, info: dict | None, answers: dict | None) -> dict:
        """Save progress. Partial answers are fine; only the answers given are checked."""
        self._require_open(ctx)
        if ctx.application.accepted_at is not None and (info is not None or answers is not None):
            raise ConflictError("You have already accepted the offer; contact the internship team to change your details.")
        errors: dict[str, str] = {}
        if info is not None:
            if not ctx.config.modes.allow_info_edit:
                raise ValidationError("Your details cannot be edited here. Contact the internship team if something is wrong.")
            proposed = self._clean_info(info, await self._info(ctx))
            if proposed != (ctx.application.info_proposed or {}):
                ctx.application.info_proposed = proposed
                ctx.application.info_review_status = "pending" if proposed else "none"
                await event(self.db, ctx.application, "info_changes_proposed", actor="student", fields=sorted(proposed))
        if answers is not None:
            kept, errors = forms.clean(ctx.config.form, {**ctx.application.form_responses, **answers}, complete=False)
            ctx.application.form_responses = kept
            record, _ = await config_of(self.db, ctx.internship)
            ctx.application.form_version = record.version if record else 0
        self._touch(ctx, step if step in STEPS else None)
        await self.db.flush()
        return {"errors": errors}

    @staticmethod
    def _clean_info(info: dict, current: dict) -> dict:
        """Only real differences are kept, and only for name, phone and the imported detail columns."""
        out: dict = {}
        name = " ".join(str(info.get("name") or "").split())[:255]
        if name and name != current["name"]:
            out["name"] = name
        if "phone" in info:
            phone = " ".join(str(info.get("phone") or "").split())[:50]
            if phone != (current["phone"] or "") and (not phone or forms._PHONE.match(phone)):
                out["phone"] = phone
        details = {k: " ".join(str(v).split())[:255] for k, v in (info.get("details") or {}).items() if isinstance(k, str) and k in current["details"]}
        changed = {k: v for k, v in details.items() if v != current["details"].get(k)}
        if changed:
            out["details"] = changed
        return out

    # ---------------------------------------------------------------- documents

    async def upload(self, ctx: Context, key: str, filename: str, data: bytes) -> OnboardingDocument:
        from modules.internship_learning.files import safe_filename
        from packages.storage.client import get_storage_client

        self._require_open(ctx)
        cfg = ctx.config
        requirement = next((r for r in cfg.documents if r.key == key), None)
        if requirement is None or not cfg.modes.require_documents:
            raise NotFoundError("Document requirement", key)
        if not data:
            raise ValidationError("The file is empty.")
        if len(data) > requirement.max_mb * 1024 * 1024:
            raise ValidationError(f"The file is larger than {requirement.max_mb} MB.")
        kind = sniff(data)
        if kind is None or kind not in requirement.types:
            allowed = ", ".join(t.upper() for t in requirement.types)
            raise ValidationError(f"Upload a {allowed} file. The file's contents do not match an allowed type.")
        await self.db.execute(select(OnboardingApplication.id).where(OnboardingApplication.id == ctx.application.id).with_for_update())
        versions = (
            await self.db.execute(
                select(OnboardingDocument).where(OnboardingDocument.application_id == ctx.application.id, OnboardingDocument.requirement_key == key)
                .order_by(OnboardingDocument.version.desc())
            )
        ).scalars().all()  # fmt: skip
        live = next((d for d in versions if d.status != "superseded"), None)
        if live is not None and live.status == "verified":
            raise ConflictError("This document has already been verified. Contact the internship team if it must be replaced.")
        version = (versions[0].version + 1) if versions else 1
        name = safe_filename(filename)
        if not name.lower().endswith("." + kind) and not (kind == "jpg" and name.lower().endswith(".jpeg")):
            name = f"{name.rsplit('.', 1)[0]}.{kind}"
        storage_key = f"onboarding/{ctx.application.organization_id}/{ctx.application.id}/{key}/v{version}-{uuid.uuid4().hex}.{kind}"
        await get_storage_client().upload_bytes(storage_key, data, CONTENT_TYPES[kind])
        if live is not None:
            live.status = "superseded"
        document = OnboardingDocument(
            organization_id=ctx.application.organization_id, application_id=ctx.application.id, requirement_key=key,
            version=version, filename=name[:160], content_type=CONTENT_TYPES[kind], size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(), storage_key=storage_key, status="submitted",
        )
        self.db.add(document)
        self._touch(ctx, "documents")
        await self.db.flush()
        await event(self.db, ctx.application, "document_submitted", actor="student", document=key, version=version)
        return document

    # ---------------------------------------------------------------- the decision

    async def accept(self, ctx: Context, confirmed: bool, terms_version: str, ip: str | None, user_agent: str | None) -> None:
        self._require_open(ctx)
        cfg, app = ctx.config, ctx.application
        if ctx.selection.offer_response == OfferResponse.ACCEPTED:
            raise ConflictError("You have already accepted this offer.")
        acceptance_deadline = cfg.deadlines.acceptance_deadline
        if app.deadline_override_at is None and acceptance_deadline and now() > acceptance_deadline:
            raise ConflictError("The deadline to accept this offer has passed.")
        if not confirmed:
            raise ValidationError("Tick the declaration to accept the offer.")
        if terms_version != cfg.declaration.terms_version:
            raise ConflictError("The terms have changed since you opened this page. Reload and read them again.")
        _, errors = forms.clean(cfg.form, app.form_responses, complete=True)
        if errors:
            raise ValidationError("Complete the form before accepting: " + ", ".join(sorted(errors)))
        record, _ = await config_of(self.db, ctx.internship)
        snapshot = fee_maths.snapshot(cfg.fees) if cfg.modes.require_payment else {**fee_maths.snapshot(cfg.fees), "total": "0.00"}
        t = now()
        ctx.selection.offer_response = OfferResponse.ACCEPTED
        ctx.selection.offer_response_at = t
        app.accepted_at, app.declined_at, app.decline_reason = t, None, None
        app.terms_version = cfg.declaration.terms_version
        app.declaration_text = cfg.declaration.text
        app.config_version = record.version if record else 0
        app.fee_snapshot = snapshot
        # enough to recognise the device later, without keeping the raw address
        app.acceptance_meta = {
            "ip_hash": hashlib.sha256(f"{settings.JWT_SECRET_KEY}:{ip or ''}".encode()).hexdigest()[:16] if ip else None,
            "user_agent": (user_agent or "")[:160],
        }
        self._touch(ctx, "payment" if cfg.modes.require_payment else "done")
        await self.db.flush()
        await event(self.db, app, "offer_accepted", actor="student", terms_version=app.terms_version, total=snapshot["total"])
        from modules.internship_onboarding.completion import check_and_queue

        await check_and_queue(self.db, app)

    async def decline(self, ctx: Context, reason: str | None) -> None:
        self._require_open(ctx)
        if ctx.selection.offer_response == OfferResponse.ACCEPTED:
            raise ConflictError("You have already accepted this offer. Contact the internship team to withdraw.")
        t = now()
        ctx.selection.offer_response = OfferResponse.DECLINED
        ctx.selection.offer_response_at = t
        ctx.application.declined_at = t
        ctx.application.decline_reason = (reason or "").strip()[:1000] or None
        self._touch(ctx)
        await self.db.flush()
        await event(self.db, ctx.application, "offer_declined", actor="student", reason=ctx.application.decline_reason)
