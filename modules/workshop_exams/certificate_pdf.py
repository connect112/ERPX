"""
Workshop participation certificate PDF.

A single landscape A4 page: company logo (when one is on file), the
heading, the attendee's name, a line of wording, the issue date, a unique
certificate number and a QR code that points at the public verification
page. Deliberately carries no signature or company seal image -- those
are only ever applied to documents their owner has explicitly approved.
"""

import io
import unicodedata
from datetime import datetime
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_LOGO_PATH = Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "static" / "payroll" / "logo.png"

_INK = colors.HexColor("#1f2937")
_ACCENT = colors.HexColor("#0f4c81")
_MUTED = colors.HexColor("#6b7280")


def printable_name(name: str) -> str:
    """A name the built-in PDF fonts can actually draw.

    Those fonts only cover Western European letters, so an accented Latin
    name is reduced to its plain letters (Srinivasa, not boxes) and anything
    still undrawable is dropped rather than printed as a missing-glyph box.
    """
    decomposed = unicodedata.normalize("NFKD", " ".join(name.split()))
    letters = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    safe = letters.encode("cp1252", errors="ignore").decode("cp1252")
    safe = "".join(ch for ch in safe if ch.isprintable())
    return " ".join(safe.split()) or "Participant"


def _fit_font_size(c: canvas.Canvas, text: str, font: str, start: float, max_width: float) -> float:
    size = start
    while size > 14 and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def build_certificate_pdf(
    *,
    attendee_name: str,
    heading: str,
    body_text: str,
    issuer_name: str,
    issued_on: datetime,
    certificate_number: str,
    verify_url: str,
) -> bytes:
    attendee_name = printable_name(attendee_name)
    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle(f"{heading} - {attendee_name}")

    # Double border.
    c.setStrokeColor(_ACCENT)
    c.setLineWidth(3)
    c.rect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm)
    c.setLineWidth(0.8)
    c.rect(14 * mm, 14 * mm, width - 28 * mm, height - 28 * mm)

    y = height - 34 * mm
    if _LOGO_PATH.exists():
        logo_h = 20 * mm
        c.drawImage(
            str(_LOGO_PATH), width / 2 - 30 * mm, y - logo_h + 6 * mm, width=60 * mm, height=logo_h,
            preserveAspectRatio=True, mask="auto", anchor="c",
        )
        y -= logo_h + 4 * mm
    else:
        c.setFillColor(_ACCENT)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, y, issuer_name.upper())
        y -= 12 * mm

    c.setFillColor(_ACCENT)
    heading_size = _fit_font_size(c, heading, "Helvetica-Bold", 34, width - 60 * mm)
    c.setFont("Helvetica-Bold", heading_size)
    c.drawCentredString(width / 2, y - 6 * mm, heading)
    y -= 22 * mm

    c.setFillColor(_MUTED)
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, y, "This is to certify that")
    y -= 18 * mm

    c.setFillColor(_INK)
    name_size = _fit_font_size(c, attendee_name, "Helvetica-Bold", 32, width - 70 * mm)
    c.setFont("Helvetica-Bold", name_size)
    c.drawCentredString(width / 2, y, attendee_name)
    c.setStrokeColor(_MUTED)
    c.setLineWidth(0.6)
    name_w = min(c.stringWidth(attendee_name, "Helvetica-Bold", name_size) + 20 * mm, width - 60 * mm)
    c.line(width / 2 - name_w / 2, y - 3 * mm, width / 2 + name_w / 2, y - 3 * mm)
    y -= 16 * mm

    c.setFillColor(_INK)
    c.setFont("Helvetica", 14)
    for line in _wrap(c, body_text, "Helvetica", 14, width - 90 * mm):
        c.drawCentredString(width / 2, y, line)
        y -= 7 * mm

    # Footer: date (left), QR + number (right), issuer (centre).
    base = 26 * mm
    c.setFillColor(_INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(28 * mm, base + 6 * mm, issued_on.strftime("%d %B %Y"))
    c.setFont("Helvetica", 9)
    c.setFillColor(_MUTED)
    c.drawString(28 * mm, base, "Date of issue")

    c.setFillColor(_INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, base + 6 * mm, issuer_name)
    c.setFont("Helvetica", 9)
    c.setFillColor(_MUTED)
    c.drawCentredString(width / 2, base, "Issued by")

    qr_code = qr.QrCodeWidget(verify_url)
    x1, y1, x2, y2 = qr_code.getBounds()
    size = 24 * mm
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(qr_code)
    renderPDF.draw(drawing, c, width - 28 * mm - size, base - 2 * mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(_MUTED)
    c.drawRightString(width - 28 * mm, base - 6 * mm, f"Certificate No. {certificate_number}")

    c.showPage()
    c.save()
    return buffer.getvalue()


def _wrap(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if c.stringWidth(trial, font, size) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines
