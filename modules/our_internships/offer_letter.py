"""
Offer letters: an uploaded PDF template with each student's details printed on it, and the email that carries it.

The admin uploads the finished letter (with the wording, signature and letterhead) as a PDF and says where each detail goes:
the student's name, the institution, the internship, the date and a reference number. Positions are fractions of the page so
they do not depend on the PDF's size. Each student's details are stamped on a transparent layer that is merged onto the
template, so everything else in the uploaded PDF is kept exactly as it was.

Pure functions, no database: the service decides who gets a letter and when.
"""

import io
import re
import unicodedata
from html import escape
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

MAX_TEMPLATE_BYTES = 10 * 1024 * 1024
MAX_PAGES = 10

FieldKey = Literal["name", "institution", "internship", "date", "reference"]
FIELD_LABELS: dict[str, str] = {
    "name": "Student's name",
    "institution": "Institution",
    "internship": "Internship name",
    "date": "Date",
    "reference": "Reference number",
}
FontKey = Literal["sans", "sans_bold", "serif", "serif_bold"]
_FONTS = {"sans": "Helvetica", "sans_bold": "Helvetica-Bold", "serif": "Times-Roman", "serif_bold": "Times-Bold"}
_MIN_FONT_PT = 6.0


class OfferField(BaseModel):
    key: FieldKey
    page: int = Field(default=1, ge=1, le=MAX_PAGES)
    x: float = Field(default=0.5, ge=0, le=1)  # where the text is anchored, fraction of the page width
    y: float = Field(default=0.5, ge=0, le=1)  # text baseline, fraction of the page height from the top
    font_size: float = Field(default=0.022, ge=0.008, le=0.08)  # fraction of the page height
    max_width: float = Field(default=0.5, ge=0.05, le=1)  # the text shrinks to fit this much of the width
    color: str = Field(default="#111827", pattern=r"^#[0-9a-fA-F]{6}$")
    font: FontKey = "sans_bold"
    align: Literal["left", "center", "right"] = "left"


class OfferLayout(BaseModel):
    fields: list[OfferField] = Field(default_factory=list, max_length=len(FIELD_LABELS))

    @field_validator("fields")
    @classmethod
    def _each_once(cls, value: list[OfferField]) -> list[OfferField]:
        keys = [f.key for f in value]
        if len(set(keys)) != len(keys):
            raise ValueError("Each detail can be placed only once.")
        return value

    @model_validator(mode="after")
    def _name_is_required(self):
        if self.fields and "name" not in {f.key for f in self.fields}:
            raise ValueError("Place the student's name on the letter.")
        return self


class TemplateError(ValueError):
    """The uploaded file cannot be used as an offer letter template. Shown to the admin as is."""


def inspect_template(raw: bytes) -> int:
    """Validate an uploaded PDF and return its page count."""
    if not raw:
        raise TemplateError("The file is empty.")
    if len(raw) > MAX_TEMPLATE_BYTES:
        raise TemplateError("The PDF is larger than 10 MB.")
    if not raw.lstrip().startswith(b"%PDF"):
        raise TemplateError("That is not a PDF. Export the offer letter as a PDF and upload that.")
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise TemplateError("That PDF is password protected. Remove the password and upload it again.")
        pages = len(reader.pages)
    except TemplateError:
        raise
    except (PdfReadError, ValueError, KeyError, OSError, RecursionError) as exc:
        raise TemplateError("That PDF could not be read. Try exporting it again.") from exc
    if pages < 1:
        raise TemplateError("That PDF has no pages.")
    if pages > MAX_PAGES:
        raise TemplateError(f"The letter can have at most {MAX_PAGES} pages.")
    return pages


def safe_text(value: str) -> str:
    """Text the built-in PDF fonts can draw: Western European letters, with accents reduced to plain letters."""
    decomposed = unicodedata.normalize("NFKD", " ".join(str(value).split()))
    letters = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    safe = letters.encode("cp1252", errors="ignore").decode("cp1252")
    return " ".join("".join(ch for ch in safe if ch.isprintable()).split())


def _fit(text: str, font: str, size: float, max_width: float) -> float:
    while size > _MIN_FONT_PT and pdfmetrics.stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def build_offer_pdf(template: bytes, layout: OfferLayout, values: dict[str, str]) -> bytes:
    """The template with ``values`` (keyed by field key) printed where the layout says. A field with no value is skipped."""
    reader = PdfReader(io.BytesIO(template))
    writer = PdfWriter()
    for number, page in enumerate(reader.pages, start=1):
        # a page the author rotated (a scanned landscape letter) is turned into upright content first, so that the
        # fractions in the layout mean the same thing as what is seen on the screen
        if page.rotation:
            page.transfer_rotation_to_content()
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        left, bottom = float(page.mediabox.left), float(page.mediabox.bottom)
        fields = [f for f in layout.fields if f.page == number and safe_text(values.get(f.key, ""))]
        if fields:
            layer = io.BytesIO()
            c = canvas.Canvas(layer, pagesize=(left + width, bottom + height))
            for f in fields:
                text = safe_text(values[f.key])
                font = _FONTS[f.font]
                size = _fit(text, font, f.font_size * height, f.max_width * width)
                c.setFont(font, size)
                c.setFillColor(colors.HexColor(f.color))
                x, y = left + f.x * width, bottom + height - f.y * height
                if f.align == "center":
                    c.drawCentredString(x, y, text)
                elif f.align == "right":
                    c.drawRightString(x, y, text)
                else:
                    c.drawString(x, y, text)
            c.save()
            layer.seek(0)
            page.merge_page(PdfReader(layer).pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ------------------------------------------------------------------ the email

PLACEHOLDERS: dict[str, str] = {
    "full_name": "The student's name",
    "internship_title": "The internship's name",
    "institution": "The student's institution",
    "reference": "The offer reference number",
}
_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")

DEFAULT_SUBJECT = "Your internship offer: {{internship_title}}"
DEFAULT_BODY = (
    "Dear {{full_name}},\n\n"
    "Congratulations! Based on your performance in our workshop and hackathon, we are pleased to offer you a place on "
    "{{internship_title}}.\n\n"
    "Your offer letter (reference {{reference}}) is attached to this email. Please read it carefully and reply to this "
    "email if you have any questions.\n\n"
    "We look forward to working with you.\n\n"
    "Regards,\nPentrix"
)


def unknown_placeholders(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for name in _PLACEHOLDER.findall(text or ""):
            if name not in PLACEHOLDERS and name not in found:
                found.append(name)
    return found


def fill(text: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def render_offer_email(subject: str | None, body: str | None, values: dict[str, str]) -> tuple[str, str, str]:
    """(subject, plain text, html) with the placeholders filled in. The subject is one line; the body keeps its paragraphs."""
    subject_text = " ".join(fill(subject or DEFAULT_SUBJECT, values).split())
    text = fill(body or DEFAULT_BODY, values).strip()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    html_body = "".join(f"<p style=\"margin:0 0 14px\">{escape(p.strip()).replace(chr(10), '<br>')}</p>" for p in paragraphs)
    html = f"<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:#1f2937\">{html_body}</div>"
    return subject_text, text, html


def attachment_name(full_name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in safe_text(full_name)).strip("_") or "student"
    return f"Internship_Offer_{safe}.pdf"
