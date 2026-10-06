"""
Admin-supplied certificate artwork, with each attendee's name printed on it.

The admin uploads the finished design *without* a name and says where the
name goes (centre point, font, size, colour); we stamp every attendee's
name there. Positions are fractions of the page so they survive the image
being re-encoded or shown at any size in the browser.
"""

import io
from datetime import datetime
from typing import Literal

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
# Longest side kept on file. Plenty for an A4 print, and keeps each of 200
# emailed PDFs under ~1 MB.
_MAX_SIDE_PX = 2600
_MAX_PIXELS = 36_000_000
_PAGE_LONG_SIDE_PT = 842.0  # A4 long edge

_FONTS = {
    "sans_bold": "Helvetica-Bold",
    "serif_bold": "Times-Bold",
    "serif_bold_italic": "Times-BoldItalic",
}


class CertificateLayout(BaseModel):
    name_x: float = Field(default=0.5, ge=0, le=1)  # horizontal centre, fraction of width
    name_y: float = Field(default=0.5, ge=0, le=1)  # text baseline, fraction of height from the top
    font_size: float = Field(default=0.07, ge=0.02, le=0.2)  # fraction of page height
    max_width: float = Field(default=0.7, ge=0.1, le=1)  # the name shrinks to fit this much of the width
    color: str = Field(default="#1f2937", pattern=r"^#[0-9a-fA-F]{6}$")
    font: Literal["sans_bold", "serif_bold", "serif_bold_italic"] = "sans_bold"
    # Off by default: a finished design rarely has room for it. When on, a
    # small certificate number + verification QR go in the bottom-right corner.
    show_verification: bool = False


class TemplateError(ValueError):
    """The uploaded file can't be used as a certificate template."""


def normalize_template(raw: bytes) -> tuple[bytes, int, int]:
    """Validate an uploaded image and return (jpeg_bytes, width_px, height_px)."""
    if not raw:
        raise TemplateError("The file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise TemplateError("The image is larger than 8 MB.")
    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        # Reject before decoding: a small file can inflate to gigabytes of pixels.
        if probe.width * probe.height > _MAX_PIXELS:
            raise TemplateError("That image is too large. Export it at a smaller size (under about 6000 x 6000).")
        probe.verify()
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise TemplateError("That isn't an image. Upload a PNG or JPG of the certificate.") from exc
    if fmt not in {"PNG", "JPEG"}:
        raise TemplateError("Upload the certificate as a PNG or JPG image.")

    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")

    scale = _MAX_SIDE_PX / max(image.size)
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue(), image.width, image.height


def _hex(color: str):
    return colors.HexColor(color)


def build_templated_certificate_pdf(
    *,
    template_jpeg: bytes,
    width_px: int,
    height_px: int,
    layout: CertificateLayout,
    attendee_name: str,
    certificate_number: str,
    verify_url: str,
) -> bytes:
    # Page keeps the artwork's own proportions, A4-sized along its long edge.
    if width_px >= height_px:
        page_w, page_h = _PAGE_LONG_SIDE_PT, _PAGE_LONG_SIDE_PT * height_px / width_px
    else:
        page_w, page_h = _PAGE_LONG_SIDE_PT * width_px / height_px, _PAGE_LONG_SIDE_PT

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setTitle(f"Certificate - {attendee_name}")
    c.drawImage(ImageReader(io.BytesIO(template_jpeg)), 0, 0, width=page_w, height=page_h)

    font = _FONTS[layout.font]
    size = layout.font_size * page_h
    limit = layout.max_width * page_w
    floor = size * 0.4
    while size > floor and c.stringWidth(attendee_name, font, size) > limit:
        size -= 0.5
    c.setFillColor(_hex(layout.color))
    c.setFont(font, size)
    c.drawCentredString(layout.name_x * page_w, page_h - layout.name_y * page_h, attendee_name)

    if layout.show_verification:
        margin = 0.025 * page_w
        qr_size = 0.09 * page_h
        qr_code = qr.QrCodeWidget(verify_url)
        x1, y1, x2, y2 = qr_code.getBounds()
        drawing = Drawing(qr_size, qr_size, transform=[qr_size / (x2 - x1), 0, 0, qr_size / (y2 - y1), 0, 0])
        drawing.add(qr_code)
        renderPDF.draw(drawing, c, page_w - margin - qr_size, margin + 9)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#374151"))
        c.drawRightString(page_w - margin, margin, f"Certificate No. {certificate_number}")

    c.showPage()
    c.save()
    return buffer.getvalue()


SAMPLE_NAME = "Sample Student Name"


def sample_certificate_pdf(template_jpeg: bytes, width_px: int, height_px: int, layout: CertificateLayout) -> bytes:
    number = f"WS-{datetime.now().year}-SAMPLE00"
    return build_templated_certificate_pdf(
        template_jpeg=template_jpeg,
        width_px=width_px,
        height_px=height_px,
        layout=layout,
        attendee_name=SAMPLE_NAME,
        certificate_number=number,
        verify_url=f"https://example.invalid/verify-workshop-certificate/{number}",
    )
