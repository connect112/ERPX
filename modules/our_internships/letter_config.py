"""
The offer letter generator's settings: company details, branding, the internship programme, the wording, and the email.

Pure functions and pydantic models, no database. The settings an organisation saves once are its defaults; an internship may
override any part of them. Both are stored as partial JSON, and the settings a letter is made from are the code defaults, then the
organisation's defaults, then the internship's overrides, merged key by key (lists and plain values are replaced as a whole).
"""

import hashlib
import json
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ------------------------------------------------------------------ placeholders

PLACEHOLDERS: dict[str, str] = {
    "student_name": "The student's full name",
    "institution_name": "The student's institution",
    "institution_location": "Where the institution is",
    "student_email": "The student's email address",
    "registration_id": "The student's registration or roll number (blank when we do not have one)",
    "internship_name": "The internship programme's name",
    "internship_position": "The position offered",
    "internship_duration": "The duration, for example 3 months",
    "internship_start_date": "The start date",
    "internship_end_date": "The end date",
    "program_type": "Paid or unpaid internship",
    "company_name": "The company's name",
    "authorized_signatory": "The authorised signatory's name",
    "authorized_designation": "The authorised signatory's designation",
    "reference": "The offer letter's reference number",
    "letter_date": "The date on the letter",
}
_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def unknown_placeholders(*texts: str | None) -> list[str]:
    found: list[str] = []
    for text in texts:
        for name in _PLACEHOLDER.findall(text or ""):
            if name not in PLACEHOLDERS and name not in found:
                found.append(name)
    return found


def fill(text: str, values: dict[str, str]) -> str:
    """The text with each {{placeholder}} replaced; an unknown one is left as written."""
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), text)


# ------------------------------------------------------------------ the settings

Alignment = Literal["left", "center", "right"]
HexColor = Field(default="#1f3a8a", pattern=r"^#[0-9a-fA-F]{6}$")


class CompanyInfo(BaseModel):
    name: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=200)
    signatory_name: str = Field(default="", max_length=200)
    signatory_designation: str = Field(default="", max_length=200)


class LogoStyle(BaseModel):
    show: bool = True
    position: Alignment = "center"
    width_mm: float = Field(default=45, ge=8, le=120)
    height_mm: float = Field(default=22, ge=5, le=60)  # the logo keeps its proportions inside this box
    spacing_mm: float = Field(default=3, ge=0, le=30)


class WatermarkStyle(BaseModel):
    show: bool = True
    size_percent: float = Field(default=75, ge=10, le=150)  # of the page width
    position: Literal["center", "top", "bottom"] = "center"
    offset_x_mm: float = Field(default=0, ge=-100, le=100)
    offset_y_mm: float = Field(default=0, ge=-150, le=150)
    opacity: float = Field(default=0.08, ge=0.02, le=0.4)
    pages: Literal["all", "first", "last"] = "all"


class SignatureStyle(BaseModel):
    width_mm: float = Field(default=42, ge=10, le=100)
    height_mm: float = Field(default=18, ge=6, le=50)
    position: Alignment = "left"
    show_stamp: bool = False
    stamp_size_mm: float = Field(default=26, ge=10, le=60)


class Branding(BaseModel):
    brand_color: str = HexColor
    font_family: Literal["helvetica", "times", "courier"] = "helvetica"
    font_size: float = Field(default=10.5, ge=8, le=14)
    text_align: Literal["left", "justify"] = "left"
    margin_top_mm: float = Field(default=16, ge=8, le=40)
    margin_bottom_mm: float = Field(default=18, ge=8, le=40)
    margin_left_mm: float = Field(default=20, ge=10, le=40)
    margin_right_mm: float = Field(default=20, ge=10, le=40)
    header_text: str = Field(default="", max_length=200)  # a line under the contact details on every page after the first
    footer_text: str = Field(default="", max_length=200)
    show_page_numbers: bool = True
    show_extra_image: bool = False  # the extra branding image, in the footer
    logo: LogoStyle = Field(default_factory=LogoStyle)
    watermark: WatermarkStyle = Field(default_factory=WatermarkStyle)
    signature: SignatureStyle = Field(default_factory=SignatureStyle)


class Phase(BaseModel):
    label: str = Field(default="", max_length=60)  # for example "Month 1"
    title: str = Field(default="", max_length=200)


class Programme(BaseModel):
    name: str = Field(default="", max_length=200)  # empty means the internship's own name
    position: str = Field(default="", max_length=200)
    duration: str = Field(default="", max_length=60)  # for example "3 months"
    start_date: date | None = None
    end_date: date | None = None
    program_type: Literal["unpaid", "paid"] = "unpaid"
    stipend: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    phases: list[Phase] = Field(default_factory=list, max_length=24)


SELECTION_REASONS = ("hackathon", "workshop", "technical_evaluation", "direct_selection", "custom")


class FinancialNote(BaseModel):
    """A fee the student is told about. Never printed unless it is switched on AND approved."""

    enabled: bool = False
    approved: bool = False
    amount: str = Field(default="", max_length=60)
    purpose: str = Field(default="", max_length=500)
    payment_conditions: str = Field(default="", max_length=500)
    refund_terms: str = Field(default="", max_length=500)

    @property
    def active(self) -> bool:
        return self.enabled and self.approved and bool(self.amount.strip())


class Content(BaseModel):
    subject: str = Field(default="Internship Offer Letter - {{company_name}}", max_length=250)
    selection_reason: Literal["hackathon", "workshop", "technical_evaluation", "direct_selection", "custom"] = "hackathon"
    custom_reason: str = Field(default="", max_length=600)
    introduction: str = Field(default="", max_length=2000)  # empty means the sentence written from the selection reason
    documents_intro: str = Field(default="Before the program starts, please submit the following:", max_length=300)
    documents: list[str] = Field(default_factory=list, max_length=20)
    terms: list[str] = Field(default_factory=list, max_length=30)
    confirmation: str = Field(
        default="By signing this offer letter, you confirm your participation in the program and agree to abide by the company's policies.",
        max_length=600,
    )
    closing: str = Field(
        default="We look forward to your confirmation and are excited to have you on board. Please do not hesitate to reach out to us if you need any further clarification.",
        max_length=1000,
    )
    acceptance: str = Field(
        default="I, {{student_name}}, hereby accept the internship offer from {{company_name}} and agree to the terms and conditions mentioned above.",
        max_length=800,
    )
    guardian_required: bool = False
    guardian_acceptance: str = Field(
        default="I have also obtained consent from my parents/guardians, and they have signed the offer letter.", max_length=400
    )
    show_registration_id: bool = False
    notes: list[str] = Field(default_factory=list, max_length=10)
    financial_note: FinancialNote = Field(default_factory=FinancialNote)
    start_documentation_on_new_page: bool = True
    letter_date: date | None = None  # empty means the day each letter is generated


class EmailSettings(BaseModel):
    subject: str = Field(default="Your internship offer letter - {{company_name}}", max_length=250)
    body: str = Field(
        default=(
            "Dear {{student_name}},\n\n"
            "Congratulations! We are pleased to offer you the position of {{internship_position}} on {{internship_name}} at {{company_name}}.\n\n"
            "Your offer letter (reference {{reference}}) is attached to this email. Please read it carefully, sign it, and send it back "
            "with the documents it lists. Reply to this email if you have any questions.\n\n"
            "We look forward to working with you.\n\n"
            "Regards,\n{{authorized_signatory}}\n{{authorized_designation}}, {{company_name}}"
        ),
        max_length=5000,
    )


class LetterConfig(BaseModel):
    company: CompanyInfo = Field(default_factory=CompanyInfo)
    branding: Branding = Field(default_factory=Branding)
    programme: Programme = Field(default_factory=Programme)
    content: Content = Field(default_factory=Content)
    email: EmailSettings = Field(default_factory=EmailSettings)

    @field_validator("programme")
    @classmethod
    def _dates_in_order(cls, value: Programme) -> Programme:
        if value.start_date and value.end_date and value.end_date < value.start_date:
            raise ValueError("The end date must not be before the start date.")
        return value

    @model_validator(mode="after")
    def _placeholders_are_known(self):
        c = self.content
        texts = [c.subject, c.introduction, c.documents_intro, c.confirmation, c.closing, c.acceptance, c.guardian_acceptance,
                 self.email.subject, self.email.body, self.branding.header_text, self.branding.footer_text, *c.documents, *c.terms, *c.notes,
                 c.financial_note.purpose, c.financial_note.payment_conditions, c.financial_note.refund_terms, self.programme.description]
        texts += [p.title for p in self.programme.phases]
        bad = unknown_placeholders(*texts)
        if bad:
            raise ValueError(
                "These placeholders are not recognised: " + ", ".join("{{" + b + "}}" for b in bad)
                + ". Use: " + ", ".join("{{" + k + "}}" for k in PLACEHOLDERS) + "."
            )
        return self


