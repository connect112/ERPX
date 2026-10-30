"""Internship onboarding: configuration rules, fee maths and the derived status machine. No database."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from modules.internship_onboarding import fees as fee
from modules.internship_onboarding import state
from modules.internship_onboarding.config import Fees, LateFee, OnboardingConfig, masked_accounts

NOW = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
BANK = {"holder": "GIR Technologies", "bank": "Test Bank", "account_number": "123456789012", "ifsc": "TEST0123456"}


def cfg(**over) -> dict:
    base = {
        "modes": {"mode": "automated", "require_payment": True},
        "fees": {"base_amount": "5000", "methods": ["bank_transfer"]},
        "deadlines": {"opens_at": "2026-11-01T00:00:00+05:30", "closes_at": "2026-11-15T23:59:00+05:30"},
        "payment_accounts": {"bank": BANK},
    }
    for k, v in over.items():
        base[k] = {**base.get(k, {}), **v} if isinstance(v, dict) else v
    return base


# ---------------------------------------------------------------- configuration


def test_a_complete_configuration_is_accepted_and_keeps_money_exact():
    c = OnboardingConfig.model_validate(cfg())
    assert c.fees.base_amount == Decimal("5000") and isinstance(c.fees.base_amount, Decimal)
    assert c.modes.self_service and [d.key for d in c.documents] == ["college_id", "signed_offer_letter"]
    # Aadhaar is not requested by default
    assert not any("aadhaar" in d.key for d in c.documents)


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"fees": {"base_amount": "0"}}, "fee is 0"),
        ({"fees": {"methods": []}}, "at least one payment method"),
        ({"fees": {"methods": ["upi"]}}, "UPI ID"),
        ({"payment_accounts": {"bank": None}}, "bank account"),
        ({"deadlines": {"closes_at": None}}, "closing date"),
        ({"deadlines": {"closes_at": "2026-10-01T00:00:00+05:30"}}, "close after it opens"),
        ({"deadlines": {"acceptance_deadline": "2026-12-01T00:00:00+05:30"}}, "on or before the closing"),
        ({"deadlines": {"closes_at": "2026-11-15T23:59:00"}}, "time zone offset"),
        ({"deadlines": {"timezone": "Mars/Base"}}, "Unknown time zone"),
        ({"modes": {"mode": "manual", "lms_access": "automatic"}}, "Automatic LMS access"),
        ({"modes": {"require_documents": False, "payment_order": "after_document_approval"}}, "document verification"),
        ({"fees": {"tax_mode": "exclusive", "tax_rate_percent": "0"}}, "tax rate"),
        ({"fees": {"tax_rate_percent": "18"}}, "tax treatment"),
        ({"fees": {"discount_amount": "6000"}}, "discount"),
        ({"fees": {"base_amount": "10.005"}}, "two decimal places"),
        ({"fees": {"base_amount": "-1"}}, "negative"),
        ({"communication": {"whatsapp_link": "https://evil.example/join"}}, "chat.whatsapp.com"),
        ({"documents": [{"key": "a", "label": "A"}, {"key": "a", "label": "B"}]}, "same key"),
        ({"form": [{"key": "x", "label": "X", "type": "dropdown", "options": ["only"]}]}, "two options"),
        ({"form": [{"key": "x", "label": "X", "type": "short_text", "visible_if": {"field": "nope", "equals": "y"}}]}, "does not exist"),
        ({"form": [{"key": "d", "label": "Declare", "type": "declaration"}]}, "must be required"),
        ({"fees": {"late_fee": {"mode": "percent", "value": "150"}}}, "100%"),
    ],
)
def test_contradictory_or_unsafe_configurations_are_refused(over, message):
    with pytest.raises(ValidationError, match=message):
        OnboardingConfig.model_validate(cfg(**over))


def test_unknown_settings_are_refused_rather_than_ignored():
    with pytest.raises(ValidationError):
        OnboardingConfig.model_validate({**cfg(), "run_this": "import os"})


def test_zero_fee_internships_need_no_gateway():
    c = OnboardingConfig.model_validate(cfg(modes={"require_payment": False}, fees={"base_amount": "0", "methods": []}))
    assert fee.snapshot(c.fees)["total"] == "0.00"


def test_account_numbers_are_masked_for_staff_without_finance_permission():
    assert masked_accounts({"bank": BANK})["bank"]["account_number"] == "••••••••9012"


# ---------------------------------------------------------------- fees


def test_exclusive_tax_is_added_and_rounded_half_up():
    s = fee.snapshot(Fees(base_amount=Decimal("999.99"), tax_mode="exclusive", tax_rate_percent=Decimal("18"), methods=["upi"]))
    assert (s["taxable"], s["tax"], s["total"]) == ("999.99", "180.00", "1179.99")


def test_inclusive_tax_is_split_out_of_the_price():
    s = fee.snapshot(Fees(base_amount=Decimal("1180"), tax_mode="inclusive", tax_rate_percent=Decimal("18")))
    assert (s["taxable"], s["tax"], s["total"]) == ("1000.00", "180.00", "1180.00")


def test_discounts_come_off_before_tax():
    s = fee.snapshot(Fees(base_amount=Decimal("5000"), discount_amount=Decimal("1000"), tax_mode="exclusive", tax_rate_percent=Decimal("18")))
    assert (s["taxable"], s["tax"], s["total"]) == ("4000.00", "720.00", "4720.00")


@pytest.mark.parametrize(
    ("late", "total", "expected"),
    [(LateFee(), "5000", "0.00"), (LateFee(mode="fixed", value=Decimal("500")), "5000", "500.00"),
     (LateFee(mode="percent", value=Decimal("2.5")), "4999.99", "125.00")],
)  # fmt: skip
def test_late_fees(late, total, expected):
    assert str(fee.late_fee_amount(late, Decimal(total))) == expected


# ---------------------------------------------------------------- derived status


def facts(**kw) -> state.Facts:
    return state.Facts(now=NOW, offer_delivery="sent", required_documents=("college_id", "signed_offer_letter"), **kw)


def test_a_new_invitation_has_not_started():
    f = facts(deadline=NOW + timedelta(days=3))
    assert (state.offer_status(f), state.overall_status(f)) == ("awaiting_response", "not_started")


def test_an_unanswered_offer_expires_exactly_after_the_deadline():
    assert state.offer_status(facts(deadline=NOW)) == "awaiting_response"  # at the deadline itself: still open
    f = facts(deadline=NOW - timedelta(seconds=1))
    assert (state.offer_status(f), state.overall_status(f)) == ("expired", "expired")


def test_an_accepted_offer_never_expires():
    f = facts(offer_response="accepted", deadline=NOW - timedelta(days=1))
    assert state.offer_status(f) == "accepted" and state.overall_status(f) == "awaiting_documents"


def test_document_status_follows_the_latest_version_of_each_required_document():
    assert state.document_status(facts(document_states={"college_id": "submitted"})) == "partially_submitted"
    both = {"college_id": "submitted", "signed_offer_letter": "submitted"}
    assert state.document_status(facts(document_states=both)) == "submitted"
    assert state.document_status(facts(document_states={**both, "college_id": "verified"})) == "under_review"
    assert state.document_status(facts(document_states={**both, "college_id": "rejected"})) == "changes_requested"
    assert state.document_status(facts(document_states={"college_id": "verified", "signed_offer_letter": "verified"})) == "verified"
    assert state.document_status(facts(manual_verification="verified")) == "verified"  # staff verified by hand


def test_payment_is_paid_only_when_the_confirmed_total_covers_what_is_payable():
    base = dict(require_payment=True, payable=Decimal("5000"))
    assert state.payment_status(facts(**base)) == "not_initiated"
    assert state.payment_status(facts(**base, open_order=True)) == "pending"
    assert state.payment_status(facts(**base, awaiting_manual=True)) == "awaiting_manual_verification"
    assert state.payment_status(facts(**base, paid=Decimal("2000"))) == "partially_paid"  # an installment is not "paid"
    assert state.payment_status(facts(**base, paid=Decimal("5000"))) == "paid"
    assert state.payment_status(facts(**base, paid=Decimal("5000"), refunded=Decimal("5000"))) == "refunded"
    assert state.payment_status(facts(**base, paid=Decimal("5000"), refunded=Decimal("1000"))) == "partially_refunded"
    assert state.payment_status(facts(**base, last_attempt_failed=True)) == "failed"
    assert state.payment_status(facts(require_payment=False)) == "not_required"


def test_completed_needs_acceptance_documents_and_payment():
    docs = {"college_id": "verified", "signed_offer_letter": "verified"}
    paid = dict(require_payment=True, payable=Decimal("100"), paid=Decimal("100"))
    assert state.overall_status(facts(offer_response="accepted", document_states=docs, **paid)) == "completed"
    # submitting a payment for checking is not completion
    pending = dict(require_payment=True, payable=Decimal("100"), awaiting_manual=True)
    assert state.overall_status(facts(offer_response="accepted", document_states=docs, **pending)) == "awaiting_manual_payment_approval"
    assert state.overall_status(facts(offer_response="declined")) == "cancelled"


def test_payment_order_modes():
    submitted = {"college_id": "submitted", "signed_offer_letter": "submitted"}
    owing = dict(offer_response="accepted", document_states=submitted, require_payment=True, payable=Decimal("100"))
    after_submission = facts(**owing)
    assert state.payment_open(after_submission) and state.overall_status(after_submission) == "awaiting_payment"
    after_approval = facts(**owing, payment_after_approval=True)
    assert not state.payment_open(after_approval) and state.overall_status(after_approval) == "awaiting_verification"


def test_payment_is_never_open_before_acceptance():
    f = facts(document_states={"college_id": "verified", "signed_offer_letter": "verified"}, require_payment=True, payable=Decimal("1"))
    assert not state.payment_open(f)
