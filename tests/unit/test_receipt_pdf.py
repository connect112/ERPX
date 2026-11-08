"""
The receipt design and the PDF it draws: validation, one page for a normal document, more pages (never cut off) for a long one, the
rupee sign in an embedded font, selectable text, optional sections that hide and mandatory ones that cannot, safe handling of custom
text, and image validation. Pure: no database, no network.
"""

import io

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from modules.internship_onboarding.receipt_design import ReceiptDesign, contrast_with_white, default_design, parse_design
from modules.internship_onboarding.receipt_pdf import Image_, build_receipt_pdf, money, printable
from modules.internship_onboarding.receipt_service import AssetError, normalize_image

pytestmark = pytest.mark.unit

PNG_MAGIC = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
JPEG_MAGIC = bytes([0xFF, 0xD8, 0xFF])
KINDS = ("receipt", "tax_invoice", "credit_note")
ALIGNS = ("left", "center", "right")


def details(kind="receipt", **over):
    d = {
        "kind": kind,
        "issuer": {"name": "GIR Technologies", "address": "Plot 12, Madhapur, Hyderabad 500081", "gstin": "36ABCDE1234F1Z5" if kind == "tax_invoice" else None},
        "student": {"name": "Asha Rao", "email": "asha.rao@example.com"},
        "application_reference": "ERPX-INT-2026-000123", "internship": "Cloud Internship 2026", "description": "Internship programme fee",
        "method": "Online (Cashfree)", "transaction_reference": "5114910123456", "paid_on": "2026-11-04", "issued_on": "2026-11-05",
        "currency": "INR", "amount": "5900.00",
        "tax": {"label": "GST", "rate_percent": "18", "taxable": "5000.00", "tax": "900.00"} if kind == "tax_invoice" else None,
        "against": "Receipt RCPT-2026-000045" if kind == "credit_note" else None, "footer": "",
    }
    d.update(over)
    return d


def png(w=300, h=120, color=(31, 58, 95, 255)) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGBA", (w, h), color).save(out, "PNG")
    return out.getvalue()


def words(pdf: bytes) -> list[tuple[str, float, float, int]]:
    """Every text run with its position: (text, x, y, page number)."""
    runs = []
    reader = PdfReader(io.BytesIO(pdf))
    for number, page in enumerate(reader.pages, start=1):
        def visit(text, cm, tm, font, size, number=number):
            if text.strip():  # the position on the page: the text matrix inside the current transformation
                runs.append((text.strip(), cm[4] + tm[4] * cm[0], cm[5] + tm[5] * cm[3], number))

        page.extract_text(visitor_text=visit)
    return runs


def text_of(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


# ------------------------------------------------------------------ the design


def test_the_default_design_is_valid_and_readable():
    design = default_design()
    assert design.branding.header_align == "left" and design.sections.student_mobile is False
    assert contrast_with_white(design.branding.brand_color) >= 3


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"branding": {"brand_color": "navy"}}, "colour like"),
        ({"branding": {"brand_color": "#FFFF99"}}, "too light"),
        ({"branding": {"header_align": "justify"}}, "header_align"),
        ({"texts": {"thank_you": "x" * 301}}, "300"),
        ({"texts": {"footer": "a\x00b"}}, "cannot be printed"),
        ({"contacts": {"email": "a\nb"}}, "single line"),
        ({"logo": {"width_mm": 500}}, "width_mm"),
        ({"unknown_field": 1}, "unknown_field"),
        ({"sections": {"document_title": False}}, "document_title"),  # mandatory parts cannot be switched off
    ],
)
def test_a_design_that_is_unreadable_unsafe_or_hides_mandatory_parts_is_refused(bad, message):
    with pytest.raises(ValidationError, match=message):
        parse_design(bad)


def test_colours_are_normalized_and_the_design_round_trips():
    design = parse_design({"branding": {"brand_color": "#0f766e", "accent_color": "#e6f4f1"}})
    assert design.branding.brand_color == "#0F766E"
    assert ReceiptDesign.model_validate(design.model_dump(mode="json")) == design


# ------------------------------------------------------------------ one page for a normal document


