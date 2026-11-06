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

from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
Align = Literal["left", "center", "right"]
ASSET_KINDS = ("logo", "signature", "stamp")
DEFAULT_THANK_YOU = "Thank you for your payment."
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
    thank_you: bool = True
    footer: bool = True


class Texts(_Strict):
    thank_you: str = Field(default=DEFAULT_THANK_YOU, max_length=300)
    footer: str = Field(default="", max_length=500)

    @field_validator("thank_you", "footer")
    @classmethod
    def _plain(cls, v: str) -> str:
        return _text(v)


class ReceiptDesign(_Strict):
    branding: Branding = Branding()
    contacts: Contacts = Contacts()
    sections: Sections = Sections()
    texts: Texts = Texts()
    logo: ImageSlot = ImageSlot()
    signature: ImageSlot = ImageSlot(width_mm=36, height_mm=14, show=False)
    stamp: ImageSlot = ImageSlot(width_mm=24, height_mm=24, show=False)
    signatory_label: str = Field(default="Authorized signatory", max_length=60)

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
