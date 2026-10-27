"""
Draws an internship offer letter as a PDF from the generator's settings and one student's details.

Pure functions, no database. The text is real, selectable text in the PDF's own fonts (never an image of text); the logo,
watermark, signature and stamp are the images the admin uploaded, placed where the settings say. Content that does not fit on
two pages flows onto more pages, with the watermark and the footer on each, and a small header on the pages after the first.
"""

import io
from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from PIL import ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from modules.our_internships.letter_config import LetterConfig, fill, unprintable

MAX_ASSET_BYTES = 4 * 1024 * 1024
RASTER_TYPES = {"image/png": "PNG", "image/jpeg": "JPEG"}
SVG_TYPE = "image/svg+xml"
_FONTS = {
    "helvetica": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
    "times": ("Times-Roman", "Times-Bold", "Times-Italic"),
    "courier": ("Courier", "Courier-Bold", "Courier-Oblique"),
}
_MAX_PIXELS = {"logo": 900, "watermark": 1100, "signature": 700, "stamp": 600, "extra": 900}


class AssetError(ValueError):
    """An uploaded image that cannot be used. Shown to the admin as is."""


@dataclass(frozen=True)
class Asset:
    kind: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class StudentFacts:
    name: str
    institution: str
    location: str
    email: str
    registration_id: str = ""


# ------------------------------------------------------------------ images


def sniff_image(data: bytes) -> str:
    """The content type of an uploaded image by what it contains, or an AssetError."""
    if not data:
        raise AssetError("The file is empty.")
    if len(data) > MAX_ASSET_BYTES:
        raise AssetError("The image is larger than 4 MB.")
    head = data.lstrip()[:512].lower()
    if head.startswith(b"<svg") or (head.startswith((b"<?xml", b"<!doctype svg")) and b"<svg" in data[:4096].lower()):
        return SVG_TYPE
    try:
        with PILImage.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise AssetError("That file is not an image. Upload a PNG, JPG or SVG.") from exc
    if fmt == "PNG":
        return "image/png"
    if fmt in ("JPEG", "MPO"):
        return "image/jpeg"
    raise AssetError("Upload a PNG, JPG or SVG image.")