@pytest.mark.parametrize("align", ALIGNS)
@pytest.mark.parametrize("kind", KINDS)
def test_a_normal_document_is_one_a4_page_in_every_layout(kind, align):
    design = parse_design({"branding": {"header_align": align}, "signature": {"show": True}, "stamp": {"show": True}, "contacts": {"email": "a@b.example", "phone": "+91 40 1234 5678", "website": "example.com"},
                           "texts": {"footer": "Registered office: GIR Technologies, Hyderabad."}})  # fmt: skip
    pdf, pages = build_receipt_pdf(kind, "RCPT-2026-000046", details(kind), design, {"logo": Image_(png()), "signature": Image_(png()), "stamp": Image_(png(100, 100))})
    reader = PdfReader(io.BytesIO(pdf))
    assert pages == 1 == len(reader.pages)
    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (595, 842)  # A4


def test_the_rupee_sign_is_drawn_from_an_embedded_unicode_font_and_the_text_is_selectable():
    pdf, _ = build_receipt_pdf("tax_invoice", "RCPT-2026-000046", details("tax_invoice"), default_design())
    text = text_of(pdf)
    assert "₹ 5,900.00" in text and "₹ 5,000.00" in text and "₹ 900.00" in text
    assert "GST @ 18%" in text and "TAX INVOICE" in text and "GSTIN: 36ABCDE1234F1Z5" in text and "RCPT-2026-000046" in text
    fonts = {}
    for page in PdfReader(io.BytesIO(pdf)).pages:
        fonts.update(page["/Resources"]["/Font"])
    embedded = [f.get_object() for f in fonts.values() if "DejaVu" in str(f.get_object().get("/BaseFont"))]
    assert len(embedded) >= 2  # regular and bold, as subsets of the real font (not a built-in font)
    for f in embedded:
        assert "/FontFile2" in f["/FontDescriptor"]  # the font program itself is inside the file
    assert b"\xe2\x82\xb9" not in pdf  # (the sign is a glyph in the font, not raw text)


def test_other_currencies_keep_their_code_and_amounts_are_never_rounded_away():
    assert money("5900", "INR") == "₹ 5,900.00" and money("1234567.5", "INR") == "₹ 1,234,567.50" and money("10", "USD") == "USD 10.00"


def test_the_footer_and_page_number_are_on_the_same_page_as_the_content():
    design = parse_design({"texts": {"footer": "GIR Technologies, Hyderabad. Thank you."}})
    pdf, pages = build_receipt_pdf("receipt", "RCPT-2026-000046", details(), design)
    runs = words(pdf)
    assert pages == 1 and {r[3] for r in runs} == {1}
    by_text = {t: y for t, _, y, _ in runs}
    total_y = next(y for t, y in by_text.items() if t.startswith("₹ 5,900.00") and y < 700)
    footer_y = next(y for t, y in by_text.items() if "Thank you." in t)
    page_y = next(y for t, y in by_text.items() if t.startswith("Page 1 of 1"))
    assert page_y < footer_y < total_y  # the content, then the footer, then the page number, all on page 1


def test_no_text_runs_outside_the_margins_or_into_the_footer_band():
    design = parse_design({"branding": {"header_align": "center"}, "texts": {"footer": "Footer line"}})
    pdf, _ = build_receipt_pdf("tax_invoice", "RCPT-2026-000046", details("tax_invoice"), design, {"logo": Image_(png())})
    for text, x, y, _ in words(pdf):
        assert 40 <= x <= 560 and 20 <= y <= 820, (text, x, y)
        body = not text.startswith(("Page ", "Footer", "Tax Invoice RCPT"))
        if body:
            assert y > 32 * 2.835 - 1, (text, y)  # nothing of the content is drawn in the reserved footer band


def test_the_pdf_is_reproducible():
    one = build_receipt_pdf("receipt", "RCPT-2026-000046", details(), default_design())[0]
    two = build_receipt_pdf("receipt", "RCPT-2026-000046", details(), default_design())[0]
    assert one == two


# ------------------------------------------------------------------ a long document uses more pages, never cuts anything off