# ------------------------------------------------------------------ the starting point

DEFAULT_TERMS = [
    "You will be required to follow all company policies during your internship period.",
]
DEFAULT_DOCUMENTS = ["A signed copy of this offer letter", "College ID card copy", "Identity verification document"]


def code_defaults() -> dict[str, Any]:
    """What a brand-new organisation starts from: the wording of the reference letter, with nothing financial in it."""
    base = LetterConfig().model_dump(mode="json")
    base["content"]["documents"] = list(DEFAULT_DOCUMENTS)
    base["content"]["terms"] = list(DEFAULT_TERMS)
    base["programme"]["phases"] = []
    return base


# ------------------------------------------------------------------ merging and differences


def deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def difference(base: dict[str, Any], full: dict[str, Any]) -> dict[str, Any]:
    """The parts of ``full`` that differ from ``base`` (what an internship overrides)."""
    out: dict[str, Any] = {}
    for key, value in full.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested = difference(base[key], value)
            if nested:
                out[key] = nested
        elif base.get(key) != value:
            out[key] = value
    return out


def effective(default_json: dict[str, Any] | None, override_json: dict[str, Any] | None) -> LetterConfig:
    merged = deep_merge(deep_merge(code_defaults(), default_json or {}), override_json or {})
    return LetterConfig.model_validate(merged)


def config_hash(config: LetterConfig, asset_hashes: dict[str, str]) -> str:
    """Changes whenever anything that affects how a letter looks or reads changes."""
    payload = json.dumps([config.model_dump(mode="json"), sorted(asset_hashes.items())], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


# ------------------------------------------------------------------ what the letter text may contain

ASSET_KINDS = ("logo", "watermark", "signature", "stamp", "extra")
ASSET_LABELS = {
    "logo": "Company logo",
    "watermark": "Background watermark",
    "signature": "Authorised signature",
    "stamp": "Company stamp",
    "extra": "Additional branding image",
}


def unprintable(text: str) -> list[str]:
    """Characters the letter's built-in fonts cannot draw (they cover Western European languages)."""
    bad: list[str] = []
    for ch in text:
        if ch in "\n\r\t":
            continue
        try:
            ch.encode("cp1252")
        except UnicodeEncodeError:
            if ch not in bad:
                bad.append(ch)
    return bad


def check_printable(config: LetterConfig) -> list[str]:
    """Problems with characters in the text the admin wrote (empty when it can all be printed)."""
    data = config.model_dump(mode="json")
    problems: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            bad = unprintable(node)
            if bad:
                problems.append(f"{path} has characters the letter cannot print: {' '.join(bad)}")
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i + 1}]")

    walk(data, "")
    return problems


def program_problems(config: LetterConfig, internship_title: str) -> list[str]:
    """What must be filled in before any letter can be made (shown to the admin as a to-do list)."""
    problems: list[str] = []
    c, p = config.company, config.programme
    if not c.name.strip():
        problems.append("Enter the company name.")
    if not c.signatory_name.strip():
        problems.append("Enter the authorised signatory's name.")
    if not c.signatory_designation.strip():
        problems.append("Enter the authorised signatory's designation.")
    if not (p.name.strip() or internship_title.strip()):
        problems.append("Enter the internship programme name.")
    if not p.position.strip():
        problems.append("Enter the internship position.")
    if not p.duration.strip():
        problems.append("Enter the internship duration.")
    if p.start_date is None:
        problems.append("Enter the internship start date.")
    if p.end_date is None:
        problems.append("Enter the internship end date.")
    if p.program_type == "paid" and not p.stipend.strip():
        problems.append("This is a paid internship: enter the stipend details.")
    fn = config.content.financial_note
    if fn.enabled and not fn.approved:
        problems.append("The financial note is switched on but not approved, so it will not be printed. Approve it or switch it off.")
    if fn.enabled and fn.approved and not fn.amount.strip():
        problems.append("The financial note needs an amount.")
    problems += check_printable(config)
    return problems
