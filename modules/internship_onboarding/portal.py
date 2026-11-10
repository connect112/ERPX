"""
The student's side, reached only through their link. The token is hashed and looked up; nothing else identifies the
student, and every query is scoped to the one application it resolves to.

After the student's deadline the link is read-only: what they already did stays visible (and payment of an accepted
offer stays possible until the payment deadline), but nothing new can be submitted.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthorizationError, ConflictError, ERPXException, NotFoundError, ServiceUnavailableError, ValidationError
from modules.institutions.models import Institution, InstitutionStudent
from modules.internship_onboarding import fees as fee_maths
from modules.internship_onboarding.scan import scan
from modules.internship_onboarding.accounts import PaymentAccountService, qr_png_data_url, upi_link
from modules.internship_onboarding import forms, ledger, state
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.phone import INVALID as INVALID_MOBILE
from modules.internship_onboarding.phone import mask, normalize_mobile
from modules.internship_onboarding.models import OnboardingApplication, OnboardingDocument, PaymentTransaction
from modules.internship_onboarding.service import (
    ApplicationService,
    config_of,
    effective_deadline,
    event,
    hash_token,
    now,
    payment_deadline,
    pending_is_alive,
)
from modules.organizations.models import Organization
from modules.our_internships.course_links import learning_course_for_portal
from modules.our_internships.models import InternshipSelection, OfferResponse, OurInternship

STEPS = ("welcome", "information", "form", "documents", "acceptance", "payment", "done")
SIGNATURES = {"pdf": (b"%PDF-",), "jpg": (b"\xff\xd8\xff",), "png": (b"\x89PNG\r\n\x1a\n",)}
CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}
GONE = "This onboarding link is not valid. It may have been replaced by a newer one; use the latest email you received."
LINK_EXPIRED = (
    "This onboarding link has expired. Your onboarding information has been saved. "
    "Please contact the internship team if you need assistance."
)


class LinkExpiredError(ERPXException):
    """The student's personal link was valid but its hour after completion is over (410 Gone)."""

    status_code = 410
    error_code = "onboarding_link_expired"


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


NO_REFUND_REQUESTS_NOTICE = (
    "Refund requests are not taken through this page. This does not affect any refund you are entitled to by law; for any "
    "question about your payment, contact the internship team."
)


def refund_terms_of(cfg: OnboardingConfig) -> dict:
    """The refund terms a student accepting now agrees to (stored with the acceptance)."""
    p = cfg.policies
    if p.allow_refund_requests:
        return {
            "allow_refund_requests": True, "policy_version": p.refund_policy_version,
            "policy_sha256": hashlib.sha256(p.refund_policy.encode()).hexdigest(), "request_days": p.refund_request_days,
        }  # fmt: skip
    return {"allow_refund_requests": False, "notice": NO_REFUND_REQUESTS_NOTICE if cfg.modes.require_payment else None}


class PortalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.apps = ApplicationService(db)

    async def resolve(self, token: str) -> Context:
        if not token or len(token) > 200:
            raise NotFoundError("Onboarding link", "")
        digest = hash_token(token)
        application = (
            await self.db.execute(
                select(OnboardingApplication).where(or_(OnboardingApplication.token_hash == digest, OnboardingApplication.pending_token_hash == digest))
            )
        ).scalar_one_or_none()
        if application is None or application.token_revoked_at is not None:
            raise NotFoundError("Onboarding link", "")
        # A link an email carries but that was not confirmed yet works for a limited time; using it confirms it.
        via_pending = application.token_hash != digest
        if via_pending and (application.cancelled_at is not None or not pending_is_alive(application)):
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
        # Every student endpoint resolves its link here, so this one check covers them all. It comes before a pending link is
        # promoted: an expired link is never made the active one.
        if await self._link_expired(application, selection, config):
            raise LinkExpiredError(LINK_EXPIRED)
        if via_pending:
            await self.apps.promote_pending(application.id, digest, reason="first_use")
        return Context(application, selection, student, internship, config, effective_deadline(application, config))

    async def _link_expired(self, application: OnboardingApplication, selection: InternshipSelection, config: OnboardingConfig) -> bool:
        """Is the hour after completion over? The window is recorded on the server when onboarding is completed
        (``link_expires_at``, set once, in the same statement as ``completed_at``), so a retry, a second tab or a second request
        cannot move it. It ends the link only while the student still has nothing left to do: if a late fee, a refund or a document
        sent back has made something outstanding again, the link keeps working, the window is cleared, and a fresh hour starts when
        everything is met again (``completion.check``)."""
        expires = application.link_expires_at
        if expires is None or now() < expires:
            return False
        if state.overall_status(await self.apps.facts(config, selection, application)) == "completed":
            return True
        cleared = await self.db.execute(
            update(OnboardingApplication)
            .where(OnboardingApplication.id == application.id, OnboardingApplication.link_expires_at == expires)
            .values(link_expires_at=None)
            .execution_options(synchronize_session=False)
        )  # fmt: skip  (compare-and-swap: a completion recorded meanwhile keeps its new window)
        if cleared.rowcount == 1:
            await self.db.refresh(application)
            await event(self.db, application, "link_window_paused", actor="system", reason="something is outstanding again")
        return False

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

    def _mobile(self, ctx: Context) -> dict:
        """The student's payment mobile number as the page shows it: the number they confirmed, or the one on their record, and
        whether it is waiting for staff to update the record."""
        app = ctx.application
        usable = normalize_mobile(app.confirmed_phone) or normalize_mobile(ctx.student.phone)
        proposed = app.info_proposed or {}
        pending = app.info_review_status == "pending" and ("phone_change" in proposed or "phone" in proposed)
        return {
            "number": usable or ctx.student.phone,
            "confirmed": app.confirmed_phone is not None,
            "valid": usable is not None,  # a number Cashfree will accept
            "record_review_pending": pending,
            "editable": app.cancelled_at is None and ctx.selection.offer_response != OfferResponse.DECLINED,
        }

    # ---------------------------------------------------------------- payment methods and refund terms

    async def offered(self, ctx: Context) -> tuple[list[str], dict[str, dict | None]]:
        """The payment methods a student can use now and their details: Cashfree only while the installation has it on,
        bank/UPI only with details from the settings or an enabled, verified saved account."""
        details = await PaymentAccountService(self.db).for_students(ctx.internship.organization_id, ctx.config)
        usable = {"cashfree": settings.CASHFREE_ENABLED, "bank_transfer": details["bank"] is not None, "upi": details["upi"] is not None}
        return [m for m in ctx.config.fees.methods if usable[m]], details

    async def refund_window(self, app: OnboardingApplication, totals) -> tuple[bool, datetime | None]:
        """Whether the student may ask for a refund now, under the terms they accepted (never today's settings)."""
        terms = app.refund_terms or {}
        if not terms.get("allow_refund_requests") or totals.paid - totals.refunded <= 0:
            return False, None
        if (app.refund_request or {}).get("status") == "open":
            return False, None
        last = (
            await self.db.execute(
                select(func.max(PaymentTransaction.verified_at)).where(
                    PaymentTransaction.application_id == app.id, PaymentTransaction.kind == "payment", PaymentTransaction.status == "confirmed"
                )
            )
        ).scalar_one_or_none()  # fmt: skip
        until = last + timedelta(days=terms["request_days"]) if last and terms.get("request_days") else None
        return (until is None or now() <= until), until

    async def request_refund(self, ctx: Context, reason: str) -> None:
        """Ask for a refund. Nothing is refunded here: finance staff decide, and pay any refund through the usual route."""
        app = ctx.application
        if not (app.refund_terms or {}).get("allow_refund_requests"):
            raise ConflictError("Refund requests are not part of the terms you accepted. Contact the internship team about your payment.")
        if not reason.strip():
            raise ValidationError("Tell us why you are asking for a refund.")
        await self.db.execute(select(OnboardingApplication.id).where(OnboardingApplication.id == app.id).with_for_update())
        totals = await ledger.totals(self.db, app, fee_maths.total_of(fee_maths.snapshot(ctx.config.fees)))
        allowed, until = await self.refund_window(app, totals)
        if not allowed:
            if (app.refund_request or {}).get("status") == "open":
                raise ConflictError("Your refund request is already with the internship team.")
            if totals.paid - totals.refunded <= 0:
                raise ConflictError("There is no payment to refund.")
            raise ConflictError("The period for refund requests under your accepted terms has ended.")
        app.refund_request = {
            "status": "open", "reason": reason.strip()[:1000], "requested_at": now().isoformat(),
            "policy_version": (app.refund_terms or {}).get("policy_version"),
        }  # fmt: skip
        self._touch(ctx)
        await self.db.flush()
        await event(self.db, app, "refund_request_submitted", actor="student", reason=reason.strip()[:200])

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
        methods, details = await self.offered(ctx) if payment_open else ([], {"bank": None, "upi": None})
        upi = details["upi"] if "upi" in methods else None
        if upi and totals.balance > 0:
            # a payment-specific UPI request: this account, exactly what is owed, the student's reference as the note
            link = upi_link(upi, totals.balance, app.reference)
            upi = {**upi, "link": link, "qr": qr_png_data_url(link) if upi.get("show_qr", True) else None}
        can_request_refund, refund_until = await self.refund_window(app, totals)
        policies = cfg.policies
        return {
            "organization": org.name if org else "",
            "internship": {"title": ctx.internship.title, "description": ctx.internship.description},
            # the linked LMS course (title, description, level, duration), read live; absent when none is linked. Never a price.
            "learning_course": await learning_course_for_portal(self.db, ctx.internship, ctx.selection),
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
            "mobile": self._mobile(ctx),
            "form": {
                "fields": [fld.model_dump(mode="json") for fld in cfg.form],
                "answers": app.form_responses,
            },
            "documents": [
                {
                    "key": r.key, "label": r.label, "instructions": r.instructions, "required": r.required, "types": r.types,
                    "max_mb": r.max_mb, "sensitive": r.sensitive, "accepting": not r.sensitive or settings.CLAMAV_ENABLED,
                    "status": latest[r.key].status if r.key in latest else "not_submitted",
                    "filename": latest[r.key].filename if r.key in latest else None,
                    "note": latest[r.key].review_note if r.key in latest and latest[r.key].status == "rejected" else None,
                }
                for r in cfg.documents
            ] if cfg.modes.require_documents else [],
            "identity_document_retention_days": cfg.policies.identity_document_retention_days,
            "acceptance": {
                "declaration": cfg.declaration.text, "terms_version": cfg.declaration.terms_version,
                "terms_url": cfg.declaration.terms_url,
                "refund_policy": policies.refund_policy if policies.allow_refund_requests else None,
                "refund_policy_version": policies.refund_policy_version if policies.allow_refund_requests else None,
                "payment_terms_notice": refund_terms_of(cfg).get("notice"),
                "refund_terms": app.refund_terms,
                "fees": app.fee_snapshot or (fee_maths.snapshot(cfg.fees) if cfg.modes.require_payment else None),
                "accepted_at": app.accepted_at, "declined_at": app.declined_at,
                "decline_allowed": cfg.modes.allow_decline,
            },
            "payment": {
                "required": cfg.modes.require_payment,
                "open": payment_open,
                "payable": str(totals.payable), "paid": str(totals.paid - totals.refunded), "balance": str(totals.balance),
                "currency": cfg.fees.currency,
                "methods": methods,
                "bank": details["bank"] if "bank_transfer" in methods else None,
                "upi": upi,
                "deadline": pay_until,
            },
            "refund": {
                "requests_offered": bool((app.refund_terms or {}).get("allow_refund_requests")),
                "can_request": can_request_refund, "until": refund_until,
                "request": {k: v for k, v in (app.refund_request or {}).items() if k != "decided_by"} or None,
            },
            "completion": {
                "completed": completed,
                "next_steps": cfg.communication.next_steps if completed else "",
                "whatsapp_link": comms.whatsapp_link if show_whatsapp else None,
                "lms_status": ctx.selection.lms_status.value,
                # when this link stops working (one hour after completion); the server enforces it, the page only tells the student
                "link_expires_at": app.link_expires_at if completed else None,
            },
            "contact": {"email": comms.contact_email, "phone": comms.contact_phone},
            "financial_documents": [
                {"id": d.id, "kind": d.kind, "number": d.number, "amount": str(d.amount), "currency": d.currency, "issued_at": d.issued_at}
                for d in await self._financial(app.id)
            ],
        }  # fmt: skip

    async def _financial(self, application_id):
        from modules.internship_onboarding.models import FinancialDocument

        rows = await self.db.execute(
            select(FinancialDocument).where(FinancialDocument.application_id == application_id).order_by(FinancialDocument.issued_at)
        )
        return list(rows.scalars())

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
        # (the mobile number is not corrected here: it has its own confirmed step, ``set_mobile``)
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
        if requirement.sensitive and not settings.CLAMAV_ENABLED:
            # identity documents are never accepted unscanned; staff collect them another way until scanning is set up
            raise ServiceUnavailableError(f"{requirement.label} cannot be uploaded here yet. Contact the internship team.")
        if not data:
            raise ValidationError("The file is empty.")
        if len(data) > requirement.max_mb * 1024 * 1024:
            raise ValidationError(f"The file is larger than {requirement.max_mb} MB.")
        kind = sniff(data)
        if kind is None or kind not in requirement.types:
            allowed = ", ".join(t.upper() for t in requirement.types)
            raise ValidationError(f"Upload a {allowed} file. The file's contents do not match an allowed type.")
        scanned = await scan(data, "document")
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
            scan_status=scanned,
        )
        self.db.add(document)
        self._touch(ctx, "documents")
        await self.db.flush()
        await event(self.db, ctx.application, "document_submitted", actor="student", document=key, version=version)
        return document

    # ---------------------------------------------------------------- the decision

    async def accept(
        self, ctx: Context, confirmed: bool, terms_version: str, ip: str | None, user_agent: str | None,
        refund_policy_version: str | None = None,
    ) -> None:  # fmt: skip
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
        if cfg.policies.allow_refund_requests and refund_policy_version != cfg.policies.refund_policy_version:
            raise ConflictError("The refund policy has changed since you opened this page. Reload and read it again.")
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
        # what the student agreed to, word for word, and the refund terms as a snapshot later settings never rewrite
        terms = refund_terms_of(cfg)
        if terms["allow_refund_requests"]:
            extra = f"\n\nRefund policy (version {cfg.policies.refund_policy_version}):\n{cfg.policies.refund_policy}"
        else:
            extra = f"\n\nPayment terms:\n{terms['notice']}" if terms.get("notice") else ""
        app.declaration_text = cfg.declaration.text + extra
        app.refund_terms = terms
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

    # ---------------------------------------------------------------- the mobile number

    async def set_mobile(self, ctx: Context, phone: str, confirmed: bool) -> None:
        """Save the mobile number the student confirmed. It is used for NEW payment orders; orders already created, receipts and
        ledger entries keep what they have. The record on the student's file changes only when staff approve (the usual review)."""
        app = ctx.application
        if not confirmed:
            raise ValidationError("Confirm your mobile number to save it.")
        if app.cancelled_at is not None or ctx.selection.offer_response == OfferResponse.DECLINED:
            raise ConflictError("Onboarding is closed for you. Contact the internship team to update your mobile number.")
        number = normalize_mobile(phone)
        if number is None:
            raise ValidationError(INVALID_MOBILE)
        await self.db.execute(select(OnboardingApplication.id).where(OnboardingApplication.id == app.id).with_for_update())
        await self.db.refresh(app)
        record_number = normalize_mobile(ctx.student.phone)
        before = normalize_mobile(app.confirmed_phone) or record_number
        changed = number != before
        app.confirmed_phone = number
        if changed:
            app.phone_changed_at = now()
        # Staff decide whether the student's record changes. The review request is only a marker: the number itself lives in
        # ``confirmed_phone``, which is kept out of the audit trail (``info_proposed`` is audited).
        proposed = dict(app.info_proposed or {})
        proposed.pop("phone", None)
        if number != record_number:
            proposed["phone_change"] = True
        else:
            proposed.pop("phone_change", None)
        if proposed != (app.info_proposed or {}):
            app.info_proposed = proposed
            if proposed:
                app.info_review_status = "pending"
            elif app.info_review_status == "pending":
                app.info_review_status = "none"  # nothing is left to review
        self._touch(ctx)
        await self.db.flush()
        # only the last four digits ever reach the timeline
        await event(self.db, app, "mobile_confirmed", actor="student", last4=mask(number)[-4:], changed=changed)

    async def decline(self, ctx: Context, reason: str | None) -> None:
        if not ctx.config.modes.allow_decline:
            # enforced here, not only in the page: a direct request cannot decline an offer the settings do not allow declining
            raise AuthorizationError("Declining the offer is not available on this page. Please contact the internship team.")
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
