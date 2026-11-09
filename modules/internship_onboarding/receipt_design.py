"""
The look of receipts, tax invoices and credit notes: one validated document, pure (no database).

What lives here is *presentation*: colours, alignment, which optional sections are shown, the images, the thank-you and footer
wording. The legal and financial identity of the issuer (legal name, address, GSTIN, receipt prefix) stays where it already is, in
the internship's onboarding settings (``config.issuer``, finance permission, versioned), and the amounts, tax lines and numbers
come from the verified payment. A design can therefore never change what a document legally says, only how it is laid out.

Every design is validated before it is stored. Text is plain text: it is escaped when drawn, never interpreted as markup.
"""

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
Align = Literal["left", "center", "right"]
ASSET_KINDS = ("logo", "signature", "stamp")
DEFAULT_THANK_YOU = "Thank you for your payment."
KINDS = ("receipt", "tax_invoice", "credit_note")
BODY_PARTS = ("details", "items", "thank_you", "signature")  # the blocks whose order can be changed (the totals always stay with the items)
MIN_CONTRAST = 3.0  # the brand colour is used for text on white, so it must be readable there

# a control character (other than a line break or tab) has no business in a receipt
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _luminance(hex_color: str) -> float:
    def channel(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_with_white(hex_color: str) -> float:
    return 1.05 / (_luminance(hex_color) + 0.05)


def _text(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("That text contains characters that cannot be printed.")
    return value.replace("\r\n", "\n").strip()


class Branding(_Strict):
    brand_color: str = "#1F3A5F"
    accent_color: str = "#E8EDF4"
    header_align: Align = "left"

    @field_validator("brand_color", "accent_color")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not HEX.match(v):
            raise ValueError("Use a colour like #1F3A5F.")
        return v.upper()

    @field_validator("brand_color")
    @classmethod
    def _readable(cls, v: str) -> str:
        if contrast_with_white(v) < MIN_CONTRAST:
            raise ValueError("The brand colour is too light to read on a white page. Choose a darker colour.")
        return v


class ImageSlot(_Strict):
    """A logo, signature or stamp: which uploaded image, and how big it may be drawn (the image keeps its proportions)."""

    show: bool = True
    asset_id: uuid.UUID | None = None
    align: Literal["auto", "left", "center", "right"] = "auto"  # "auto": follows the header alignment (the logo)
    width_mm: float = Field(default=40, ge=8, le=80)
    height_mm: float = Field(default=18, ge=6, le=40)


class Contacts(_Strict):
    """How the customer can reach the issuer. Display only; the legal identity is the issuer's settings."""

    website: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=30)

    @field_validator("website", "email", "phone")
    @classmethod
    def _plain(cls, v: str) -> str:
        v = _text(v)
        if "\n" in v:
            raise ValueError("Use a single line.")
        return v


class Sections(_Strict):
    """Optional parts of the page. The document title, number, date, issuer identity, customer name, amounts, tax lines, payment date,
    transaction reference and payment status are always shown: they are what makes it a financial document."""

    student_email: bool = True
    student_mobile: bool = False
    application_reference: bool = True
    programme: bool = True
    payment_method: bool = True
    issuer_contacts: bool = True
    issuer_address: bool = True
    thank_you: bool = True
    footer: bool = True


class Texts(_Strict):
    thank_you: str = Field(default=DEFAULT_THANK_YOU, max_length=300)
    footer: str = Field(default="", max_length=500)
    header_text: str = Field(default="", max_length=120)  # a line under the issuer's name (a tagline); the legal name itself is never replaced
    description_note: str = Field(default="", max_length=300)  # a note under the description line; the description itself is the accepted fee's
    terms: str = Field(default="", max_length=600)  # terms or a remark printed after the body

    @field_validator("thank_you", "footer", "header_text", "description_note", "terms")
    @classmethod
    def _plain(cls, v: str) -> str:
        return _text(v)


def _line(v: str) -> str:
    v = _text(v)
    if "\n" in v:
        raise ValueError("Use a single line.")
    return v


class Labels(_Strict):
    """Every fixed word on the document. Defaults are the wording used before the designer had these controls. What can never be set here:
    amounts, tax figures, transaction references, numbers and dates (they come from the verified records), and wording that would
    misrepresent which kind of document it is."""

    title_receipt: str = Field(default="PAYMENT RECEIPT", min_length=1, max_length=40)
    title_tax_invoice: str = Field(default="TAX INVOICE", min_length=1, max_length=40)
    title_credit_note: str = Field(default="CREDIT NOTE", min_length=1, max_length=40)
    subtitle_receipt: str = Field(default="", max_length=120)
    subtitle_tax_invoice: str = Field(default="", max_length=120)
    subtitle_credit_note: str = Field(default="", max_length=120)
    number: str = Field(default="No.", min_length=1, max_length=20)
    issue_date: str = Field(default="Date:", min_length=1, max_length=20)
    gstin: str = Field(default="GSTIN:", min_length=1, max_length=20)
    mobile: str = Field(default="Mobile:", min_length=1, max_length=20)
    billed_to: str = Field(default="BILLED TO", min_length=1, max_length=30)
    payment_details: str = Field(default="PAYMENT DETAILS", min_length=1, max_length=30)
    application: str = Field(default="Application", min_length=1, max_length=30)
    programme: str = Field(default="Programme", min_length=1, max_length=30)
    payment_method: str = Field(default="Payment method", min_length=1, max_length=30)
    transaction_ref: str = Field(default="Transaction ref.", min_length=1, max_length=30)
    payment_date: str = Field(default="Payment date", min_length=1, max_length=30)
    against: str = Field(default="Against", min_length=1, max_length=30)
    payment_status: str = Field(default="Payment status", min_length=1, max_length=30)
    col_description: str = Field(default="DESCRIPTION", min_length=1, max_length=30)
    col_amount: str = Field(default="AMOUNT", min_length=1, max_length=30)
    total_received: str = Field(default="Total received", min_length=1, max_length=40)
    total_refunded: str = Field(default="Total refunded", min_length=1, max_length=40)
    status_paid: str = Field(default="PAID", min_length=1, max_length=20)
    status_refunded: str = Field(default="REFUNDED", min_length=1, max_length=20)
    status_paid_word: str = Field(default="Paid", min_length=1, max_length=20)
    status_refunded_word: str = Field(default="Refunded", min_length=1, max_length=20)
    system_line: str = Field(default="This document was issued electronically and needs no signature.", min_length=1, max_length=200)
    page: str = Field(default="Page", min_length=1, max_length=20)

    @field_validator("*")
    @classmethod
    def _single_line(cls, v: str) -> str:
        return _line(v)

    @model_validator(mode="after")
    def _honest_titles(self) -> "Labels":
        """A document's title can be reworded but never made to say it is another kind of document."""
        low = {k: getattr(self, f"title_{k}").casefold() for k in KINDS}
        if "tax invoice" not in low["tax_invoice"] or "credit note" in low["tax_invoice"]:
            raise ValueError('The tax invoice title must contain "Tax Invoice" (and not "Credit Note").')
        if "credit note" not in low["credit_note"] or "invoice" in low["credit_note"]:
            raise ValueError('The credit note title must contain "Credit Note" (and not "Invoice").')
        if "invoice" in low["receipt"] or "credit note" in low["receipt"]:
            raise ValueError("The receipt title cannot call the document an invoice or a credit note.")
        if "refund" in (self.status_paid + self.status_paid_word).casefold() or "paid" in (self.status_refunded + self.status_refunded_word).casefold():
            raise ValueError("The status wording must not contradict the document: a payment is not shown as refunded, a refund not as paid.")
        return self

    def title(self, kind: str) -> str:
        return getattr(self, f"title_{kind}")

    def subtitle(self, kind: str) -> str:
        return getattr(self, f"subtitle_{kind}")


class Style(_Strict):
    """Typography and spacing. The defaults are the layout used before these controls existed."""

    body_size: float = Field(default=9, ge=8, le=12)
    title_size: float = Field(default=17, ge=12, le=30)
    issuer_size: float = Field(default=14, ge=10, le=22)
    section_gap_mm: float = Field(default=7, ge=4, le=14)
    margin_x_mm: float = Field(default=18, ge=12, le=25)
    table_borders: Literal["lines", "grid", "none"] = "lines"
    header_rule: bool = True


class ReceiptDesign(_Strict):
    branding: Branding = Branding()
    contacts: Contacts = Contacts()
    sections: Sections = Sections()
    texts: Texts = Texts()
    labels: Labels = Labels()
    style: Style = Style()
    logo: ImageSlot = ImageSlot()
    signature: ImageSlot = ImageSlot(width_mm=36, height_mm=14, show=False)
    stamp: ImageSlot = ImageSlot(width_mm=24, height_mm=24, show=False)
    signature_align: Align = "right"
    signatory_label: str = Field(default="Authorized signatory", max_length=60)
    body_order: list[Literal["details", "items", "thank_you", "signature"]] = Field(default_factory=lambda: list(BODY_PARTS))

    @field_validator("body_order")
    @classmethod
    def _order(cls, v: list[str]) -> list[str]:
        if sorted(v) != sorted(BODY_PARTS):
            raise ValueError("List each part once: details, items, thank_you and signature.")
        return v

    @field_validator("signatory_label")
    @classmethod
    def _label(cls, v: str) -> str:
        v = _text(v)
        if "\n" in v:
            raise ValueError("Use a single line.")
        return v

    def slots(self) -> dict[str, ImageSlot]:
        return {"logo": self.logo, "signature": self.signature, "stamp": self.stamp}

    def asset_ids(self) -> set[uuid.UUID]:
        return {slot.asset_id for slot in self.slots().values() if slot.asset_id is not None}


def default_design() -> ReceiptDesign:
    return ReceiptDesign()


def parse_design(data: dict | None) -> ReceiptDesign:
    """A stored or submitted design. Raises pydantic's ValidationError with a message the administrator can act on."""
    return ReceiptDesign.model_validate(data or {})


def dump(design: ReceiptDesign) -> dict:
    return design.model_dump(mode="json")


def first_error(exc) -> str:
    """One readable sentence from a pydantic ValidationError."""
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first.get("loc", ()))
    message = str(first.get("msg", "Invalid design.")).removeprefix("Value error, ")
    return f"{where}: {message}" if where else message