def _svg_drawing(data: bytes):
    try:
        from svglib.svglib import svg2rlg  # imported late: only SVG uploads need it
    except ImportError as exc:  # pragma: no cover - the dependency is part of the API image
        raise AssetError("SVG images are not supported on this server. Upload a PNG or JPG.") from exc
    try:
        drawing = svg2rlg(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - svglib raises many kinds of errors on bad input
        raise AssetError("That SVG could not be read. Export it again, or upload a PNG.") from exc
    if drawing is None or not getattr(drawing, "width", 0) or not getattr(drawing, "height", 0):
        raise AssetError("That SVG has no size. Export it again, or upload a PNG.")
    return drawing


def validate_asset(kind: str, data: bytes) -> str:
    content_type = sniff_image(data)
    if content_type == SVG_TYPE:
        _svg_drawing(data)
    return content_type


def _raster(asset: Asset, opacity: float | None = None) -> tuple[io.BytesIO, float]:
    """(image file, width/height). The image is shrunk to a sensible size, and made see-through when ``opacity`` is given."""
    with PILImage.open(io.BytesIO(asset.data)) as img:
        img = ImageOps.exif_transpose(img)
        limit = _MAX_PIXELS.get(asset.kind, 900)
        img.thumbnail((limit, limit))
        if opacity is None and img.mode in ("RGB", "L"):
            out = io.BytesIO()
            img.convert("RGB").save(out, "JPEG", quality=88)
        else:
            rgba = img.convert("RGBA")
            if opacity is not None:
                alpha = rgba.getchannel("A").point(lambda v: int(v * opacity))
                rgba.putalpha(alpha)
            out = io.BytesIO()
            rgba.save(out, "PNG")
        width, height = img.size
    out.seek(0)
    return out, width / height


def _fit(aspect: float, max_w: float, max_h: float) -> tuple[float, float]:
    width = max_w
    height = width / aspect
    if height > max_h:
        height, width = max_h, max_h * aspect
    return width, height


def _asset_flowable(asset: Asset, max_w: float, max_h: float, align: str):
    """The image as a flowable that fits inside the box, keeping its proportions."""
    if asset.content_type == SVG_TYPE:
        drawing = _svg_drawing(asset.data)
        w, h = _fit(drawing.width / drawing.height, max_w, max_h)
        drawing.scale(w / drawing.width, h / drawing.height)
        drawing.width, drawing.height = w, h
        drawing.hAlign = align.upper()
        return drawing
    reader, aspect = _raster(asset)
    w, h = _fit(aspect, max_w, max_h)
    image = Image(reader, width=w, height=h)
    image.hAlign = align.upper()
    return image


def _draw_asset(c, asset: Asset, x: float, y: float, w_max: float, h_max: float, opacity: float | None = None) -> None:
    """Draw the image with its lower-left corner at (x, y), inside the box, centred in it."""
    if asset.content_type == SVG_TYPE:
        from reportlab.graphics import renderPDF

        drawing = _svg_drawing(asset.data)
        w, h = _fit(drawing.width / drawing.height, w_max, h_max)
        drawing.scale(w / drawing.width, h / drawing.height)
        c.saveState()
        if opacity is not None:
            c.setFillAlpha(opacity)
            c.setStrokeAlpha(opacity)
        renderPDF.draw(drawing, c, x + (w_max - w) / 2, y + (h_max - h) / 2)
        c.restoreState()
        return
    buffer, aspect = _raster(asset, opacity)
    w, h = _fit(aspect, w_max, h_max)
    c.drawImage(ImageReader(buffer), x + (w_max - w) / 2, y + (h_max - h) / 2, w, h, mask="auto")


# ------------------------------------------------------------------ the words


def letter_values(config: LetterConfig, facts: StudentFacts, internship_title: str, reference: str, letter_date: str) -> dict[str, str]:
    p, c = config.programme, config.company

    def day(value: date | None) -> str:
        return value.strftime("%d-%m-%Y") if value else ""

    return {
        "student_name": facts.name,
        "institution_name": facts.institution,
        "institution_location": facts.location,
        "student_email": facts.email,
        "registration_id": facts.registration_id,
        "internship_name": p.name.strip() or internship_title,
        "internship_position": p.position,
        "internship_duration": p.duration,
        "internship_start_date": day(p.start_date),
        "internship_end_date": day(p.end_date),
        "program_type": "Paid Internship" if p.program_type == "paid" else "Unpaid Internship",
        "company_name": c.name,
        "authorized_signatory": c.signatory_name,
        "authorized_designation": c.signatory_designation,
        "reference": reference,
        "letter_date": letter_date,
    }


_REASONS = {
    "hackathon": "After reviewing your performance during our recent Hackathon, we believe you are a good fit for this opportunity.",
    "workshop": "After reviewing your performance during our recent Workshop, we believe you are a good fit for this opportunity.",
    "technical_evaluation": "After reviewing the results of your technical evaluation, we believe you are a good fit for this opportunity.",
    "direct_selection": "You have been selected by {{company_name}} for this opportunity.",
}


def introduction(config: LetterConfig) -> str:
    """The opening paragraph: the admin's own wording if given, otherwise written from the selection reason (no results invented)."""
    c = config.content
    if c.introduction.strip():
        return c.introduction.strip()
    offer = "We are pleased to offer you an internship position at {{company_name}}."
    if c.selection_reason == "custom":
        reason = c.custom_reason.strip()
    else:
        reason = _REASONS[c.selection_reason]
    return f"{offer} {reason}".strip()


def printable(text: str) -> str:
    """Text the built-in fonts can draw; anything else is dropped (checked and refused earlier, so this is only a safety net)."""
    bad = set(unprintable(text))
    return "".join(ch for ch in text if ch not in bad)


def _para(text: str) -> str:
    return escape(printable(text)).replace("\r", "").replace("\n", "<br/>")


# ------------------------------------------------------------------ the page


def _styles(config: LetterConfig) -> dict[str, ParagraphStyle]:
    b = config.branding
    regular, bold, italic = _FONTS[b.font_family]
    size = b.font_size
    lead = size * 1.4
    align = TA_JUSTIFY if b.text_align == "justify" else TA_LEFT
    brand = colors.HexColor(b.brand_color)
    body = ParagraphStyle("body", fontName=regular, fontSize=size, leading=lead, alignment=align, spaceAfter=size * 0.5)
    return {
        "body": body,
        "bold": ParagraphStyle("bold", parent=body, fontName=bold),
        "company": ParagraphStyle("company", parent=body, fontName=bold, fontSize=size + 4, leading=(size + 4) * 1.25, textColor=brand, alignment=1, spaceAfter=2),
        "contact": ParagraphStyle("contact", parent=body, fontSize=size - 0.5, leading=(size - 0.5) * 1.35, spaceAfter=0, alignment=1),
        "heading": ParagraphStyle(
            "heading", parent=body, fontName=bold, textColor=brand, spaceBefore=size * 0.6, spaceAfter=size * 0.35, leftIndent=15,
            bulletIndent=0, bulletFontName="ZapfDingbats", bulletFontSize=size - 2, keepWithNext=1,
        ),
        "plain_heading": ParagraphStyle("plain_heading", parent=body, fontName=bold, textColor=brand, spaceBefore=size * 0.8, spaceAfter=size * 0.4, keepWithNext=1),
        "bullet": ParagraphStyle("bullet", parent=body, leftIndent=28, bulletIndent=15, bulletFontName=regular, spaceAfter=size * 0.25),
        "sub": ParagraphStyle("sub", parent=body, leftIndent=44, bulletIndent=31, bulletFontName=regular, spaceAfter=size * 0.2),
        "small": ParagraphStyle("small", parent=body, fontName=italic, fontSize=size - 1, leading=(size - 1) * 1.35),
        "line": ParagraphStyle("line", parent=body, spaceAfter=0),
    }


def _header_story(config: LetterConfig, assets: dict[str, Asset], st: dict[str, ParagraphStyle]) -> list:
    b, c = config.branding, config.company
    story: list = []
    logo = assets.get("logo")
    if logo is not None and b.logo.show:
        story.append(_asset_flowable(logo, b.logo.width_mm * mm, b.logo.height_mm * mm, b.logo.position))
        story.append(Spacer(1, b.logo.spacing_mm * mm))
    align = {"left": 0, "center": 1, "right": 2}[b.logo.position if (logo is not None and b.logo.show) else "center"]
    company = ParagraphStyle("c", parent=st["company"], alignment=align)
    contact = ParagraphStyle("k", parent=st["contact"], alignment=align)
    if c.name.strip():
        story.append(Paragraph(_para(c.name), company))
    for line in (c.address, c.phone, c.email, c.website):
        if line.strip():
            story.append(Paragraph(_para(line), contact))
    story.append(Spacer(1, 7 * mm))
    return story


def _signature_row(config: LetterConfig, assets: dict[str, Asset]):
    b = config.branding
    parts: list = []
    sig = assets.get("signature")
    if sig is not None:
        parts.append(_asset_flowable(sig, b.signature.width_mm * mm, b.signature.height_mm * mm, "left"))
    stamp = assets.get("stamp")
    if stamp is not None and b.signature.show_stamp:
        parts.append(_asset_flowable(stamp, b.signature.stamp_size_mm * mm, b.signature.stamp_size_mm * mm, "left"))
    if not parts:
        return Spacer(1, 12 * mm)  # room to sign by hand
    widths = [(b.signature.width_mm + 6) * mm if i == 0 and sig is not None else (b.signature.stamp_size_mm + 4) * mm for i in range(len(parts))]
    table = Table([parts], colWidths=widths, hAlign=b.signature.position.upper())
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return table


def _sign_lines(config: LetterConfig, st: dict[str, ParagraphStyle], width: float):
    rows = [["Signature of Student:", "", "Date:", ""]]
    if config.content.guardian_required:
        rows.append(["Signature of Parent/Guardian:", "", "Date:", ""])
    label = 52 * mm
    date_label = 12 * mm
    date_line = 34 * mm
    line = width - label - date_label - date_line
    table = Table(
        [[Paragraph(r[0], st["line"]), "", Paragraph(r[2], st["line"]), ""] for r in rows],
        colWidths=[label, line, date_label, date_line],
        rowHeights=[14 * mm] * len(rows),
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LINEBELOW", (1, 0), (1, -1), 0.6, colors.black),
                ("LINEBELOW", (3, 0), (3, -1), 0.6, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _story(config: LetterConfig, facts: StudentFacts, assets: dict[str, Asset], values: dict[str, str], width: float) -> list:
    st = _styles(config)
    c, p = config.content, config.programme

    def f(text: str) -> str:
        return _para(fill(text, values))

    def bullet(text: str, style: str = "bullet", mark: str = "•") -> Paragraph:
        return Paragraph(f(text), st[style], bulletText=mark)

    def labelled(label: str, value: str, style: str = "bullet") -> Paragraph:
        return Paragraph(f"<b>{_para(label)}:</b> {f(value)}", st[style], bulletText="•")

    story: list = _header_story(config, assets, st)

    # recipient
    to = [Paragraph("<b>TO,</b>", st["line"]), Spacer(1, 2 * mm), Paragraph(f"<b>{_para(facts.name)}</b>", st["line"]), Paragraph(_para(facts.institution), st["line"]), Paragraph(_para(facts.location), st["line"])]
    if c.show_registration_id and facts.registration_id:
        to.append(Paragraph(f"Registration ID: {_para(facts.registration_id)}", st["line"]))
    story += [KeepTogether(to), Spacer(1, 5 * mm)]
    story.append(Paragraph(f"<b>Subject: {f(c.subject)}</b>", st["body"]))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph(f(introduction(config)), st["body"]))
    story.append(Paragraph("Below are the details of the internship:", st["body"]))

    # programme overview
    overview: list = [Paragraph("Internship Program Overview:", st["heading"], bulletText="➢")]
    overview.append(labelled("Position", p.position))
    if p.duration.strip():
        overview.append(labelled("Internship Duration", p.duration))
    for phase in p.phases:
        title = phase.title.strip()
        label = phase.label.strip()
        text = f"{label}: {title}" if label and title else label or title
        if text:
            overview.append(Paragraph(f(text), st["sub"], bulletText="–"))
    if p.start_date:
        overview.append(labelled("Start Date", values["internship_start_date"]))
    if p.end_date:
        overview.append(labelled("End Date", values["internship_end_date"]))
    overview.append(labelled("Program Type", values["program_type"]))
    if p.program_type == "paid" and p.stipend.strip():
        overview.append(labelled("Stipend", p.stipend))
    if p.description.strip():
        overview.append(labelled("About the program", p.description))
    story += overview

    # documentation and terms (a new page, like the reference letter, unless the admin turned that off)
    if c.start_documentation_on_new_page:
        story += [NextPageTemplate("later"), PageBreak()]
    else:
        story.append(CondPageBreak(60 * mm))
    if c.documents:
        story.append(Paragraph("Documentation:", st["heading"], bulletText="➢"))
        if c.documents_intro.strip():
            story.append(Paragraph(f(c.documents_intro), st["body"]))
        story += [bullet(d) for d in c.documents]
    if c.terms:
        story.append(Paragraph("Terms &amp; Conditions:", st["heading"], bulletText="➢"))
        story += [bullet(t) for t in c.terms]
    if c.confirmation.strip():
        story.append(Paragraph(f(c.confirmation), st["body"]))
    if c.closing.strip():
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f(c.closing), st["body"]))

    # authorised signatory
    signatory = [Paragraph("Sincerely,", st["body"]), _signature_row(config, assets)]
    comp = config.company
    sign_block = [Paragraph(f"<b>{_para(comp.signatory_name)}</b>", st["line"])]
    for line in (comp.signatory_designation, comp.name):
        if line.strip():
            sign_block.append(Paragraph(_para(line), st["line"]))
    story.append(KeepTogether(signatory + sign_block))

    # acceptance
    acceptance_text = f(c.acceptance)
    if c.guardian_required and c.guardian_acceptance.strip():
        acceptance_text += " " + f(c.guardian_acceptance)
    story.append(
        KeepTogether(
            [
                Spacer(1, 4 * mm),
                Paragraph("Acknowledgement and Acceptance", st["plain_heading"]),
                Paragraph(acceptance_text, st["body"]),
                _sign_lines(config, st, width),
            ]
        )
    )

    # notes
    notes: list[str] = [fill(n, values) for n in c.notes if n.strip()]
    fn = c.financial_note
    if fn.active:
        text = f"A fee of {fn.amount.strip()}"
        if fn.purpose.strip():
            text += f" applies for {fn.purpose.strip().rstrip('.')}"
        text += "."
        for extra in (fn.payment_conditions, fn.refund_terms):
            if extra.strip():
                text += " " + extra.strip().rstrip(".") + "."
        notes.insert(0, fill(text, values))
    if notes:
        block = [Paragraph("Note:", st["plain_heading"])] + [Paragraph(_para(n), st["body"]) for n in notes]
        story.append(KeepTogether(block))
    return story


