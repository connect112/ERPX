"""
Taking and confirming payment for internship onboarding. One ledger for every method.

* Bank transfer / UPI: the student submits the transaction reference (UTR), date, amount and a proof. That is a claim,
  ``awaiting_verification``, never payment: a finance user confirms it after checking the money actually arrived. A
  reference can be live only once per organization (database constraint).
* Cashfree: the server creates the order for the amount owed; the student pays on the hosted checkout. Only a signed
  notification or a server-side status check whose order id, amount and currency match makes a payment confirmed. The
  browser's return to our page proves nothing and changes nothing.

When the confirmed total covers what is payable, the selection's existing ``payment_status`` becomes ``paid`` (the field
the manual process and the LMS grant already use). Confirmed money is never edited or deleted; corrections are new rows.
"""

import hashlib
import re
import secrets
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import User
from modules.internship_onboarding import fees as fee_maths
from modules.internship_onboarding import ledger, state
from modules.internship_onboarding.models import (
    OnboardingApplication,
    PaymentOrder,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from modules.internship_onboarding.financial import issue_safely
from modules.internship_onboarding.portal import CONTENT_TYPES, Context, sniff
from modules.internship_onboarding.providers import ProviderError, get_provider
from modules.internship_onboarding.service import (
    FINANCE_MANAGE,
    FINANCE_VIEW,
    ApplicationService,
    config_of,
    event,
    now,
    payment_deadline,
    require,
)
from modules.our_internships.models import InternshipSelection, OurInternship, PaymentStatus

logger = get_logger(__name__)

MAX_PROOF_BYTES = 5 * 1024 * 1024


def normalize_reference(reference: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", reference.upper())


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.apps = ApplicationService(db)

    # ---------------------------------------------------------------- shared

    async def _totals(self, application: OnboardingApplication, internship: OurInternship) -> ledger.Totals:
        _, config = await config_of(self.db, internship)
        return await ledger.totals(self.db, application, fee_maths.total_of(fee_maths.snapshot(config.fees)))

    async def settle(self, application: OnboardingApplication, user_id: uuid.UUID | None, reference: str | None = None) -> None:
        """Mark the selection paid once confirmed money covers what is owed. Never un-marks: refunds are handled by staff."""
        internship = await self.db.get(OurInternship, application.internship_id)
        selection = await self.db.get(InternshipSelection, application.selection_id)
        if internship is None or selection is None:
            return
        totals = await self._totals(application, internship)
        net = totals.paid - totals.refunded
        if net > 0 and totals.balance == 0 and selection.payment_status != PaymentStatus.PAID:
            selection.payment_status = PaymentStatus.PAID
            selection.payment_amount = net
            selection.payment_reference = (reference or application.reference)[:120]
            selection.payment_received_on = date.today()
            selection.payment_confirmed_at = now()
            selection.payment_confirmed_by_user_id = user_id
            await event(self.db, application, "payment_completed", actor="staff" if user_id else "system", user_id=user_id, amount=str(net))
        await self.db.flush()
        from modules.internship_onboarding.completion import check_and_queue

        await check_and_queue(self.db, application)

    async def _payable_now(self, ctx: Context) -> ledger.Totals:
        cfg = ctx.config
        if not cfg.modes.require_payment:
            raise ValidationError("No payment is needed for this internship.")
        f = await self.apps.facts(cfg, ctx.selection, ctx.application)
        if not state.payment_open(f):
            if state.payment_satisfied(f):
                raise ConflictError("Your payment is already complete.")
            if state.offer_status(f) != "accepted":
                raise ConflictError("Accept the offer before paying.")
            raise ConflictError("Payment opens once your documents are verified." if cfg.modes.payment_order == "after_document_approval" else "Submit your documents before paying.")
        until = payment_deadline(ctx.application, cfg)
        if until is not None and now() > until:
            raise ConflictError("The payment deadline has passed. Contact the internship team.")
        totals = await self._totals(ctx.application, ctx.internship)
        if totals.awaiting_manual:
            raise ConflictError("A payment you submitted is being checked. Wait for it before paying again.")
        if totals.balance <= 0:
            raise ConflictError("Your payment is already complete.")
        return totals

    # ---------------------------------------------------------------- bank transfer / UPI

    async def submit_claim(
        self, ctx: Context, method: str, reference: str, paid_on: date, amount: Decimal, remarks: str | None,
        proof_name: str, proof: bytes,
    ) -> PaymentTransaction:  # fmt: skip
        from packages.storage.client import get_storage_client

        if method not in ctx.config.fees.methods:
            raise ValidationError("That payment method is not available for this internship.")
        totals = await self._payable_now(ctx)
        amount = fee_maths.q(amount)
        if amount != totals.balance:
            raise ValidationError(f"Pay the full amount due: {ctx.config.fees.currency} {totals.balance}.")
        if paid_on > date.today() or paid_on < date.today() - timedelta(days=60):
            raise ValidationError("Enter the date you made the payment.")
        normalized = normalize_reference(reference)
        if len(normalized) < 6:
            raise ValidationError("Enter the full transaction reference (UTR).")
        if not proof or len(proof) > MAX_PROOF_BYTES:
            raise ValidationError("Attach the payment receipt or screenshot (up to 5 MB).")
        kind = sniff(proof)
        if kind is None:
            raise ValidationError("Attach the receipt as a PDF, JPG or PNG file.")
        key = f"onboarding/{ctx.application.organization_id}/{ctx.application.id}/payments/{uuid.uuid4().hex}.{kind}"
        claim = PaymentTransaction(
            organization_id=ctx.application.organization_id, application_id=ctx.application.id, kind="payment", method=method,
            amount=amount, currency=ctx.config.fees.currency, status="awaiting_verification", reference=reference.strip()[:120],
            reference_normalized=normalized[:120], paid_on=paid_on, proof_storage_key=key, proof_filename=f"payment-proof.{kind}",
            proof_content_type=CONTENT_TYPES[kind], proof_sha256=hashlib.sha256(proof).hexdigest(),
            remarks=(remarks or "").strip()[:1000] or None,
        )  # fmt: skip
        try:
            async with self.db.begin_nested():
                self.db.add(claim)
                await self.db.flush()
        except IntegrityError:
            raise ConflictError("This transaction reference has already been submitted.") from None
        await get_storage_client().upload_bytes(key, proof, CONTENT_TYPES[kind])
        await event(self.db, ctx.application, "payment_submitted", actor="student", method=method, amount=str(amount))
        return claim

    async def _transaction(self, internship: OurInternship, transaction_id: uuid.UUID) -> tuple[PaymentTransaction, OnboardingApplication]:
        row = (
            await self.db.execute(
                select(PaymentTransaction, OnboardingApplication)
                .join(OnboardingApplication, OnboardingApplication.id == PaymentTransaction.application_id)
                .where(PaymentTransaction.id == transaction_id, OnboardingApplication.internship_id == internship.id,
                       PaymentTransaction.organization_id == internship.organization_id)
                .with_for_update(of=PaymentTransaction)
            )
        ).first()  # fmt: skip
        if row is None:
            raise NotFoundError("Payment", transaction_id)
        return row[0], row[1]

    async def verify_claim(
        self, internship: OurInternship, transaction_id: uuid.UUID, approve: bool, amount_received: Decimal | None,
        note: str | None, user: User,
    ) -> PaymentTransaction:  # fmt: skip
        await require(self.db, user, FINANCE_MANAGE)
        claim, application = await self._transaction(internship, transaction_id)
        if claim.kind != "payment" or claim.status != "awaiting_verification":
            raise ConflictError("This payment is not waiting for verification.")
        claim.verified_by_user_id, claim.verified_at = user.id, now()
        if approve:
            received = fee_maths.q(amount_received) if amount_received is not None else claim.amount
            if received != claim.amount:
                if not (note or "").strip():
                    raise ValidationError("Explain why the amount received differs from the amount claimed.")
                claim.note = f"Claimed {claim.amount}, received {received}. {note.strip()}"
                claim.amount = received
            claim.status = "confirmed"
            await event(self.db, application, "payment_verified", user_id=user.id, amount=str(received), method=claim.method)
            await self.db.flush()
            await issue_safely(self.db, claim)
            await self.settle(application, user.id, claim.reference)
        else:
            if not (note or "").strip():
                raise ValidationError("Give the reason, so the student knows what to do.")
            claim.status = "rejected"
            claim.rejection_reason = note.strip()[:1000]
            await event(self.db, application, "payment_rejected", user_id=user.id, reason=claim.rejection_reason)
            await self.db.flush()
        return claim

    async def record_payment(
        self, internship: OurInternship, student_id: uuid.UUID, method: str, reference: str, paid_on: date,
        amount: Decimal, note: str, user: User,
    ) -> PaymentTransaction:  # fmt: skip
        """Staff record money they have already checked (the manual process, now in the ledger)."""
        await require(self.db, user, FINANCE_MANAGE)
        _, config = await config_of(self.db, internship)
        selection, _ = await self.apps.one(internship, student_id)
        application = await self.apps.ensure(internship, selection, config)
        row = PaymentTransaction(
            organization_id=internship.organization_id, application_id=application.id, kind="payment", method=method,
            amount=fee_maths.q(amount), currency=config.fees.currency, status="confirmed", reference=reference.strip()[:120],
            reference_normalized=normalize_reference(reference)[:120] or None, paid_on=paid_on, note=note.strip()[:1000],
            created_by_user_id=user.id, verified_by_user_id=user.id, verified_at=now(),
        )  # fmt: skip
        try:
            async with self.db.begin_nested():
                self.db.add(row)
                await self.db.flush()
        except IntegrityError:
            raise ConflictError("This transaction reference is already recorded.") from None
        await event(self.db, application, "payment_recorded", user_id=user.id, amount=str(row.amount), method=method)
        await issue_safely(self.db, row)
        await self.settle(application, user.id, row.reference)
        return row

    async def list_for_internship(self, internship: OurInternship, user: User, status: str | None) -> list[dict]:
        if not await _has_any(self.db, user):
            await require(self.db, user, FINANCE_VIEW)
        query = (
            select(PaymentTransaction, OnboardingApplication)
            .join(OnboardingApplication, OnboardingApplication.id == PaymentTransaction.application_id)
            .where(OnboardingApplication.internship_id == internship.id, PaymentTransaction.organization_id == internship.organization_id)
            .order_by(PaymentTransaction.created_at.desc())
        )
        if status:
            query = query.where(PaymentTransaction.status == status)
        out = []
        for t, a in (await self.db.execute(query)).all():
            duplicate_proof = False
            if t.proof_sha256:
                duplicate_proof = (await self.db.execute(
                    select(PaymentTransaction.id).where(PaymentTransaction.organization_id == t.organization_id,
                                                        PaymentTransaction.proof_sha256 == t.proof_sha256, PaymentTransaction.id != t.id).limit(1)
                )).first() is not None  # fmt: skip
            out.append({
                "id": t.id, "reference_number": a.reference, "selection_id": a.selection_id, "kind": t.kind, "method": t.method,
                "amount": str(t.amount), "currency": t.currency, "status": t.status, "transaction_reference": t.reference,
                "paid_on": t.paid_on, "remarks": t.remarks, "note": t.note, "rejection_reason": t.rejection_reason,
                "has_proof": bool(t.proof_storage_key), "same_proof_used_elsewhere": duplicate_proof,
                "created_at": t.created_at, "verified_at": t.verified_at,
            })  # fmt: skip
        return out

    async def proof_url(self, internship: OurInternship, transaction_id: uuid.UUID, user: User) -> str:
        from packages.storage.client import get_storage_client

        if not await _has_any(self.db, user):
            await require(self.db, user, FINANCE_VIEW)
        claim, _ = await self._transaction(internship, transaction_id)
        if not claim.proof_storage_key:
            raise NotFoundError("Payment proof", transaction_id)
        return get_storage_client().presigned_download_url(claim.proof_storage_key, expires=timedelta(minutes=3), download_name=claim.proof_filename)

    # ---------------------------------------------------------------- Cashfree

    async def start_checkout(self, ctx: Context) -> dict:
        if "cashfree" not in ctx.config.fees.methods:
            raise ValidationError("Online payment is not available for this internship.")
        totals = await self._payable_now(ctx)
        try:
            provider = get_provider("cashfree")
        except ProviderError as exc:
            raise ServiceUnavailableError(str(exc)) from None
        await self.db.execute(select(OnboardingApplication.id).where(OnboardingApplication.id == ctx.application.id).with_for_update())
        existing = (
            await self.db.execute(
                select(PaymentOrder).where(
                    PaymentOrder.application_id == ctx.application.id, PaymentOrder.method == "cashfree",
                    PaymentOrder.status == "active", PaymentOrder.amount == totals.balance,
                    PaymentOrder.expires_at > now() + timedelta(minutes=5),
                )
            )
        ).scalars().first()
        if existing is not None and existing.payment_session_id:
            return {"payment_session_id": existing.payment_session_id, "environment": provider.environment, "order_id": existing.merchant_order_id}
        merchant_order_id = f"ERPXI{secrets.token_hex(12).upper()}"
        expires = now() + timedelta(minutes=max(15, settings.CASHFREE_ORDER_MINUTES))
        order = PaymentOrder(
            organization_id=ctx.application.organization_id, application_id=ctx.application.id, method="cashfree",
            amount=totals.balance, currency=ctx.config.fees.currency, status="created", merchant_order_id=merchant_order_id,
            provider="cashfree", expires_at=expires,
        )  # fmt: skip
        self.db.add(order)
        await self.db.flush()
        try:
            created = await provider.create_order(
                merchant_order_id=merchant_order_id, amount=totals.balance, currency=order.currency,
                customer_id=ctx.application.reference, customer_name=ctx.student.name, customer_email=ctx.student.email,
                customer_phone=ctx.student.phone or "", return_url=f"{settings.FRONTEND_URL.rstrip('/')}/internship-onboarding?order={merchant_order_id}",
                expires_at=expires, note=f"{ctx.internship.title} - {ctx.application.reference}",
            )  # fmt: skip
        except ProviderError as exc:
            order.status = "failed"
            await self.db.flush()
            raise ServiceUnavailableError(str(exc)) from None
        order.status = "active"
        order.provider_order_id = created.provider_order_id
        order.payment_session_id = created.payment_session_id
        await event(self.db, ctx.application, "checkout_started", actor="student", amount=str(order.amount))
        await self.db.flush()
        return {"payment_session_id": created.payment_session_id, "environment": provider.environment, "order_id": merchant_order_id}

    async def apply_gateway_payment(self, order: PaymentOrder, payment, source: str) -> str:
        """Record what the gateway reports for one of our orders. Idempotent: the same gateway payment is recorded once,
        and a success is only accepted for the order's exact amount and currency."""
        application = await self.db.get(OnboardingApplication, order.application_id)
        if application is None:
            return "order without application"
        existing = (
            await self.db.execute(
                select(PaymentTransaction).where(PaymentTransaction.provider == "cashfree", PaymentTransaction.provider_payment_id == payment.provider_payment_id)
                .with_for_update()
            )
        ).scalar_one_or_none()  # fmt: skip
        if payment.status == "success":
            if payment.amount != order.amount or payment.currency != order.currency:
                await event(self.db, application, "payment_mismatch", actor="system", expected=str(order.amount), received=str(payment.amount), source=source)
                logger.warning("cashfree_amount_mismatch", order=order.merchant_order_id)
                return "amount mismatch: left for staff"
            if existing is not None and existing.status == "confirmed":
                return "already recorded"
            if existing is None:
                existing = PaymentTransaction(
                    organization_id=order.organization_id, application_id=order.application_id, order_id=order.id, kind="payment",
                    method="cashfree", amount=payment.amount, currency=payment.currency, provider="cashfree",
                    provider_payment_id=payment.provider_payment_id, reference=payment.provider_payment_id, status="confirmed",
                    paid_on=(payment.paid_at or now()).date(), verified_at=now(),
                )  # fmt: skip
                self.db.add(existing)
            else:
                existing.status, existing.verified_at = "confirmed", now()  # a failure we saw first was superseded by success
            order.status, order.paid_at = "paid", payment.paid_at or now()
            await self.db.flush()
            await event(self.db, application, "payment_confirmed", actor="system", amount=str(payment.amount), source=source)
            await issue_safely(self.db, existing)
            await self.settle(application, None, payment.provider_payment_id)
            return "confirmed"
        if payment.status == "failed":
            if existing is not None:
                return "already recorded"  # never let a late failure overwrite a recorded success
            self.db.add(PaymentTransaction(
                organization_id=order.organization_id, application_id=order.application_id, order_id=order.id, kind="payment",
                method="cashfree", amount=payment.amount if payment.amount > 0 else order.amount, currency=order.currency,
                provider="cashfree", provider_payment_id=payment.provider_payment_id, status="failed",
            ))  # fmt: skip
            if order.status == "active":
                order.status = "failed"
            await self.db.flush()
            await event(self.db, application, "payment_failed", actor="system", source=source)
            return "failed"
        return "pending"

    async def apply_gateway_refund(self, order: PaymentOrder, update, source: str) -> str:
        """Record what the gateway reports about one of our refunds (idempotent; amount must match)."""
        pending = (
            await self.db.execute(
                select(PaymentTransaction).where(PaymentTransaction.kind == "refund", PaymentTransaction.order_id == order.id,
                                                 PaymentTransaction.status == "pending").with_for_update()
            )
        ).scalars().all()  # fmt: skip
        match = next((r for r in pending if f"RF{r.id.hex[:30]}" == update.refund_id), None)
        if match is None:
            return "unknown refund"
        if update.amount != match.amount:
            return "refund amount mismatch: left for staff"
        application = await self.db.get(OnboardingApplication, match.application_id)
        if update.status == "success":
            await RefundService(self.db)._confirm(match, application, None)
            return "refund confirmed"
        if update.status == "failed":
            match.status, match.rejection_reason = "failed", f"The gateway reported the refund failed ({source})."
            await self.db.flush()
            await event(self.db, application, "refund_failed", actor="system")
            return "refund failed"
        return "refund pending"

    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        """(HTTP status, outcome). Bad signatures are refused and not processed; repeats are acknowledged and ignored."""
        try:
            provider = get_provider("cashfree")
        except ProviderError:
            return 503, "not configured"
        event_hash = hashlib.sha256(raw_body).hexdigest()
        if not provider.verify_webhook(raw_body, headers):
            logger.warning("cashfree_webhook_bad_signature")
            return 401, "invalid signature"
        seen = (await self.db.execute(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_hash == event_hash))).scalar_one_or_none()
        if seen is not None and seen.processed_at is not None:
            return 200, "duplicate"
        try:
            parsed = provider.parse_webhook(raw_body)
        except ProviderError:
            return 400, "unreadable"
        order = (
            await self.db.execute(select(PaymentOrder).where(PaymentOrder.merchant_order_id == parsed.merchant_order_id).with_for_update())
        ).scalar_one_or_none()
        record = seen or PaymentWebhookEvent(provider="cashfree", event_hash=event_hash, signature_valid=True)
        record.event_type, record.merchant_order_id = parsed.event_type, parsed.merchant_order_id[:64]
        if seen is None:
            self.db.add(record)
        if order is None:
            record.outcome, record.processed_at = "unknown order", now()
            await self.db.flush()
            return 200, "unknown order"
        record.organization_id = order.organization_id
        if parsed.refund is not None:
            outcome = await self.apply_gateway_refund(order, parsed.refund, "webhook")
        else:
            outcome = await self.apply_gateway_payment(order, parsed.payment, "webhook") if parsed.payment else "no payment"
        record.outcome, record.processed_at = outcome[:200], now()
        await self.db.flush()
        return 200, outcome

    async def refresh_order(self, order: PaymentOrder) -> str:
        """Ask the gateway directly (the student pressed "check payment", or the reconciliation task)."""
        provider = get_provider("cashfree")
        order.last_checked_at = now()
        outcome = "pending"
        for payment in await provider.order_payments(order.merchant_order_id):
            result = await self.apply_gateway_payment(order, payment, "status check")
            if result == "confirmed":
                outcome = result
        if outcome != "confirmed" and order.status == "active" and order.expires_at and order.expires_at < now():
            order.status = "expired"
        await self.db.flush()
        return outcome

    async def refresh_for_student(self, ctx: Context) -> str:
        orders = (
            await self.db.execute(
                select(PaymentOrder).where(PaymentOrder.application_id == ctx.application.id, PaymentOrder.method == "cashfree",
                                           PaymentOrder.status.in_(("active", "created", "failed")))
            )
        ).scalars().all()  # fmt: skip
        outcome = "nothing to check"
        for order in orders:
            try:
                result = await self.refresh_order(order)
            except ProviderError as exc:
                raise ServiceUnavailableError(str(exc)) from None
            if result == "confirmed":
                outcome = result
            elif outcome != "confirmed":
                outcome = result
        return outcome

    async def stale_orders(self, older_than: timedelta = timedelta(minutes=10), limit: int = 200) -> list[PaymentOrder]:
        cutoff = now() - older_than
        rows = await self.db.execute(
            select(PaymentOrder).where(
                PaymentOrder.method == "cashfree", PaymentOrder.status == "active", PaymentOrder.created_at < cutoff,
                (PaymentOrder.last_checked_at.is_(None)) | (PaymentOrder.last_checked_at < cutoff),
            ).limit(limit)
        )  # fmt: skip
        return list(rows.scalars())


async def _has_any(db: AsyncSession, user: User) -> bool:
    from modules.internship_onboarding.service import has

    return await has(db, user, FINANCE_VIEW) or await has(db, user, FINANCE_MANAGE)


# ------------------------------------------------------------------ refunds


class RefundService(PaymentService):
    """Money going back. Only finance staff ask for it; a refund never exceeds what is left of the payment it returns,
    original payments are never edited or deleted, and each confirmed refund gets a credit note."""

    async def refundable(self, payment: PaymentTransaction) -> Decimal:
        rows = (
            await self.db.execute(
                select(PaymentTransaction.amount).where(
                    PaymentTransaction.refund_of_id == payment.id, PaymentTransaction.status.in_(("pending", "awaiting_verification", "confirmed"))
                )
            )
        ).scalars().all()
        return fee_maths.q(payment.amount - sum(rows, Decimal("0")))

    async def request(
        self, internship: OurInternship, payment_id: uuid.UUID, amount: Decimal, reason: str, user: User,
    ) -> PaymentTransaction:  # fmt: skip
        await require(self.db, user, FINANCE_MANAGE)
        payment, application = await self._transaction(internship, payment_id)
        if payment.kind != "payment" or payment.status != "confirmed":
            raise ConflictError("Only a confirmed payment can be refunded.")
        if not reason.strip():
            raise ValidationError("Give the reason for the refund.")
        amount = fee_maths.q(amount)
        if amount <= 0 or amount > await self.refundable(payment):
            raise ValidationError(f"At most {payment.currency} {await self.refundable(payment)} of this payment can be refunded.")
        refund = PaymentTransaction(
            organization_id=payment.organization_id, application_id=payment.application_id, order_id=payment.order_id,
            kind="refund", method=payment.method, amount=amount, currency=payment.currency, refund_of_id=payment.id,
            status="awaiting_verification", note=reason.strip()[:1000], created_by_user_id=user.id,
        )  # fmt: skip
        self.db.add(refund)
        await self.db.flush()
        if payment.method == "cashfree" and payment.order_id:
            order = await self.db.get(PaymentOrder, payment.order_id)
            try:
                result = await get_provider("cashfree").create_refund(order.merchant_order_id, f"RF{refund.id.hex[:30]}", amount, reason.strip())
            except ProviderError as exc:
                refund.status, refund.rejection_reason = "failed", str(exc)[:500]
                await self.db.flush()
                raise ServiceUnavailableError(str(exc)) from None
            refund.provider, refund.provider_refund_id = "cashfree", result.provider_refund_id
            refund.status = "pending"
            await self.db.flush()
            if result.status == "success":
                await self._confirm(refund, application, None)
        await event(self.db, application, "refund_requested", user_id=user.id, amount=str(amount), reason=reason.strip()[:200])
        return refund

    async def _confirm(self, refund: PaymentTransaction, application: OnboardingApplication, user_id: uuid.UUID | None) -> None:
        """A refund finance agreed to also lowers what the student owes, except the part that only returns an overpayment;
        otherwise the student would be asked to pay the refunded money again."""
        internship = await self.db.get(OurInternship, application.internship_id)
        before = await self._totals(application, internship)
        overpaid = max(Decimal("0"), before.paid - before.refunded - before.payable)
        adjustment = fee_maths.q(max(Decimal("0"), refund.amount - overpaid))
        refund.status, refund.verified_at, refund.verified_by_user_id = "confirmed", now(), user_id
        if adjustment > 0:
            self.db.add(PaymentTransaction(
                organization_id=refund.organization_id, application_id=refund.application_id, kind="waiver", amount=adjustment,
                currency=refund.currency, status="confirmed", note="refund_adjustment", refund_of_id=refund.refund_of_id,
                created_by_user_id=user_id,
            ))  # fmt: skip
        await self.db.flush()
        await event(self.db, application, "refund_completed", actor="staff" if user_id else "system", user_id=user_id, amount=str(refund.amount))
        await issue_safely(self.db, refund)

    async def decide(
        self, internship: OurInternship, refund_id: uuid.UUID, approve: bool, reference: str | None, note: str | None, user: User,
    ) -> PaymentTransaction:  # fmt: skip
        """For a refund made by bank transfer/UPI: confirm once the money has been sent (with its reference), or cancel."""
        await require(self.db, user, FINANCE_MANAGE)
        refund, application = await self._transaction(internship, refund_id)
        if refund.kind != "refund" or refund.status != "awaiting_verification":
            raise ConflictError("This refund is not waiting for confirmation.")
        if approve:
            if not (reference or "").strip():
                raise ValidationError("Enter the reference of the transfer that returned the money.")
            refund.reference = reference.strip()[:120]
            refund.paid_on = date.today()
            await self._confirm(refund, application, user.id)
        else:
            if not (note or "").strip():
                raise ValidationError("Give the reason for cancelling the refund.")
            refund.status, refund.rejection_reason = "rejected", note.strip()[:1000]
            refund.verified_at, refund.verified_by_user_id = now(), user.id
            await self.db.flush()
            await event(self.db, application, "refund_cancelled", user_id=user.id, reason=refund.rejection_reason)
        return refund




async def cancel_application(db: AsyncSession, internship: OurInternship, student_id: uuid.UUID, reason: str, user: User) -> None:
    """Withdrawal or cancellation by staff. The link stops working; payments stay and are refunded separately if due."""
    if not reason.strip():
        raise ValidationError("Give the reason for cancelling.")
    apps = ApplicationService(db)
    selection, _ = await apps.one(internship, student_id)
    application = await apps.ensure(internship, selection)
    if application.cancelled_at is not None:
        raise ConflictError("This onboarding is already cancelled.")
    application.cancelled_at, application.cancel_reason = now(), reason.strip()[:1000]
    application.token_hash, application.token_revoked_at = None, now()
    await db.flush()
    await event(db, application, "onboarding_cancelled", user_id=user.id, reason=application.cancel_reason)

