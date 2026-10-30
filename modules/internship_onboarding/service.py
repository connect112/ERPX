"""
Staff side of internship onboarding: settings and their versions, templates, each student's application (reference and
link), individual reopening with a late fee, document review, and the dashboard.

Every change that matters is written to the student's timeline (``OnboardingEvent``) and, through the audit hooks, to
the audit trail. Raw link tokens exist only in memory: the database keeps their SHA-256.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.institutions.models import InstitutionStudent
from modules.internship_onboarding import fees as fee_maths
from modules.internship_onboarding import ledger, state
from modules.internship_onboarding.config import FINANCE_SECTIONS, OnboardingConfig, masked_accounts
from modules.internship_onboarding.models import (
    OnboardingApplication,
    OnboardingConfigRecord,
    OnboardingConfigVersion,
    OnboardingCounter,
    OnboardingDocument,
    OnboardingEvent,
    OnboardingTemplate,
    OnboardingTemplateVersion,
    PaymentTransaction,
)
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship, VerificationStatus

REVIEW = "our_internships.onboarding.review"
FINANCE_VIEW = "our_internships.finance.view"
FINANCE_MANAGE = "our_internships.finance.manage"
PREVIEW_MINUTES = 3


def now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def link_for(token: str) -> str:
    # In the fragment: browsers never send it to any server, so it cannot reach access logs, analytics or Referer headers.
    return f"{settings.FRONTEND_URL.rstrip('/')}/internship-onboarding#t={token}"


async def has(db: AsyncSession, user: User, code: str) -> bool:
    if user.is_superuser:
        return True
    return code in await AuthorizationRepository(db).get_permission_codes_for_user(user.id)


async def require(db: AsyncSession, user: User, code: str) -> None:
    if not await has(db, user, code):
        raise AuthorizationError(f"This action requires the following permission(s): {code}")


def parse_config(data: dict | None) -> OnboardingConfig:
    try:
        return OnboardingConfig.model_validate(data or {})
    except PydanticValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ()) if p != "__root__")
        message = str(first.get("msg", "Invalid settings.")).removeprefix("Value error, ")
        raise ValidationError(f"{where}: {message}" if where else message) from None


def dump(config: OnboardingConfig) -> dict:
    return config.model_dump(mode="json")


async def event(
    db: AsyncSession, application: OnboardingApplication, name: str, actor: str = "staff",
    user_id: uuid.UUID | None = None, **detail,
) -> None:
    db.add(OnboardingEvent(
        organization_id=application.organization_id, application_id=application.id, actor=actor,
        actor_user_id=user_id, event=name, detail={k: v for k, v in detail.items() if v is not None},
    ))  # fmt: skip


async def config_of(db: AsyncSession, internship: OurInternship) -> tuple[OnboardingConfigRecord | None, OnboardingConfig]:
    record = (
        await db.execute(select(OnboardingConfigRecord).where(OnboardingConfigRecord.internship_id == internship.id))
    ).scalar_one_or_none()
    return record, (parse_config(record.settings) if record else OnboardingConfig())


def effective_deadline(application: OnboardingApplication, config: OnboardingConfig) -> datetime | None:
    return application.deadline_override_at or config.deadlines.closes_at


def payment_deadline(application: OnboardingApplication, config: OnboardingConfig) -> datetime | None:
    if application.deadline_override_at:
        return application.deadline_override_at
    d = config.deadlines
    base = d.payment_deadline or d.closes_at
    return base + timedelta(hours=d.payment_grace_hours) if base else None


# ------------------------------------------------------------------ settings


class ConfigService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def view(self, internship: OurInternship, user: User) -> dict:
        record, config = await config_of(self.db, internship)
        data = dump(config)
        finance = await has(self.db, user, FINANCE_VIEW) or await has(self.db, user, FINANCE_MANAGE)
        if not finance:
            data["payment_accounts"] = masked_accounts(data["payment_accounts"])
        return {
            "settings": data,
            "version": record.version if record else 0,
            "template_id": record.template_id if record else None,
            "template_version": record.template_version if record else None,
            "can_edit_finance": await has(self.db, user, FINANCE_MANAGE),
            "fee_preview": fee_maths.snapshot(config.fees),
        }

    async def save(
        self, internship: OurInternship, user: User, data: dict,
        template: OnboardingTemplate | None = None,
    ) -> OnboardingConfigRecord:  # fmt: skip
        record, current = await config_of(self.db, internship)
        new = parse_config(data)
        before, after = dump(current), dump(new)
        if any(before[s] != after[s] for s in FINANCE_SECTIONS) and not await has(self.db, user, FINANCE_MANAGE):
            raise AuthorizationError(
                f"Changing fees or payment accounts requires the following permission(s): {FINANCE_MANAGE}"
            )
        if record is None:
            record = OnboardingConfigRecord(
                organization_id=internship.organization_id, internship_id=internship.id, version=1, settings=after,
                updated_by_user_id=user.id,
            )
            self.db.add(record)
        elif before == after and template is None:
            return record
        else:
            record.version += 1
            record.settings = after
            record.updated_by_user_id = user.id
        if template is not None:
            record.template_id, record.template_version = template.id, template.version
        await self.db.flush()
        self.db.add(OnboardingConfigVersion(
            organization_id=internship.organization_id, config_id=record.id, version=record.version, settings=after,
            created_by_user_id=user.id,
        ))  # fmt: skip
        await self.db.flush()
        return record

    async def versions(self, internship: OurInternship) -> list[OnboardingConfigVersion]:
        record, _ = await config_of(self.db, internship)
        if record is None:
            return []
        rows = await self.db.execute(
            select(OnboardingConfigVersion).where(OnboardingConfigVersion.config_id == record.id).order_by(OnboardingConfigVersion.version.desc())
        )
        return list(rows.scalars())


# ------------------------------------------------------------------ templates


class TemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, organization_id: uuid.UUID, template_id: uuid.UUID) -> OnboardingTemplate:
        row = (
            await self.db.execute(
                select(OnboardingTemplate).where(OnboardingTemplate.id == template_id, OnboardingTemplate.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Onboarding template", template_id)
        return row

    async def list(self, organization_id: uuid.UUID, include_archived: bool = False) -> list[OnboardingTemplate]:
        query = select(OnboardingTemplate).where(OnboardingTemplate.organization_id == organization_id).order_by(OnboardingTemplate.name)
        if not include_archived:
            query = query.where(OnboardingTemplate.archived.is_(False))
        return list((await self.db.execute(query)).scalars())

    async def _version(self, template: OnboardingTemplate, user: User) -> None:
        self.db.add(OnboardingTemplateVersion(
            organization_id=template.organization_id, template_id=template.id, version=template.version,
            settings=template.settings, created_by_user_id=user.id,
        ))  # fmt: skip
        await self.db.flush()

    async def _name_free(self, organization_id: uuid.UUID, name: str, except_id: uuid.UUID | None = None) -> None:
        query = select(OnboardingTemplate.id).where(OnboardingTemplate.organization_id == organization_id, func.lower(OnboardingTemplate.name) == name.lower())
        if except_id:
            query = query.where(OnboardingTemplate.id != except_id)
        if (await self.db.execute(query)).first():
            raise ConflictError("A template with that name already exists.")

    async def create(self, organization_id: uuid.UUID, user: User, name: str, description: str | None, data: dict) -> OnboardingTemplate:
        name = name.strip()
        if not name:
            raise ValidationError("Give the template a name.")
        await self._name_free(organization_id, name)
        template = OnboardingTemplate(
            organization_id=organization_id, name=name[:150], description=description, version=1,
            settings=dump(parse_config(data)), created_by_user_id=user.id,
        )
        self.db.add(template)
        await self.db.flush()
        await self._version(template, user)
        return template

    async def update(self, template: OnboardingTemplate, user: User, name: str | None, description: str | None, data: dict | None) -> OnboardingTemplate:
        if name is not None and name.strip() and name.strip() != template.name:
            await self._name_free(template.organization_id, name.strip(), template.id)
            template.name = name.strip()[:150]
        if description is not None:
            template.description = description
        if data is not None:
            new = dump(parse_config(data))
            if new != template.settings:
                template.settings = new
                template.version += 1
                await self.db.flush()
                await self._version(template, user)
        await self.db.flush()
        await self.db.refresh(template)  # updated_at is set by the database
        return template

    async def duplicate(self, template: OnboardingTemplate, user: User, name: str) -> OnboardingTemplate:
        return await self.create(template.organization_id, user, name, template.description, template.settings)

    async def archive(self, template: OnboardingTemplate, archived: bool) -> OnboardingTemplate:
        template.archived = archived
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def apply(self, template: OnboardingTemplate, internship: OurInternship, user: User) -> OnboardingConfigRecord:
        """Copy the template into the internship. Students who already accepted keep the terms and fee they accepted."""
        if template.archived:
            raise ValidationError("This template is archived.")
        if template.organization_id != internship.organization_id:
            raise NotFoundError("Onboarding template", template.id)
        return await ConfigService(self.db).save(internship, user, template.settings, template=template)


# ------------------------------------------------------------------ applications


@dataclass
class Issued:
    application: OnboardingApplication
    link: str


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _next_reference(self, organization_id: uuid.UUID, prefix: str) -> str:
        year = now().year
        from sqlalchemy.dialects.postgresql import insert

        await self.db.execute(
            insert(OnboardingCounter).values(organization_id=organization_id, year=year, last_value=0)
            .on_conflict_do_nothing(constraint="uq_onboarding_counter")
        )  # fmt: skip
        counter = (
            await self.db.execute(
                select(OnboardingCounter).where(OnboardingCounter.organization_id == organization_id, OnboardingCounter.year == year).with_for_update()
            )
        ).scalar_one()
        counter.last_value += 1
        await self.db.flush()
        return f"{prefix}-{year}-{counter.last_value:06d}"

    async def get_for_selection(self, selection_id: uuid.UUID) -> OnboardingApplication | None:
        return (
            await self.db.execute(select(OnboardingApplication).where(OnboardingApplication.selection_id == selection_id))
        ).scalar_one_or_none()

    async def ensure(self, internship: OurInternship, selection: InternshipSelection, config: OnboardingConfig | None = None) -> OnboardingApplication:
        """The student's one application, created on first need. Never two for one selection."""
        existing = await self.get_for_selection(selection.id)
        if existing is not None:
            return existing
        if config is None:
            _, config = await config_of(self.db, internship)
        reference = await self._next_reference(internship.organization_id, config.reference_prefix)
        try:
            async with self.db.begin_nested():
                application = OnboardingApplication(
                    organization_id=internship.organization_id, internship_id=internship.id, selection_id=selection.id,
                    reference=reference,
                )
                self.db.add(application)
                await self.db.flush()
        except IntegrityError:
            again = await self.get_for_selection(selection.id)
            if again is None:
                raise
            return again
        await event(self.db, application, "application_created", actor="system", reference=reference)
        return application

    async def issue_link(self, internship: OurInternship, selection: InternshipSelection, user_id: uuid.UUID | None, reason: str) -> Issued:
        """A new link for this student. Any earlier link stops working."""
        _, config = await config_of(self.db, internship)
        if not config.modes.self_service:
            raise ValidationError("Student self-service is off for this internship (manual onboarding).")
        application = await self.ensure(internship, selection, config)
        if application.cancelled_at is not None:
            raise ValidationError("This student's onboarding was cancelled.")
        token = secrets.token_urlsafe(32)
        application.token_hash = hash_token(token)
        application.token_issued_at = now()
        application.token_revoked_at = None
        await self.db.flush()
        await event(self.db, application, "link_issued", actor="staff" if user_id else "system", user_id=user_id, reason=reason)
        return Issued(application, link_for(token))

    async def revoke_link(self, application: OnboardingApplication, user_id: uuid.UUID) -> None:
        application.token_hash = None
        application.token_revoked_at = now()
        await self.db.flush()
        await event(self.db, application, "link_revoked", user_id=user_id)

    async def selections(self, internship: OurInternship, student_ids: list[uuid.UUID] | None = None) -> list[tuple[InternshipSelection, InstitutionStudent]]:
        query = (
            select(InternshipSelection, InstitutionStudent)
            .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .where(InternshipSelection.internship_id == internship.id, InstitutionStudent.organization_id == internship.organization_id)
            .order_by(InstitutionStudent.name)
        )
        if student_ids is not None:
            query = query.where(InternshipSelection.student_id.in_(list(dict.fromkeys(student_ids))))
        return [(s, st) for s, st in (await self.db.execute(query)).all()]

    async def one(self, internship: OurInternship, student_id: uuid.UUID) -> tuple[InternshipSelection, InstitutionStudent]:
        rows = await self.selections(internship, [student_id])
        if not rows:
            raise NotFoundError("Selected student", student_id)
        return rows[0]

    async def documents(self, application_id: uuid.UUID) -> list[OnboardingDocument]:
        rows = await self.db.execute(
            select(OnboardingDocument).where(OnboardingDocument.application_id == application_id)
            .order_by(OnboardingDocument.requirement_key, OnboardingDocument.version.desc())
        )  # fmt: skip
        return list(rows.scalars())

    @staticmethod
    def latest_states(documents: list[OnboardingDocument]) -> dict[str, str]:
        latest: dict[str, str] = {}
        for d in documents:  # newest version first per key
            if d.status != "superseded" and d.requirement_key not in latest:
                latest[d.requirement_key] = d.status
        return latest

    async def facts(
        self, config: OnboardingConfig, selection: InternshipSelection, application: OnboardingApplication | None,
        documents: list[OnboardingDocument] | None = None, totals: ledger.Totals | None = None,
    ) -> state.Facts:  # fmt: skip
        current_total = fee_maths.total_of(fee_maths.snapshot(config.fees))
        if application is not None and totals is None:
            totals = await ledger.totals(self.db, application, current_total)
        if application is not None and documents is None:
            documents = await self.documents(application.id)
        m = config.modes
        return state.Facts(
            now=now(),
            offer_delivery=selection.offer_status.value,
            offer_response=selection.offer_response.value,
            manual_verification=selection.verification_status.value,
            manual_payment=selection.payment_status.value,
            lms_status=selection.lms_status.value,
            started=bool(application and application.started_at),
            cancelled=bool(application and application.cancelled_at),
            deadline=effective_deadline(application, config) if application else config.deadlines.closes_at,
            require_documents=m.require_documents,
            require_payment=m.require_payment,
            payment_after_approval=m.payment_order == "after_document_approval",
            required_documents=tuple(d.key for d in config.documents if d.required),
            document_states=self.latest_states(documents or []),
            payable=totals.payable if totals else current_total,
            paid=totals.paid if totals else Decimal("0"),
            refunded=totals.refunded if totals else Decimal("0"),
            awaiting_manual=bool(totals and totals.awaiting_manual),
            open_order=bool(totals and totals.open_order),
            last_attempt_failed=bool(totals and totals.last_attempt_failed),
        )

    # ---------------------------------------------------------------- dashboard

    async def dashboard(self, internship: OurInternship) -> dict:
        _, config = await config_of(self.db, internship)
        rows = []
        metrics = {k: 0 for k in (
            "selected", "offers_released", "accepted", "declined", "not_started", "in_progress", "documents_to_review",
            "payments_to_verify", "payments_confirmed", "payments_failed", "reopened", "completed", "lms_granted",
        )}  # fmt: skip
        money = {"payable": Decimal("0"), "received": Decimal("0"), "outstanding": Decimal("0")}
        current_total = fee_maths.total_of(fee_maths.snapshot(config.fees))
        for selection, student in await self.selections(internship):
            application = await self.get_for_selection(selection.id)
            docs = await self.documents(application.id) if application else []
            totals = await ledger.totals(self.db, application, current_total) if application else None
            f = await self.facts(config, selection, application, docs, totals)
            row = {
                "student_id": student.id,
                "name": student.name,
                "email": student.email,
                "reference": application.reference if application else None,
                "offer_status": state.offer_status(f),
                "document_status": state.document_status(f),
                "payment_status": state.payment_status(f),
                "overall_status": state.overall_status(f),
                "lms_status": selection.lms_status.value,
                "deadline": f.deadline,
                "payable": str(f.payable) if config.modes.require_payment else "0.00",
                "received": str(totals.paid - totals.refunded) if totals else "0.00",
                "outstanding": str(totals.balance) if totals and config.modes.require_payment else "0.00",
                "reopened": bool(application and application.reopened_at),
                "last_activity_at": application.last_activity_at if application else None,
                "link_active": bool(application and application.token_hash),
                "documents_awaiting_review": sum(1 for d in docs if d.status == "submitted"),
            }
            rows.append(row)
            metrics["selected"] += 1
            metrics["offers_released"] += row["offer_status"] not in ("not_issued",)
            metrics["accepted"] += row["offer_status"] == "accepted"
            metrics["declined"] += row["offer_status"] == "declined"
            metrics["not_started"] += row["overall_status"] == "not_started"
            metrics["in_progress"] += row["overall_status"] not in ("not_started", "completed", "cancelled", "expired")
            metrics["documents_to_review"] += row["documents_awaiting_review"] > 0
            metrics["payments_to_verify"] += row["payment_status"] == "awaiting_manual_verification"
            metrics["payments_confirmed"] += row["payment_status"] == "paid"
            metrics["payments_failed"] += row["payment_status"] == "failed"
            metrics["reopened"] += row["reopened"]
            metrics["completed"] += row["overall_status"] == "completed"
            metrics["lms_granted"] += row["lms_status"] == "granted"
            if config.modes.require_payment and row["offer_status"] == "accepted":
                money["payable"] += Decimal(row["payable"])
                money["received"] += Decimal(row["received"])
                money["outstanding"] += Decimal(row["outstanding"])
        return {"rows": rows, "metrics": metrics, "money": {k: str(fee_maths.q(v)) for k, v in money.items()},
                "currency": config.fees.currency, "mode": config.modes.mode}  # fmt: skip

    async def detail(self, internship: OurInternship, student_id: uuid.UUID, user: User) -> dict:
        _, config = await config_of(self.db, internship)
        selection, student = await self.one(internship, student_id)
        application = await self.ensure(internship, selection, config)
        docs = await self.documents(application.id)
        f = await self.facts(config, selection, application, docs)
        events = (
            await self.db.execute(
                select(OnboardingEvent).where(OnboardingEvent.application_id == application.id).order_by(OnboardingEvent.created_at.desc()).limit(200)
            )
        ).scalars().all()
        finance = await has(self.db, user, FINANCE_VIEW) or await has(self.db, user, FINANCE_MANAGE)
        transactions = []
        if finance:
            transactions = (
                await self.db.execute(
                    select(PaymentTransaction).where(PaymentTransaction.application_id == application.id).order_by(PaymentTransaction.created_at.desc())
                )
            ).scalars().all()
        sensitive = {d.key for d in config.documents if d.sensitive}
        can_review = await has(self.db, user, REVIEW)
        return {
            "student": {"id": student.id, "name": student.name, "email": student.email, "phone": student.phone, "details": student.details},
            "reference": application.reference,
            "statuses": {
                "offer": state.offer_status(f), "documents": state.document_status(f), "payment": state.payment_status(f),
                "overall": state.overall_status(f), "lms": selection.lms_status.value,
            },
            "deadline": f.deadline,
            "link_active": bool(application.token_hash),
            "link_issued_at": application.token_issued_at,
            "started_at": application.started_at,
            "current_step": application.current_step,
            "info_original": application.info_original,
            "info_proposed": application.info_proposed,
            "info_review_status": application.info_review_status,
            "form_responses": application.form_responses,
            "acceptance": {
                "accepted_at": application.accepted_at, "declined_at": application.declined_at,
                "decline_reason": application.decline_reason, "terms_version": application.terms_version,
                "fee_snapshot": application.fee_snapshot, "config_version": application.config_version,
            },
            "reopened": {"at": application.reopened_at, "reason": application.reopen_reason, "until": application.deadline_override_at},
            "documents": [
                {
                    "id": d.id, "key": d.requirement_key, "version": d.version, "status": d.status,
                    "filename": d.filename if (can_review or d.requirement_key not in sensitive) else "(restricted)",
                    "size_bytes": d.size_bytes, "uploaded_at": d.created_at, "review_note": d.review_note,
                    "reviewed_at": d.reviewed_at, "sensitive": d.requirement_key in sensitive,
                }
                for d in docs
            ],
            "payments": [
                {
                    "id": t.id, "kind": t.kind, "method": t.method, "amount": str(t.amount), "currency": t.currency,
                    "status": t.status, "reference": t.reference, "paid_on": t.paid_on, "has_proof": bool(t.proof_storage_key),
                    "remarks": t.remarks, "note": t.note, "rejection_reason": t.rejection_reason, "created_at": t.created_at,
                    "verified_at": t.verified_at,
                }
                for t in transactions
            ] if finance else None,
            "events": [{"at": e.created_at, "actor": e.actor, "event": e.event, "detail": e.detail} for e in events],
        }  # fmt: skip

    # ---------------------------------------------------------------- reopening

    async def reopen(
        self, internship: OurInternship, student_ids: list[uuid.UUID], until: datetime, reason: str,
        late_fee: str, late_fee_amount: Decimal | None, user: User,
    ) -> dict:  # fmt: skip
        """Give individual students more time. late_fee: "none", "config" (the internship's late fee), "custom", or
        "waive" (remove a late fee charged earlier). Only one late fee is ever charged per student."""
        if until.tzinfo is None:
            raise ValidationError("The new deadline must include a time zone.")
        if until <= now():
            raise ValidationError("The new deadline must be in the future.")
        if not reason.strip():
            raise ValidationError("Give a reason for reopening.")
        if late_fee in ("config", "custom", "waive"):
            await require(self.db, user, FINANCE_MANAGE)
        _, config = await config_of(self.db, internship)
        if not config.modes.allow_late_onboarding:
            raise ValidationError("Late onboarding is switched off for this internship.")
        done, skipped = [], []
        for selection, student in await self.selections(internship, student_ids):
            application = await self.ensure(internship, selection, config)
            if selection.offer_response.value == "declined":
                skipped.append({"name": student.name, "reason": "Declined the offer; reopening needs the decline to be withdrawn first."})
                continue
            if application.cancelled_at is not None:
                skipped.append({"name": student.name, "reason": "Onboarding was cancelled."})
                continue
            application.deadline_override_at = until
            application.reopened_at = now()
            application.reopened_by_user_id = user.id
            application.reopen_reason = reason.strip()
            existing = await ledger.late_fee_charge(self.db, application.id)
            charged = None
            if late_fee in ("config", "custom") and existing is None:
                base = fee_maths.total_of(application.fee_snapshot) or fee_maths.total_of(fee_maths.snapshot(config.fees))
                amount = fee_maths.q(late_fee_amount) if late_fee == "custom" and late_fee_amount is not None else fee_maths.late_fee_amount(config.fees.late_fee, base)
                if amount > 0:
                    self.db.add(PaymentTransaction(
                        organization_id=application.organization_id, application_id=application.id, kind="charge", amount=amount,
                        currency=config.fees.currency, status="confirmed", note="late_fee", created_by_user_id=user.id,
                    ))  # fmt: skip
                    charged = str(amount)
            elif late_fee == "waive" and existing is not None:
                waived = (
                    await self.db.execute(
                        select(PaymentTransaction.id).where(
                            PaymentTransaction.application_id == application.id, PaymentTransaction.kind == "waiver",
                            PaymentTransaction.note == "late_fee", PaymentTransaction.status == "confirmed",
                        )
                    )
                ).first()
                if waived is None:
                    self.db.add(PaymentTransaction(
                        organization_id=application.organization_id, application_id=application.id, kind="waiver",
                        amount=existing.amount, currency=existing.currency, status="confirmed", note="late_fee", created_by_user_id=user.id,
                    ))  # fmt: skip
                    charged = f"-{existing.amount}"
            await event(self.db, application, "reopened", user_id=user.id, until=until.isoformat(), reason=reason.strip(), late_fee=charged)
            done.append(student.id)
        await self.db.flush()
        return {"reopened": len(done), "skipped": skipped}

    # ---------------------------------------------------------------- document review

    async def document(self, internship: OurInternship, document_id: uuid.UUID) -> tuple[OnboardingDocument, OnboardingApplication]:
        row = (
            await self.db.execute(
                select(OnboardingDocument, OnboardingApplication)
                .join(OnboardingApplication, OnboardingApplication.id == OnboardingDocument.application_id)
                .where(OnboardingDocument.id == document_id, OnboardingApplication.internship_id == internship.id,
                       OnboardingDocument.organization_id == internship.organization_id)
            )
        ).first()  # fmt: skip
        if row is None:
            raise NotFoundError("Document", document_id)
        return row[0], row[1]

    async def preview_url(self, internship: OurInternship, document_id: uuid.UUID, user: User) -> str:
        from packages.storage.client import get_storage_client

        await require(self.db, user, REVIEW)
        document, application = await self.document(internship, document_id)
        await event(self.db, application, "document_viewed", user_id=user.id, document=document.requirement_key, version=document.version)
        await self.db.flush()
        return get_storage_client().presigned_download_url(
            document.storage_key, expires=timedelta(minutes=PREVIEW_MINUTES), download_name=document.filename
        )

    async def review(self, internship: OurInternship, document_id: uuid.UUID, approve: bool, note: str | None, user: User) -> OnboardingDocument:
        await require(self.db, user, REVIEW)
        document, application = await self.document(internship, document_id)
        if document.status == "superseded":
            raise ConflictError("A newer version of this document has been uploaded; review that one.")
        if not approve and not (note or "").strip():
            raise ValidationError("Say what needs to change, so the student can fix it.")
        selection = await self.db.get(InternshipSelection, application.selection_id)
        if not approve and selection is not None and selection.lms_status == LmsStatus.GRANTED:
            raise ConflictError("This student already has LMS access. Revoke it before asking for documents again.")
        document.status = "verified" if approve else "rejected"
        document.reviewed_by_user_id = user.id
        document.reviewed_at = now()
        document.review_note = (note or "").strip() or None
        await self.db.flush()
        await event(self.db, application, "document_verified" if approve else "document_rejected", user_id=user.id,
                    document=document.requirement_key, version=document.version, note=document.review_note)  # fmt: skip
        await self.sync_verification(internship, application, selection, user.id)
        return document

    async def sync_verification(
        self, internship: OurInternship, application: OnboardingApplication, selection: InternshipSelection | None, user_id: uuid.UUID | None,
    ) -> None:  # fmt: skip
        """Keep the selection's verification (the LMS gate the manual process uses) in step with the documents."""
        if selection is None:
            return
        _, config = await config_of(self.db, internship)
        if not config.modes.require_documents:
            return
        latest = self.latest_states(await self.documents(application.id))
        required = [d.key for d in config.documents if d.required]
        if required and all(latest.get(k) == "verified" for k in required):
            if selection.verification_status != VerificationStatus.VERIFIED:
                selection.verification_status = VerificationStatus.VERIFIED
                selection.verified_at, selection.verified_by_user_id = now(), user_id
        elif selection.verification_status == VerificationStatus.VERIFIED and any(latest.get(k) == "rejected" for k in required):
            selection.verification_status = VerificationStatus.PENDING
            selection.verified_at, selection.verified_by_user_id = None, None
        await self.db.flush()

    async def review_info(self, internship: OurInternship, student_id: uuid.UUID, approve: bool, user: User) -> None:
        """Apply (or turn down) the corrections a student proposed. Never automatic; email is not changed this way."""
        selection, student = await self.one(internship, student_id)
        application = await self.ensure(internship, selection)
        if application.info_review_status != "pending":
            raise ValidationError("There are no proposed changes to review.")
        if approve:
            proposed = application.info_proposed or {}
            if proposed.get("name"):
                student.name = proposed["name"][:255]
            if "phone" in proposed:
                student.phone = (proposed["phone"] or None) and proposed["phone"][:50]
            extra = {k: v for k, v in (proposed.get("details") or {}).items() if isinstance(v, str)}
            if extra:
                student.details = {**(student.details or {}), **{k: v[:255] for k, v in extra.items()}}
        application.info_review_status = "approved" if approve else "rejected"
        await self.db.flush()
        await event(self.db, application, "info_changes_approved" if approve else "info_changes_rejected", user_id=user.id)
