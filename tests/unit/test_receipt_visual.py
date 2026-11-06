"""
Visual checks of the receipt PDF: the page is rasterized and measured, so an overlap, a clipped block or a stray blank page is caught
by what is actually painted, not only by the text positions. Needs PyMuPDF (a developer tool, not a dependency of the application):
the tests are skipped where it is not installed.
"""

import io

import pytest

from modules.internship_onboarding.receipt_design import parse_design
from modules.internship_onboarding.receipt_pdf import Image_, build_receipt_pdf
from tests.unit.test_receipt_pdf import details, png

pymupdf = pytest.importorskip("pymupdf")
pytestmark = pytest.mark.unit

DPI = 72  # one pixel per point
MM = DPI / 25.4


def raster(pdf: bytes, page: int = 0):
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    pix = doc[page].get_pixmap(dpi=DPI, alpha=False)
    return pix, len(doc)


def ink_box(pix, threshold: int = 245):
    """(left, top, right, bottom) of everything painted (not white) on the page, in points."""
    width, height, n = pix.width, pix.height, pix.n
    data = pix.samples
    left, top, right, bottom = width, height, 0, 0
    for y in range(height):
        row = data[y * width * n : (y + 1) * width * n]
        for x in range(width):
            if min(row[x * n : x * n + 3]) < threshold:
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
    return left, top, right, bottom


@pytest.mark.parametrize("align", ("left", "center", "right"))
@pytest.mark.parametrize("kind", ("receipt", "tax_invoice", "credit_note"))
def test_everything_painted_stays_inside_the_margins_on_a_single_page(kind, align):
    design = parse_design({"branding": {"header_align": align}, "signature": {"show": True}, "stamp": {"show": True}, "texts": {"footer": "Registered office: Hyderabad."}})
    pdf, pages = build_receipt_pdf(kind, "RCPT-2026-000046", details(kind), design, {"logo": Image_(png()), "signature": Image_(png()), "stamp": Image_(png(100, 100))})
    pix, count = raster(pdf)
    assert pages == count == 1
    left, top, right, bottom = ink_box(pix)
    assert left >= 15 * MM and right <= pix.width - 15 * MM, (left, right)  # the 18 mm side margins hold
    assert top >= 10 * MM and bottom <= pix.height - 8 * MM, (top, bottom)
    assert (right - left) > 100 * MM and (bottom - top) > 150 * MM  # the page is used, not mostly empty


def test_a_long_document_paints_every_page_and_none_is_blank():
    long_text = "Lab access, mentoring, assessments and certification. " * 120
    pdf, pages = build_receipt_pdf("receipt", "RCPT-2026-000046", details(description=long_text), parse_design({}))
    assert pages >= 2
    for index in range(pages):
        pix, _ = raster(pdf, index)
        left, top, right, bottom = ink_box(pix)
        assert right > left and bottom > top, f"page {index + 1} is blank"
        assert right <= pix.width - 15 * MM and bottom <= pix.height - 8 * MM


def test_the_watermark_is_painted_on_a_preview_and_not_on_an_official_document():
    def grey_pixels(pdf):
        pix, _ = raster(pdf)
        data, n = pix.samples, pix.n
        return sum(1 for i in range(0, len(data), n) if 200 <= data[i] <= 240 and abs(data[i] - data[i + 1]) < 8 and abs(data[i] - data[i + 2]) < 8)

    marked = build_receipt_pdf("receipt", "R-1", details(), parse_design({}), watermark="SAMPLE - NOT A VALID RECEIPT")[0]
    plain = build_receipt_pdf("receipt", "R-1", details(), parse_design({}))[0]
    assert grey_pixels(marked) > grey_pixels(plain) + 2000


def test_the_logo_is_painted_where_the_header_puts_it():
    pdf, _ = build_receipt_pdf("receipt", "R-1", details(), parse_design({"logo": {"width_mm": 40, "height_mm": 18}}), {"logo": Image_(png(400, 160, (200, 0, 0, 255)))})
    pix, _ = raster(pdf)
    reds = [(i // pix.n % pix.width, i // pix.n // pix.width) for i in range(0, len(pix.samples), pix.n) if pix.samples[i] > 150 and pix.samples[i + 1] < 40 and pix.samples[i + 2] < 40]
    assert reds, "the logo was not painted"
    xs, ys = [x for x, _ in reds], [y for _, y in reds]
    assert 17 * MM <= min(xs) <= 20 * MM and min(ys) < 40 * MM  # top left, inside the page margin
    assert 36 * MM <= (max(xs) - min(xs)) <= 41 * MM  # as wide as asked
