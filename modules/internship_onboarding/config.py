"""
The onboarding settings of one internship (or of a reusable template): one validated document.

Pure: no database. ``OnboardingConfig.model_validate`` refuses contradictory settings with a message an administrator can
act on, so nothing inconsistent is ever stored. Money is ``Decimal`` throughout; the JSON form keeps amounts as strings.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Decimal
PaymentMethod = Literal["cashfree", "bank_transfer", "upi"]
FileType = Literal["pdf", "jpg", "png"]
FieldType = Literal["short_text", "long_text", "email", "phone", "number", "date", "dropdown", "radio", "checkbox", "multi_select", "declaration"]

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_DOCUMENT_MB = 15
WHATSAPP_PREFIX = "https://chat.whatsapp.com/"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _money(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("Amounts cannot be negative.")
    if value.as_tuple().exponent < -2:  # type: ignore[operator]
        raise ValueError("Amounts can have at most two decimal places.")
    if value > Decimal("10000000"):
        raise ValueError("That amount is too large.")
    return value


class Modes(_Strict):
    # automated: students onboard themselves through their link; manual: staff record everything (as before); hybrid: both.
    mode: Literal["manual", "automated", "hybrid"] = "manual"
    allow_info_edit: bool = False
    require_documents: bool = True
    require_payment: bool = False
    # after_submission: pay once documents are submitted; after_document_approval: pay only once they are verified.
    payment_order: Literal["after_submission", "after_document_approval"] = "after_submission"
    lms_access: Literal["manual", "automatic"] = "manual"
    allow_late_onboarding: bool = True
    reminders: bool = True
    invoice_emails: bool = True

    @property
    def self_service(self) -> bool:
        return self.mode in ("automated", "hybrid")


class LateFee(_Strict):
    mode: Literal["none", "fixed", "percent"] = "none"
    value: Money = Decimal("0")

    @field_validator("value")
    @classmethod
    def _value(cls, v: Decimal) -> Decimal:
        return _money(v)

    @model_validator(mode="after")
    def _check(self) -> "LateFee":
        if self.mode == "percent" and self.value > 100:
            raise ValueError("A percentage late fee cannot exceed 100%.")
        if self.mode != "none" and self.value == 0:
            raise ValueError("Enter the late fee, or switch it off.")
        return self


class Fees(_Strict):
    currency: Literal["INR"] = "INR"
    base_amount: Money = Decimal("0")
    description: str = Field(default="Internship programme fee", max_length=200)
    # none: no tax shown; inclusive: the base already includes it; exclusive: added on top.
    tax_mode: Literal["none", "inclusive", "exclusive"] = "none"
    tax_rate_percent: Money = Decimal("0")
    tax_label: str = Field(default="GST", max_length=20)
    discount_amount: Money = Decimal("0")
    late_fee: LateFee = LateFee()
    methods: list[PaymentMethod] = Field(default_factory=list)

    @field_validator("base_amount", "tax_rate_percent", "discount_amount")
    @classmethod
    def _amounts(cls, v: Decimal) -> Decimal:
        return _money(v)

    @field_validator("methods")
    @classmethod
    def _methods(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def _check(self) -> "Fees":
        if self.tax_mode == "none" and self.tax_rate_percent != 0:
            raise ValueError("Set a tax treatment for the tax rate, or set the rate to 0.")
        if self.tax_mode != "none" and not (0 < self.tax_rate_percent <= 50):
            raise ValueError("Enter a tax rate between 0 and 50%.")
        if self.discount_amount > self.base_amount:
            raise ValueError("The discount cannot be more than the fee.")
        return self


class Deadlines(_Strict):
    timezone: str = "Asia/Kolkata"
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    acceptance_deadline: datetime | None = None
    documents_deadline: datetime | None = None
    payment_deadline: datetime | None = None
    payment_grace_hours: int = Field(default=0, ge=0, le=24 * 30)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"Unknown time zone: {v}") from None
        return v

    @field_validator("opens_at", "closes_at", "acceptance_deadline", "documents_deadline", "payment_deadline")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("Dates and times must include a time zone offset.")
        return v

    @model_validator(mode="after")
    def _order(self) -> "Deadlines":
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValueError("Onboarding must close after it opens.")
        for name in ("acceptance_deadline", "documents_deadline"):
            value = getattr(self, name)
            if value and self.closes_at and value > self.closes_at:
                raise ValueError(f"The {name.replace('_', ' ')} must be on or before the closing date.")
            if value and self.opens_at and value <= self.opens_at:
                raise ValueError(f"The {name.replace('_', ' ')} must be after onboarding opens.")
        if self.payment_deadline and self.opens_at and self.payment_deadline <= self.opens_at:
            raise ValueError("The payment deadline must be after onboarding opens.")
        return self


class DocumentRequirement(_Strict):
    key: str
    label: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=1000)
    required: bool = True
    types: list[FileType] = Field(default_factory=lambda: ["pdf", "jpg", "png"], min_length=1)
    max_mb: int = Field(default=5, ge=1, le=MAX_DOCUMENT_MB)
    # Government identity documents: masked in lists, viewable only by reviewers, never emailed.
    sensitive: bool = False

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _KEY.match(v):
            raise ValueError("Keys use lower-case letters, digits and underscores, starting with a letter.")
        return v


class VisibleIf(_Strict):
    field: str
    equals: str | bool


class FormField(_Strict):
    key: str
    label: str = Field(min_length=1, max_length=200)
    type: FieldType
    description: str = Field(default="", max_length=500)
    placeholder: str = Field(default="", max_length=200)
    required: bool = False
    editable: bool = True
    options: list[str] = Field(default_factory=list, max_length=50)
    min_length: int | None = Field(default=None, ge=0, le=5000)
    max_length: int | None = Field(default=None, ge=1, le=5000)
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    default: str | bool | None = None
    visible_if: VisibleIf | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _KEY.match(v):
            raise ValueError("Keys use lower-case letters, digits and underscores, starting with a letter.")
        return v

    @model_validator(mode="after")
    def _check(self) -> "FormField":
        choice = self.type in ("dropdown", "radio", "multi_select")
        if choice and len([o for o in self.options if o.strip()]) < 2:
            raise ValueError(f'"{self.label}" needs at least two options.')
        if not choice and self.options:
            raise ValueError(f'"{self.label}" is not a choice field, so it takes no options.')
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError(f'"{self.label}": the minimum length is more than the maximum.')
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError(f'"{self.label}": the minimum is more than the maximum.')
        if self.type == "declaration" and not self.required:
            raise ValueError(f'"{self.label}": a declaration must be required.')
        return self


class Declaration(_Strict):
    text: str = Field(
        default=(
            "I confirm that the information and documents submitted are accurate. I accept the internship offer and agree "
            "to the applicable program terms, policies and payment amount displayed above."
        ),
        min_length=20,
        max_length=4000,
    )
    terms_version: str = Field(default="1", min_length=1, max_length=20)
    terms_url: str | None = Field(default=None, max_length=500)


class BankAccount(_Strict):
    holder: str = Field(min_length=1, max_length=120)
    bank: str = Field(min_length=1, max_length=120)
    account_number: str = Field(pattern=r"^[0-9]{6,20}$")
    ifsc: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    branch: str = Field(default="", max_length=120)
    instructions: str = Field(default="", max_length=1000)


class UpiAccount(_Strict):
    vpa: str = Field(pattern=r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z]{2,64}$")
    beneficiary: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=1000)


class PaymentAccounts(_Strict):
    bank: BankAccount | None = None
    upi: UpiAccount | None = None


class Issuer(_Strict):
    """Who issues receipts and invoices. A tax invoice needs a GSTIN; without one, documents are payment receipts."""

    legal_name: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=500)
    gstin: str | None = Field(default=None, pattern=r"^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]{3}$")
    receipt_prefix: str = Field(default="RCPT", pattern=r"^[A-Z][A-Z0-9-]{1,11}$")
    footer: str = Field(default="", max_length=500)


class Communication(_Strict):
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=30)
    whatsapp_link: str | None = Field(default=None, max_length=300)
    whatsapp_visibility: Literal["after_completion", "after_acceptance"] = "after_completion"
    reminder_days: list[int] = Field(default_factory=lambda: [7, 3, 1], max_length=10)
    next_steps: str = Field(default="", max_length=3000)

    @field_validator("whatsapp_link")
    @classmethod
    def _wa(cls, v: str | None) -> str | None:
        if v and not v.startswith(WHATSAPP_PREFIX):
            raise ValueError(f"The WhatsApp link must start with {WHATSAPP_PREFIX}")
        return v or None

    @field_validator("reminder_days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if any(d < 1 or d > 60 for d in v):
            raise ValueError("Reminders can be 1 to 60 days before closing.")
        return sorted(set(v), reverse=True)


class OnboardingConfig(_Strict):
    modes: Modes = Modes()
    fees: Fees = Fees()
    deadlines: Deadlines = Deadlines()
    documents: list[DocumentRequirement] = Field(
        default_factory=lambda: [
            DocumentRequirement(key="college_id", label="College ID card"),
            DocumentRequirement(key="signed_offer_letter", label="Signed offer letter", types=["pdf"]),
        ],
        max_length=20,
    )
    form: list[FormField] = Field(default_factory=list, max_length=60)
    declaration: Declaration = Declaration()
    payment_accounts: PaymentAccounts = PaymentAccounts()
    communication: Communication = Communication()
    issuer: Issuer = Issuer()
    reference_prefix: str = Field(default="ERPX-INT", pattern=r"^[A-Z][A-Z0-9-]{1,19}$")

    @model_validator(mode="after")
    def _consistent(self) -> "OnboardingConfig":
        keys = [d.key for d in self.documents]
        if len(keys) != len(set(keys)):
            raise ValueError("Two document requirements have the same key.")
        fkeys = [f.key for f in self.form]
        if len(fkeys) != len(set(fkeys)):
            raise ValueError("Two form fields have the same key.")
        for f in self.form:
            if f.visible_if and f.visible_if.field not in fkeys:
                raise ValueError(f'"{f.label}" depends on a field that does not exist.')
            if f.visible_if and f.visible_if.field == f.key:
                raise ValueError(f'"{f.label}" cannot depend on itself.')
        m, fees = self.modes, self.fees
        if m.require_documents and not self.documents:
            raise ValueError("Document verification is on, but no documents are requested.")
        if m.require_payment:
            if fees.base_amount == 0:
                raise ValueError("Payment is required, but the fee is 0. Set a fee or switch payment off.")
            if not fees.methods:
                raise ValueError("Payment is required: enable at least one payment method.")
        if m.payment_order == "after_document_approval" and m.require_payment and not m.require_documents:
            raise ValueError("Payment after document approval needs document verification switched on.")
        if "bank_transfer" in fees.methods and self.payment_accounts.bank is None:
            raise ValueError("Bank transfer is enabled: enter the bank account details.")
        if "upi" in fees.methods and self.payment_accounts.upi is None:
            raise ValueError("UPI is enabled: enter the UPI ID.")
        if m.self_service and self.deadlines.closes_at is None:
            raise ValueError("Students onboard themselves: set the onboarding closing date.")
        if self.issuer.gstin and self.fees.tax_mode == "none":
            raise ValueError("A GSTIN is set: choose the tax treatment of the fee.")
        if m.lms_access == "automatic" and m.mode == "manual":
            raise ValueError("Automatic LMS access needs automated or hybrid onboarding.")
        return self


FINANCE_SECTIONS = ("fees", "payment_accounts", "issuer")


def masked_accounts(accounts: dict) -> dict:
    """Payment-account details as shown to staff without the finance permission."""
    out = dict(accounts or {})
    bank = out.get("bank")
    if bank and bank.get("account_number"):
        out["bank"] = {**bank, "account_number": "•" * max(0, len(bank["account_number"]) - 4) + bank["account_number"][-4:]}
    return out