def test_a_very_long_document_continues_on_more_pages_with_everything_kept():
    long_description = "Lab access, mentoring, assessments and certification. " * 90
    footer = "Payment terms and conditions apply to every programme. " * 30
    design = parse_design({"texts": {"footer": footer[:500]}})
    pdf, pages = build_receipt_pdf("tax_invoice", "RCPT-2026-000046", details("tax_invoice", description=long_description, footer=footer[:500]), design)
    assert pages >= 2 == len(PdfReader(io.BytesIO(pdf)).pages) or pages > 2
    text = " ".join(text_of(pdf).split())
    assert text.count("Lab access, mentoring") >= 85 and "Payment terms and conditions" in text  # nothing hidden
    assert "₹ 5,900.00" in text and "Page 1 of %d" % pages in text and "Page %d of %d" % (pages, pages) in text
    assert all(len(runs) for runs in [words(pdf)])


def test_a_long_footer_is_part_of_the_content_instead_of_being_squeezed_into_the_band():
    pdf, pages = build_receipt_pdf("receipt", "RCPT-2026-000046", details(footer="Note. " * 90), parse_design({"texts": {"footer": "Terms. " * 70}}))
    assert " ".join(text_of(pdf).split()).count("Terms.") == 70 and " ".join(text_of(pdf).split()).count("Note.") == 90
    assert pages <= 2


# ------------------------------------------------------------------ optional sections hide, mandatory ones stay


def test_optional_sections_can_be_hidden_and_the_mandatory_ones_always_show():
    off = parse_design({"sections": {"student_email": False, "application_reference": False, "programme": False, "payment_method": False, "issuer_contacts": False,
                                     "thank_you": False, "footer": False}, "contacts": {"email": "accounts@example.com"}, "texts": {"footer": "Hidden footer"}})  # fmt: skip
    text = text_of(build_receipt_pdf("tax_invoice", "RCPT-2026-000046", details("tax_invoice", footer="Issuer footer"), off)[0])
    for gone in ("asha.rao@example.com", "ERPX-INT-2026-000123", "Cloud Internship 2026", "Online (Cashfree)", "accounts@example.com", "Thank you for your payment.", "Hidden footer"):
        assert gone not in text, gone
    for kept in ("TAX INVOICE", "RCPT-2026-000046", "Date: 05 Nov 2026", "GIR Technologies", "GSTIN: 36ABCDE1234F1Z5", "Asha Rao", "5114910123456", "04 Nov 2026",
                 "Payment status", "GST @ 18%", "Total received", "₹ 5,900.00"):  # fmt: skip
        assert kept in text, kept


def test_the_mobile_number_is_shown_only_when_the_design_asks_and_the_document_has_one():
    with_phone = details(student={"name": "Asha Rao", "email": "a@b.example", "phone": "98765 43210"})
    assert "Mobile: 98765 43210" not in text_of(build_receipt_pdf("receipt", "R-1", with_phone, default_design())[0])
    assert "Mobile: 98765 43210" in text_of(build_receipt_pdf("receipt", "R-1", with_phone, parse_design({"sections": {"student_mobile": True}}))[0])
    assert "Mobile:" not in text_of(build_receipt_pdf("receipt", "R-1", details(), parse_design({"sections": {"student_mobile": True}}))[0])


def test_each_document_type_keeps_its_own_wording():
    r = text_of(build_receipt_pdf("receipt", "R-1", details("receipt"), default_design())[0])
    c = text_of(build_receipt_pdf("credit_note", "C-1", details("credit_note"), default_design())[0])
    assert "PAYMENT RECEIPT" in r and "Total received" in r and "PAID" in r and "Thank you for your payment." in r
    assert "CREDIT NOTE" in c and "Total refunded" in c and "REFUNDED" in c and "Against" in c and "Receipt RCPT-2026-000045" in c
    assert "Thank you for your payment." not in c


# ------------------------------------------------------------------ custom text is only ever text


