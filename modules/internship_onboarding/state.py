"""
Where a student is in onboarding, derived (never stored) from the records that are authoritative for each part:

* offer      the selection's offer delivery + response (the response is the one source of truth, set by the student's
             action or by staff), and the effective deadline;
* documents  the latest version of each required document, or the selection's manual verification;
* payment    the ledger totals (what is payable, confirmed, refunded, waiting for a finance check), or the selection's
             manual "paid";
* overall    a fixed order over the three above.

Pure: callers gather ``Facts`` and call these functions, so the same answer shows in every screen, email and report.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

OFFER_STATUSES = ("not_issued", "delivery_pending", "delivery_failed", "awaiting_response", "accepted", "declined", "expired")
DOCUMENT_STATUSES = ("not_required", "not_submitted", "partially_submitted", "submitted", "under_review", "changes_requested", "verified", "rejected")
PAYMENT_STATUSES = (
    "not_required", "not_initiated", "pending", "awaiting_manual_verification", "paid", "failed", "partially_paid",
    "refunded", "partially_refunded",
)  # fmt: skip
OVERALL_STATUSES = (
    "not_started", "in_progress", "awaiting_acceptance", "awaiting_documents", "awaiting_verification", "awaiting_payment",
    "awaiting_manual_payment_approval", "completed", "expired", "cancelled",
)  # fmt: skip


@dataclass
class Facts:
    now: datetime
    # selection
    offer_delivery: str = "not_sent"  # not_sent | queued | sent | failed
    offer_response: str = "awaiting"  # awaiting | accepted | declined
    manual_verification: str = "pending"  # pending | verified | rejected
    manual_payment: str = "pending"  # pending | paid
    lms_status: str = "not_granted"
    # application
    started: bool = False
    cancelled: bool = False
    deadline: datetime | None = None
    # configuration
    require_documents: bool = True
    require_payment: bool = False
    payment_after_approval: bool = False
    # documents: required key -> status of its latest version (missing key = not submitted)
    required_documents: tuple[str, ...] = ()
    document_states: dict[str, str] = field(default_factory=dict)
    # ledger
    payable: Decimal = Decimal("0")
    paid: Decimal = Decimal("0")
    refunded: Decimal = Decimal("0")
    awaiting_manual: bool = False
    open_order: bool = False
    last_attempt_failed: bool = False


def offer_status(f: Facts) -> str:
    if f.offer_response == "accepted":
        return "accepted"
    if f.offer_response == "declined":
        return "declined"
    if f.offer_delivery == "not_sent":
        return "not_issued"
    if f.offer_delivery == "queued":
        return "delivery_pending"
    if f.offer_delivery == "failed":
        return "delivery_failed"
    if f.deadline is not None and f.now > f.deadline:
        return "expired"
    return "awaiting_response"


def document_status(f: Facts) -> str:
    if f.manual_verification == "verified":
        return "verified"
    if f.manual_verification == "rejected":
        return "rejected"
    if not f.require_documents or not f.required_documents:
        return "not_required"
    states = [f.document_states.get(k) for k in f.required_documents]
    if all(s is None for s in states):
        return "not_submitted"
    if any(s == "rejected" for s in states):
        return "changes_requested"
    if any(s is None for s in states):
        return "partially_submitted"
    if all(s == "verified" for s in states):
        return "verified"
    if any(s == "verified" for s in states):
        return "under_review"
    return "submitted"


def documents_satisfied(f: Facts) -> bool:
    return document_status(f) in ("verified", "not_required")


def documents_submitted(f: Facts) -> bool:
    return document_status(f) in ("submitted", "under_review", "verified", "not_required")


def payment_status(f: Facts) -> str:
    if f.manual_payment == "paid" and f.paid == 0:
        return "paid"  # confirmed by hand, as before the ledger existed
    if not f.require_payment or f.payable <= 0:
        if f.refunded > 0:
            return "refunded"
        return "not_required"
    net = f.paid - f.refunded
    if net >= f.payable:
        return "partially_refunded" if f.refunded > 0 else "paid"
    if f.refunded > 0:
        return "refunded" if net <= 0 else "partially_refunded"
    if f.awaiting_manual:
        return "awaiting_manual_verification"
    if net > 0:
        return "partially_paid"
    if f.open_order:
        return "pending"
    if f.last_attempt_failed:
        return "failed"
    return "not_initiated"


def payment_satisfied(f: Facts) -> bool:
    """What is owed is covered by what was received and kept (a refund agreed by finance also lowers what is owed)."""
    if f.manual_payment == "paid" and f.paid == 0:
        return True
    if not f.require_payment or f.payable <= 0:
        return True
    return f.paid - f.refunded >= f.payable


def payment_open(f: Facts) -> bool:
    """May the student pay now? Only after acceptance, and in 'after approval' mode only once documents are verified."""
    if offer_status(f) != "accepted" or payment_satisfied(f):
        return False
    if f.payment_after_approval:
        return documents_satisfied(f)
    return documents_submitted(f)


def overall_status(f: Facts) -> str:
    offer = offer_status(f)
    if f.cancelled or offer == "declined":
        return "cancelled"
    docs_ok, pay_ok = documents_satisfied(f), payment_satisfied(f)
    if offer == "accepted" and docs_ok and pay_ok:
        return "completed"
    if f.lms_status == "granted":
        return "completed"  # staff granted access by hand: the manual process said this student is done
    if offer == "expired":
        return "expired"
    if offer != "accepted":
        return "in_progress" if f.started else "not_started"
    docs = document_status(f)
    pay = payment_status(f)
    if docs in ("not_submitted", "partially_submitted", "changes_requested"):
        return "awaiting_documents"
    if pay == "awaiting_manual_verification":
        return "awaiting_manual_payment_approval"
    if not pay_ok and payment_open(f):
        return "awaiting_payment"
    if not docs_ok:
        return "awaiting_verification"
    return "awaiting_payment"
