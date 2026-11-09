"""
Draws a payment receipt, tax invoice or credit note as a PDF from its stored details and a validated design. Pure: no database,
no network, nothing is stored or sent here.

* A4, real selectable text in an embedded Unicode font (DejaVu Sans, which has the rupee sign), never an image of text.
* A normal document fits one page. The footer and page number are drawn on every page in a reserved band, so they can never
  spill onto a page of their own; an unusually long document continues on further pages (with a small running header) instead of
  being cut or shrunk.
* The numbers (amounts, tax, dates, references, document number) come from ``details`` (fixed when the document was issued) and can
  never be set by a design. The design chooses the wording around them (labels, titles), colours, typography, spacing, section order,
  which optional sections show, and the images. Text is escaped, never interpreted as markup.
* ``watermark`` marks a preview or sample on every page; an official document has none.
"""

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from modules.internship_onboarding.receipt_design import ReceiptDesign

FONT_DIR = Path(__file__).resolve().parent / "fonts"
REGULAR, BOLD = "ERPXSans", "ERPXSans-Bold"
TITLES = {"receipt": "PAYMENT RECEIPT", "tax_invoice": "TAX INVOICE", "credit_note": "CREDIT NOTE"}
STATUS = {"receipt": "PAID", "tax_invoice": "PAID", "credit_note": "REFUNDED"}
SYSTEM_LINE = "This document was issued electronically and needs no signature."
GREY, DARK = colors.HexColor("#6B7280"), colors.HexColor("#111827")
CREDIT = colors.HexColor("#9B1C1C")  # credit notes are marked apart from receipts and invoices
MARGIN_TOP, MARGIN_BOTTOM = 16 * mm, 32 * mm  # the bottom band holds the footer on every page (the side margins are the design's)
RUPEE = "₹"

_fonts_ready = False


@dataclass(frozen=True)
class Image_:
    """An image to draw (already normalized when it was uploaded)."""

    data: bytes
    content_type: str = "image/png"


def _ensure_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD)
    _fonts_ready = True


def printable(text: object) -> str:
    """The text with every character the font cannot draw removed (never a blank box in the PDF)."""
    _ensure_fonts()
    face = pdfmetrics.getFont(REGULAR).face
    return "".join(ch for ch in str(text or "") if ch in "\n\t" or ord(ch) in face.charToGlyph)


def _p(text: object) -> str:
    return escape(printable(text)).replace("\r", "").replace("\n", "<br/>")


def money(value: object, currency: str) -> str:
    amount = f"{Decimal(str(value)):,.2f}"
    return f"{RUPEE} {amount}" if currency == "INR" else f"{currency} {amount}"


def day(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return date.fromisoformat(iso[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(iso)


def _styles(brand: colors.Color, st) -> dict[str, ParagraphStyle]:
    """Paragraph styles from the design's typography (the defaults are the sizes used before the designer had these controls)."""
    b = st.body_size
    base = ParagraphStyle("base", fontName=REGULAR, fontSize=b, leading=b * 1.39, textColor=DARK)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=b - 1, leading=(b - 1) * 1.375, textColor=GREY),
        "label": ParagraphStyle("label", parent=base, fontSize=b - 1.5, leading=(b - 1.5) * 1.33, textColor=GREY, fontName=BOLD),
        "issuer": ParagraphStyle("issuer", parent=base, fontName=BOLD, fontSize=st.issuer_size, leading=st.issuer_size * 1.29, textColor=brand),
        "title": ParagraphStyle("title", parent=base, fontName=BOLD, fontSize=st.title_size, leading=st.title_size * 1.24, textColor=brand),
        "bold": ParagraphStyle("bold", parent=base, fontName=BOLD),
        "name": ParagraphStyle("name", parent=base, fontName=BOLD, fontSize=b + 1.5, leading=(b + 1.5) * 1.33),
        "head": ParagraphStyle("head", parent=base, fontName=BOLD, textColor=brand),
        "total_label": ParagraphStyle("total_label", parent=base, fontName=BOLD, fontSize=b + 1.5, leading=(b + 1.5) * 1.33),
        "thanks": ParagraphStyle("thanks", parent=base, fontSize=b + 0.5, leading=(b + 0.5) * 1.42),
    }


def _aligned(style: ParagraphStyle, align: str) -> ParagraphStyle:
    code = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}[align]
    return ParagraphStyle(f"{style.name}_{align}", parent=style, alignment=code)