def test_markup_and_scripts_in_custom_text_are_drawn_as_plain_text():
    nasty = "<b>bold</b> <script>alert(1)</script> &amp; <font color='red'>x</font>"
    pdf, pages = build_receipt_pdf("receipt", "R-1", details(student={"name": nasty, "email": "a@b.example"}), parse_design({"texts": {"thank_you": nasty}}))
    text = " ".join(text_of(pdf).split())
    assert "<b>bold</b>" in text and "<script>alert(1)</script>" in text and "&amp;" in text and pages == 1
    assert b"/JavaScript" not in pdf and b"/JS" not in pdf and b"/OpenAction" not in pdf and b"/Launch" not in pdf


def test_characters_the_font_cannot_draw_are_dropped_instead_of_failing_or_printing_boxes():
    han = chr(0x6F22)  # a Han character: not in the receipt font
    assert printable(f"Asha {han} Rao") == "Asha  Rao"
    pdf, _ = build_receipt_pdf("receipt", "R-1", details(student={"name": f"Asha {han} Rao", "email": "a@b.example"}), default_design())
    assert "Asha" in text_of(pdf)


def test_a_watermark_marks_every_page_of_a_preview_and_an_official_document_has_none():
    marked = text_of(build_receipt_pdf("receipt", "R-1", details(), default_design(), watermark="SAMPLE - NOT A VALID RECEIPT")[0])
    plain = text_of(build_receipt_pdf("receipt", "R-1", details(), default_design())[0])
    assert "SAMPLE - NOT A VALID RECEIPT" in marked and "SAMPLE" not in plain


def test_images_are_placed_only_when_shown_and_provided():
    with_logo = build_receipt_pdf("receipt", "R-1", details(), default_design(), {"logo": Image_(png())})[0]
    without = build_receipt_pdf("receipt", "R-1", details(), default_design())[0]
    hidden = build_receipt_pdf("receipt", "R-1", details(), parse_design({"logo": {"show": False}}), {"logo": Image_(png())})[0]

    def images(pdf):
        return sum(len(getattr(p, "images", [])) for p in PdfReader(io.BytesIO(pdf)).pages)

    assert images(with_logo) == 1 and images(without) == 0 and images(hidden) == 0


# ------------------------------------------------------------------ uploaded images


def test_a_png_or_jpg_is_normalized_to_a_small_png_without_metadata():
    from PIL import Image

    jpeg = io.BytesIO()
    img = Image.new("RGB", (2000, 800), (200, 30, 30))
    exif = img.getexif()
    exif[0x010F] = "SecretCameraMaker"
    img.save(jpeg, "JPEG", exif=exif)
    data, w, h = normalize_image(jpeg.getvalue(), "logo")
    assert data.startswith(b"\x89PNG") and max(w, h) <= 900 and b"SecretCameraMaker" not in data
    assert normalize_image(png(), "stamp")[1:] == (300, 120)


@pytest.mark.parametrize(
    "data, kind, message",
    [
        pytest.param(b"", "logo", "empty", id="empty"),
        pytest.param(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "logo", "PNG or JPG", id="svg"),
        pytest.param(b"GIF89a" + b"0" * 100, "logo", "PNG or JPG", id="gif"),
        pytest.param(PNG_MAGIC + b"not really a png", "logo", "usable", id="fake-png"),
        pytest.param(JPEG_MAGIC + b"0" * 50, "logo", "usable", id="fake-jpeg"),
        pytest.param(b"%PDF-1.4 hello", "logo", "PNG or JPG", id="pdf"),
        pytest.param(b"0" * (2 * 1024 * 1024 + 1), "logo", "2 MB", id="too-big"),
        pytest.param(png(), "banner", "logo, signature or stamp", id="unknown-kind"),
        pytest.param(png(8, 8), "logo", "too small", id="tiny"),
    ],
)
def test_images_that_are_not_real_pictures_are_refused_with_a_reason(data, kind, message):
    with pytest.raises(AssetError, match=message):
        normalize_image(data, kind)


def test_a_decompression_bomb_is_refused_before_it_is_decoded(monkeypatch):
    from modules.internship_onboarding import receipt_service

    monkeypatch.setattr(receipt_service, "MAX_PIXELS", 1000)
    with pytest.raises(AssetError, match="too large"):
        normalize_image(png(100, 100), "logo")