def build_letter_pdf(
    config: LetterConfig,
    facts: StudentFacts,
    assets: dict[str, Asset],
    internship_title: str,
    reference: str,
    letter_date: str,
    title: str | None = None,
) -> tuple[bytes, int]:
    """(the PDF, its page count)."""
    b = config.branding
    values = letter_values(config, facts, internship_title, reference, letter_date)
    page_w, page_h = A4
    left, right = b.margin_left_mm * mm, b.margin_right_mm * mm
    top, bottom = b.margin_top_mm * mm, b.margin_bottom_mm * mm
    width = page_w - left - right
    regular, bold, _ = _FONTS[b.font_family]
    brand = colors.HexColor(b.brand_color)
    later_top = top + 16 * mm
    total_pages = [0]

    def background(c, doc) -> None:
        number = doc.page
        wm = assets.get("watermark")
        if wm is not None and b.watermark.show and (
            b.watermark.pages == "all"
            or (b.watermark.pages == "first" and number == 1)
            or (b.watermark.pages == "last" and number == (total_pages[0] or number))
        ):
            size = page_w * b.watermark.size_percent / 100
            cx = page_w / 2 + b.watermark.offset_x_mm * mm
            base = {"center": page_h / 2, "top": page_h - size / 2 - top, "bottom": size / 2 + bottom}[b.watermark.position]
            cy = base - b.watermark.offset_y_mm * mm
            _draw_asset(c, wm, cx - size / 2, cy - size / 2, size, size, b.watermark.opacity)
        if number > 1:  # a small header on the pages after the first
            y = page_h - top - 4 * mm
            logo = assets.get("logo")
            if logo is not None and b.logo.show:
                _draw_asset(c, logo, left, y - 6 * mm, 26 * mm, 11 * mm)
            c.setFillColor(brand)
            c.setFont(bold, b.font_size)
            c.drawRightString(page_w - right, y, printable(config.company.name))
            if b.header_text.strip():
                c.setFillColor(colors.HexColor("#555555"))
                c.setFont(regular, b.font_size - 2)
                c.drawRightString(page_w - right, y - 4.5 * mm, printable(fill(b.header_text, values)))
            c.setStrokeColor(brand)
            c.setLineWidth(0.5)
            c.line(left, page_h - top - 12 * mm, page_w - right, page_h - top - 12 * mm)
        # footer
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont(regular, 8)
        if b.footer_text.strip():
            c.drawCentredString(page_w / 2, bottom - 8 * mm, printable(fill(b.footer_text, values)))
        extra = assets.get("extra")
        if extra is not None and b.show_extra_image:
            _draw_asset(c, extra, left, bottom - 14 * mm, 22 * mm, 10 * mm)
        if b.show_page_numbers:
            of = f" of {total_pages[0]}" if total_pages[0] else ""
            c.drawRightString(page_w - right, bottom - 8 * mm, f"Page {number}{of}")

    def make(buffer: io.BytesIO) -> int:
        doc = BaseDocTemplate(
            buffer, pagesize=A4, leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom,
            title=printable(title or f"Internship offer letter - {facts.name}"), author=printable(config.company.name) or "ERPX",
            subject=printable(reference),
        )
        first = Frame(left, bottom, width, page_h - top - bottom, id="first", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        later = Frame(left, bottom, width, page_h - later_top - bottom, id="later", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates([PageTemplate(id="first", frames=[first], onPage=background), PageTemplate(id="later", frames=[later], onPage=background)])
        story = _story(config, facts, assets, values, width)
        # when the second page is not forced, content that spills over still needs the "later" page layout
        if not config.content.start_documentation_on_new_page:
            story.insert(0, NextPageTemplate("later"))
        doc.build(story)
        return doc.page

    scratch = io.BytesIO()
    total_pages[0] = make(scratch)  # first pass: how many pages (for "Page 1 of 2" and a "last page" watermark)
    out = io.BytesIO()
    pages = make(out)
    return out.getvalue(), pages