def _image(img: Image_, max_w: float, max_h: float, align: str = "LEFT", cell_w: float | None = None):
    """The picture inside the box, keeping its proportions. In a table cell it is wrapped in a one-cell table so it can be aligned."""
    from PIL import Image as PILImage

    with PILImage.open(io.BytesIO(img.data)) as pil:
        w, h = pil.size
    width = min(max_w, cell_w) if cell_w else max_w
    height = width * h / w
    if height > max_h:
        height, width = max_h, max_h * w / h
    flow = Image(io.BytesIO(img.data), width=width, height=height)
    if cell_w is None:
        flow.hAlign = align.upper()
        return flow
    box = Table([[flow]], colWidths=[cell_w])
    box.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), align.upper()), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))  # fmt: skip
    return box


def _rows(pairs: list[tuple[str, str]], st: dict[str, ParagraphStyle], label_w: float, value_w: float):
    table = Table(
        [[Paragraph(_p(label), st["small"]), Paragraph(_p(value), st["base"])] for label, value in pairs],
        colWidths=[label_w, value_w],
    )
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                               ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2)]))  # fmt: skip
    return table


def build_receipt_pdf(
    kind: str, number: str, details: dict, design: ReceiptDesign, images: dict[str, Image_] | None = None, watermark: str | None = None,
) -> tuple[bytes, int]:  # fmt: skip
    """(the PDF, its page count). ``details`` is the document's stored details; ``images`` maps logo/signature/stamp to their pictures."""
    _ensure_fonts()
    images = images or {}
    page_w, page_h = A4
    sty, lab = design.style, design.labels
    mx = sty.margin_x_mm * mm
    width = page_w - 2 * mx
    gap = sty.section_gap_mm * mm
    brand = colors.HexColor(design.branding.brand_color)
    accent = colors.HexColor(design.branding.accent_color)
    title_color = CREDIT if kind == "credit_note" else brand
    st = _styles(brand, sty)
    st["title"] = ParagraphStyle("title", parent=st["title"], textColor=title_color)
    align = design.branding.header_align
    sec = design.sections
    currency = details["currency"]
    issuer = details["issuer"]
    student = details["student"]
    doc_title = lab.title(kind)
    total_pages = [0]

    def shown(slot_name: str):
        slot = design.slots()[slot_name]
        return slot if slot.show else None

    def make_story() -> list:
        """A fresh story for each build (flowables are used up by a build, and the document is built twice for \"Page x of y\")."""
        # ---------------------------------------------------------------- header
        cell_widths = {"center": width, "left": width * 0.58, "right": width * 0.42}

        def issuer_block(text_align: str, cell_w: float) -> list:
            parts: list = []
            logo_slot, logo = shown("logo"), images.get("logo")
            if logo_slot is not None and logo is not None:
                parts.append(_image(logo, logo_slot.width_mm * mm, logo_slot.height_mm * mm, text_align if logo_slot.align == "auto" else logo_slot.align, cell_w))
                parts.append(Spacer(1, 2 * mm))
            parts.append(Paragraph(_p(issuer["name"]), _aligned(st["issuer"], text_align)))
            if design.texts.header_text:
                parts.append(Paragraph(_p(design.texts.header_text), _aligned(st["small"], text_align)))
            if issuer.get("address") and sec.issuer_address:
                parts.append(Paragraph(_p(issuer["address"]), _aligned(st["small"], text_align)))
            if issuer.get("gstin"):  # the GSTIN is a legal identifier: it is always shown when the issuer has one
                parts.append(Paragraph(_p(f"{lab.gstin} {issuer['gstin']}"), _aligned(st["small"], text_align)))
            if sec.issuer_contacts:
                contact = "  ·  ".join(x for x in (design.contacts.email, design.contacts.phone, design.contacts.website) if x)
                if contact:
                    parts.append(Paragraph(_p(contact), _aligned(st["small"], text_align)))
            return parts

        def title_block(text_align: str, cell_w: float) -> list:
            badge_color = CREDIT if kind == "credit_note" else colors.HexColor("#166534")
            badge_style = ParagraphStyle("badge", parent=st["bold"], fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)
            badge_text = lab.status_refunded if kind == "credit_note" else lab.status_paid
            chip = Table([[Paragraph(_p(badge_text), badge_style)]], colWidths=[max(24 * mm, (len(badge_text) * 2.4 + 8) * mm / 2)])
            chip.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), badge_color), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
            badge = Table([[chip]], colWidths=[cell_w])  # (a table in a cell is aligned by the cell)
            badge.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), text_align.upper()), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                       ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            parts = [Paragraph(_p(doc_title), _aligned(st["title"], text_align))]
            if lab.subtitle(kind):
                parts.append(Paragraph(_p(lab.subtitle(kind)), _aligned(st["small"], text_align)))
            parts += [
                Paragraph(_p(f"{lab.number} {number}"), _aligned(st["bold"], text_align)),
                Paragraph(_p(f"{lab.issue_date} {day(details['issued_on'])}"), _aligned(st["base"], text_align)),
                Spacer(1, 2.5 * mm),
                badge,
            ]
            return parts

        if align == "center":
            header = Table([[issuer_block("center", width)], [Spacer(1, 3 * mm)], [title_block("center", width)]], colWidths=[width])
        else:
            left, right = (issuer_block("left", cell_widths["left"]), title_block("right", cell_widths["right"])) if align == "left" else (title_block("left", cell_widths["left"]), issuer_block("right", cell_widths["right"]))
            header = Table([[left, right]], colWidths=[width * 0.58, width * 0.42])
        header_style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, -1), (-1, -1), 4 * mm)]
        if sty.header_rule:
            header_style.append(("LINEBELOW", (0, -1), (-1, -1), 1.4, title_color))
        header.setStyle(TableStyle(header_style))

        # ---------------------------------------------------------------- who and what
        billed = [Paragraph(_p(lab.billed_to), st["label"]), Paragraph(_p(student["name"]), st["name"])]
        if sec.student_email and student.get("email"):
            billed.append(Paragraph(_p(student["email"]), st["base"]))
        if sec.student_mobile and student.get("phone"):
            billed.append(Paragraph(_p(f"{lab.mobile} {student['phone']}"), st["base"]))

        pairs: list[tuple[str, str]] = []
        if sec.application_reference and details.get("application_reference"):
            pairs.append((lab.application, details["application_reference"]))
        if sec.programme and details.get("internship"):
            pairs.append((lab.programme, details["internship"]))
        if sec.payment_method and details.get("method"):
            pairs.append((lab.payment_method, details["method"]))
        pairs.append((lab.transaction_ref, details.get("transaction_reference") or "-"))
        pairs.append((lab.payment_date, day(details.get("paid_on")) or "-"))
        if details.get("against"):
            pairs.append((lab.against, details["against"]))
        pairs.append((lab.payment_status, lab.status_refunded_word if kind == "credit_note" else lab.status_paid_word))
        label_w = min(max(27 * mm, max(len(label) for label, _ in pairs) * (sty.body_size - 1) * 0.55), width * 0.3)
        grid = Table([[billed, [Paragraph(_p(lab.payment_details), st["label"]), _rows(pairs, st, label_w, width * 0.57 - label_w - 6)]]],
                     colWidths=[width * 0.43, width * 0.57], splitInRow=1)  # fmt: skip
        grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

        # ---------------------------------------------------------------- amounts (always from the verified record)
        tax = details.get("tax")
        lines = [[Paragraph(_p(details.get("description") or "Payment"), st["base"]),
                  Paragraph(_p(money(tax["taxable"] if tax else details["amount"], currency)), _aligned(st["base"], "right"))]]  # fmt: skip
        if design.texts.description_note:
            lines[0][0] = [lines[0][0], Paragraph(_p(design.texts.description_note), st["small"])]
        if tax:
            lines.append([Paragraph(_p(f"{tax['label']} @ {tax['rate_percent']}%"), st["base"]), Paragraph(_p(money(tax["tax"], currency)), _aligned(st["base"], "right"))])
        items = Table([[Paragraph(_p(lab.col_description), st["head"]), Paragraph(_p(lab.col_amount), _aligned(st["head"], "right"))]] + lines,
                      colWidths=[width - 42 * mm, 42 * mm], repeatRows=1, splitInRow=1)  # fmt: skip
        item_style = [("BACKGROUND", (0, 0), (-1, 0), accent), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        if sty.table_borders == "lines":
            item_style.append(("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#D1D5DB")))
        elif sty.table_borders == "grid":
            item_style.append(("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")))
        items.setStyle(TableStyle(item_style))
        total_label = lab.total_refunded if kind == "credit_note" else lab.total_received
        total = Table([[Paragraph(_p(total_label), st["total_label"]),
                        Paragraph(_p(money(details["amount"], currency)), ParagraphStyle("t", parent=st["title"], alignment=TA_RIGHT, textColor=title_color))]],
                      colWidths=[width - 70 * mm, 70 * mm])  # fmt: skip
        total.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                                   ("LINEABOVE", (0, 0), (-1, 0), 1.2, title_color)]))  # fmt: skip

        blocks: dict[str, list] = {"details": [grid], "items": [items, Spacer(1, 4 * mm), KeepTogether([total])], "thank_you": [], "signature": []}
        thanks = design.texts.thank_you
        if sec.thank_you and thanks and kind != "credit_note":
            blocks["thank_you"] = [Paragraph(_p(thanks), st["thanks"])]

        sig_slot, stamp_slot = shown("signature"), shown("stamp")
        if sig_slot is not None or stamp_slot is not None:
            cells: list = []
            widths: list[float] = []
            if stamp_slot is not None and images.get("stamp") is not None:
                cells.append(_image(images["stamp"], stamp_slot.width_mm * mm, stamp_slot.height_mm * mm, "CENTER", (stamp_slot.width_mm + 2) * mm))
                widths.append((stamp_slot.width_mm + 6) * mm)
            if sig_slot is not None:
                sign = _image(images["signature"], sig_slot.width_mm * mm, sig_slot.height_mm * mm, "CENTER", max(sig_slot.width_mm + 2, 44) * mm) if images.get("signature") is not None else Spacer(1, 14 * mm)
                cells.append([sign, HRFlowable(width="100%", thickness=0.6, color=GREY, spaceBefore=1, spaceAfter=2), Paragraph(_p(design.signatory_label), _aligned(st["small"], "center"))])
                widths.append(max(sig_slot.width_mm + 6, 46) * mm)
            block = Table([cells], colWidths=widths, hAlign=design.signature_align.upper())
            block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
            blocks["signature"] = [KeepTogether([block])]
        else:
            blocks["signature"] = [Paragraph(_p(lab.system_line), st["small"])]

        story: list = [header]
        for part in design.body_order:
            if blocks[part]:
                story += [Spacer(1, gap)] + blocks[part]
        if design.texts.terms:
            story += [Spacer(1, gap * 0.8), Paragraph(_p(design.texts.terms), st["small"])]
        if not footer_in_band:
            story += [Spacer(1, 6 * mm)] + [Paragraph(_p(t), _aligned(st["small"], "center")) for t in footer_texts]
        return story

    footer_text = (design.texts.footer or "").strip() if sec.footer else ""
    footer_issuer = (details.get("footer") or "").strip()  # the issuer's own footer line from its settings
    footer_texts = [t for t in (footer_text, footer_issuer) if t]
    footer_lines = [ln for t in footer_texts for ln in simpleSplit(printable(t).replace(chr(10), " "), REGULAR, 7.5, width)]
    FOOTER_BAND_LINES = 3
    footer_in_band = len(footer_lines) <= FOOTER_BAND_LINES  # a longer footer is part of the page content instead, so nothing is cut off

    # ---------------------------------------------------------------- the page
    def on_page(c, doc) -> None:
        c.saveState()
        n = doc.page
        if watermark:
            c.saveState()
            c.setFillColor(colors.HexColor("#9CA3AF"))
            c.setFillAlpha(0.22)
            c.setFont(BOLD, 40)
            c.translate(page_w / 2, page_h / 2)
            c.rotate(35)
            c.drawCentredString(0, 0, printable(watermark))
            c.restoreState()
        if n > 1:  # a small running header on the pages after the first
            c.setFont(BOLD, 8.5)
            c.setFillColor(title_color)
            c.drawString(mx, page_h - MARGIN_TOP + 3 * mm, printable(issuer["name"])[:70])
            c.drawRightString(page_w - mx, page_h - MARGIN_TOP + 3 * mm, printable(f"{doc_title} {number}"))
            c.setStrokeColor(title_color)
            c.setLineWidth(0.6)
            c.line(mx, page_h - MARGIN_TOP + 1.2 * mm, page_w - mx, page_h - MARGIN_TOP + 1.2 * mm)
        c.setStrokeColor(colors.HexColor("#D1D5DB"))
        c.setLineWidth(0.5)
        c.line(mx, 14 * mm + 3.4 * mm * FOOTER_BAND_LINES, page_w - mx, 14 * mm + 3.4 * mm * FOOTER_BAND_LINES)
        c.setFillColor(GREY)
        c.setFont(REGULAR, 7.5)
        if footer_in_band:
            y = 14 * mm + 3.4 * mm * (FOOTER_BAND_LINES - 1)
            for line in footer_lines:
                c.drawCentredString(page_w / 2, y, line)
                y -= 3.4 * mm
        c.drawString(mx, 11 * mm, printable(f"{doc_title.title()} {number}"))
        of = f" of {total_pages[0]}" if total_pages[0] else ""
        c.drawRightString(page_w - mx, 11 * mm, printable(f"{lab.page} {n}{of}"))
        c.restoreState()

    def make(buffer: io.BytesIO) -> int:
        doc = BaseDocTemplate(
            buffer, pagesize=A4, leftMargin=mx, rightMargin=mx, topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
            title=printable(f"{doc_title.title()} {number}"), author=printable(issuer["name"]) or "ERPX", subject=printable(details.get("application_reference", "")),
            invariant=1,
        )  # fmt: skip
        frame = Frame(mx, MARGIN_BOTTOM, width, page_h - MARGIN_TOP - MARGIN_BOTTOM, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        later = Frame(mx, MARGIN_BOTTOM, width, page_h - MARGIN_TOP - MARGIN_BOTTOM - 8 * mm, id="l", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates([PageTemplate(id="first", frames=[frame], onPage=on_page), PageTemplate(id="later", frames=[later], onPage=on_page)])
        doc.build([NextPageTemplate("later"), *make_story()])
        return doc.page

    scratch = io.BytesIO()
    total_pages[0] = make(scratch)  # first pass: how many pages ("Page 1 of 1")
    out = io.BytesIO()
    pages = make(out)
    return out.getvalue(), pages
