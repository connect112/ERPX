"""The customizable parts of the receipt design: every fixed word, the titles (which may be reworded but never misrepresent the kind of
document), typography, spacing, section order and optional text. Amounts, tax, references and numbers cannot be set by a design."""

import io

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from modules.internship_onboarding.receipt_design import default_design, parse_design
from modules.internship_onboarding.receipt_pdf import Image_, build_receipt_pdf
from tests.unit.test_receipt_pdf import details, png, text_of

pytestmark = pytest.mark.unit


def runs(pdf: bytes):
    """(text, x, y, font size, page) for every text run."""
    out = []
    for number, page in enumerate(PdfReader(io.BytesIO(pdf)).pages, start=1):
        def visit(text, cm, tm, font, size, number=number):
            if text.strip():
                out.append((text.strip(), cm[4] + tm[4] * cm[0], cm[5] + tm[5] * cm[3], size * abs(tm[0] * cm[0] or 1), number))

        page.extract_text(visitor_text=visit)
    return out


def build(kind="receipt", design=None, **over):
    return build_receipt_pdf(kind, "RCPT-2026-000046", details(kind, **over), parse_design(design or {}))


# ------------------------------------------------------------------ designs saved before these controls existed


def test_a_design_saved_before_the_new_controls_validates_and_keeps_the_original_wording():
    old = {"branding": {"brand_color": "#0F766E", "accent_color": "#E6F4F1", "header_align": "center"}, "contacts": {"email": "a@b.example"},
           "sections": {"student_mobile": True}, "texts": {"thank_you": "Thanks", "footer": "Footer"}, "logo": {"show": True, "asset_id": None, "width_mm": 30, "height_mm": 12},
           "signatory_label": "Director"}  # fmt: skip
    design = parse_design(old)
    assert design.labels == default_design().labels and design.style == default_design().style and design.body_order == ["details", "items", "thank_you", "signature"]
    text = text_of(build_receipt_pdf("tax_invoice", "R-1", details("tax_invoice"), design)[0])
    for original in ("TAX INVOICE", "BILLED TO", "PAYMENT DETAILS", "Payment status", "DESCRIPTION", "AMOUNT", "Total received", "PAID", "No. R-1", "Date: 05 Nov 2026", "Page 1 of 1"):
        assert original in text, original


# ------------------------------------------------------------------ wording


CUSTOM = {
    "title_receipt": "Fee Receipt", "title_tax_invoice": "GST Tax Invoice", "title_credit_note": "Credit Note (Refund)",
    "subtitle_receipt": "Acknowledgement of fees", "subtitle_tax_invoice": "Original for recipient", "subtitle_credit_note": "Refund of fees",
    "number": "Doc No:", "issue_date": "Issued on:", "gstin": "GST No:", "billed_to": "CUSTOMER", "payment_details": "FEE DETAILS", "application": "Enrolment",
    "programme": "Course", "payment_method": "Paid via", "transaction_ref": "Txn ID", "payment_date": "Received on", "against": "Refund of", "payment_status": "State",
    "col_description": "PARTICULARS", "col_amount": "VALUE", "total_received": "Amount received", "total_refunded": "Amount returned",
    "status_paid": "SETTLED", "status_refunded": "RETURNED", "status_paid_word": "Settled", "status_refunded_word": "Returned",
    "system_line": "Computer generated; no signature required.", "page": "Sheet",
}  # fmt: skip


@pytest.mark.parametrize("kind", ["receipt", "tax_invoice", "credit_note"])
def test_every_fixed_word_on_each_document_can_be_changed_and_the_old_wording_disappears(kind):
    pdf, pages = build(kind, {"labels": CUSTOM})
    text = " ".join(text_of(pdf).split())
    assert pages == 1
    title = {"receipt": "Fee Receipt", "tax_invoice": "GST Tax Invoice", "credit_note": "Credit Note (Refund)"}[kind]
    subtitle = {"receipt": "Acknowledgement of fees", "tax_invoice": "Original for recipient", "credit_note": "Refund of fees"}[kind]
    assert title in text and subtitle in text
    for word in ("Doc No: RCPT-2026-000046", "Issued on: 05 Nov 2026", "CUSTOMER", "FEE DETAILS", "Enrolment", "Course", "Paid via", "Txn ID", "Received on", "State", "PARTICULARS", "VALUE", "Sheet 1 of 1"):
        assert word in text, word
    assert ("Amount returned" if kind == "credit_note" else "Amount received") in text and ("RETURNED" if kind == "credit_note" else "SETTLED") in text
    assert "Computer generated; no signature required." in text
    if kind == "credit_note":
        assert "Refund of Receipt RCPT-2026-000045" in text or ("Refund of" in text and "RCPT-2026-000045" in text)
    if kind == "tax_invoice":
        assert "GST No: 36ABCDE1234F1Z5" in text
    for old in ("PAYMENT RECEIPT", "BILLED TO", "PAYMENT DETAILS", "DESCRIPTION", "Total received", "Payment status", "This document was issued electronically"):
        assert old not in text, old


@pytest.mark.parametrize(
    "labels, message",
    [
        ({"title_tax_invoice": "Bill"}, "Tax Invoice"),
        ({"title_tax_invoice": "Tax Invoice / Credit Note"}, "Tax Invoice"),
        ({"title_credit_note": "Refund"}, "Credit Note"),
        ({"title_credit_note": "Credit Note and Tax Invoice"}, "Credit Note"),
        ({"title_receipt": "Tax Invoice"}, "cannot call the document"),
        ({"title_receipt": "Invoice"}, "cannot call the document"),
        ({"title_receipt": "Credit Note"}, "cannot call the document"),
        ({"status_paid": "REFUNDED"}, "must not contradict"),
        ({"status_refunded_word": "Fully paid"}, "must not contradict"),
        ({"billed_to": ""}, "at least 1"),
        ({"billed_to": "a\nb"}, "single line"),
        ({"billed_to": "x" * 31}, "at most 30"),
        ({"amount": "Total"}, "amount"),  # there is no label that could carry an amount
    ],
)
def test_a_title_can_be_reworded_but_never_misrepresent_the_kind_of_document(labels, message):
    with pytest.raises(ValidationError, match=message):
        parse_design({"labels": labels})


def test_no_part_of_the_design_can_carry_an_amount_a_tax_figure_a_reference_a_date_or_a_number():
    for sneaky in ({"amount": "1.00"}, {"tax": "0"}, {"transaction_reference": "X"}, {"issued_on": "2020-01-01"}, {"number": "RCPT-1"},
                   {"details": {"amount": "1"}}, {"labels": {"transaction_id": "X"}}, {"labels": {"gst_amount": "0"}}, {"texts": {"amount": "1"}}):  # fmt: skip
        with pytest.raises(ValidationError):
            parse_design(sneaky)
    # and whatever the wording, the figures printed are the record's
    text = text_of(build("tax_invoice", {"labels": CUSTOM, "texts": {"description_note": "Includes lab access"}})[0])
    for figure in ("5,000.00", "900.00", "5,900.00", "5114910123456", "04 Nov 2026", "RCPT-2026-000046"):
        assert figure in text, figure


def test_header_text_description_note_and_terms_are_printed_and_the_issuers_legal_identity_is_not_replaced():
    design = {"texts": {"header_text": "Cyber training academy", "description_note": "Includes lab access", "terms": "Fees are non-transferable."}}
    text = " ".join(text_of(build("tax_invoice", design)[0]).split())
    assert "Cyber training academy" in text and "Includes lab access" in text and "Fees are non-transferable." in text
    assert "GIR Technologies" in text and "GSTIN: 36ABCDE1234F1Z5" in text and "Internship programme fee" in text  # legal name, GSTIN and the accepted description stay


def test_the_issuer_address_can_be_hidden_but_the_gstin_is_always_shown():
    text = text_of(build("tax_invoice", {"sections": {"issuer_address": False}})[0])
    assert "Plot 12, Madhapur" not in text and "GSTIN: 36ABCDE1234F1Z5" in text


# ------------------------------------------------------------------ typography, spacing, borders, order


def test_font_sizes_follow_the_design():
    def size_of(design, start):
        return next(size for text, _, _, size, _ in runs(build(design=design)[0]) if text.startswith(start))  # (a big title may wrap onto two runs)

    small, big = {"style": {"title_size": 14, "issuer_size": 11, "body_size": 8}}, {"style": {"title_size": 26, "issuer_size": 20, "body_size": 11}}
    assert size_of(big, "PAYMENT") > size_of(small, "PAYMENT") + 8
    assert size_of(big, "GIR Technologies") > size_of(small, "GIR Technologies") + 6
    assert size_of(big, "Internship programme fee") > size_of(small, "Internship programme fee") + 2


def test_section_gap_and_side_margins_move_the_content():
    def ys(design):
        return {t: y for t, _, y, _, _ in runs(build(design=design)[0])}["DESCRIPTION"]

    assert ys({"style": {"section_gap_mm": 14}}) < ys({"style": {"section_gap_mm": 4}}) - 20  # a larger gap pushes the table down the page
    left = min(x for _, x, _, _, _ in runs(build(design={"style": {"margin_x_mm": 25}})[0]))
    assert left >= 25 * 72 / 25.4 - 1


def test_the_order_of_the_blocks_can_be_changed_and_the_totals_stay_with_the_items():
    def y(design, text):
        return {t: yy for t, _, yy, _, _ in runs(build(design=design)[0])}[text]

    default = {"body_order": ["details", "items", "thank_you", "signature"]}
    swapped = {"body_order": ["thank_you", "items", "details", "signature"]}
    assert y(default, "BILLED TO") > y(default, "DESCRIPTION") > y(default, "Thank you for your payment.")
    assert y(swapped, "Thank you for your payment.") > y(swapped, "DESCRIPTION") > y(swapped, "BILLED TO")
    for order in (default, swapped):  # whatever the order, the total sits directly after its table
        assert y(order, "DESCRIPTION") > y(order, "Total received") > y(order, "DESCRIPTION") - 120
    with pytest.raises(ValidationError):
        parse_design({"body_order": ["details", "items", "thank_you"]})
    with pytest.raises(ValidationError):
        parse_design({"body_order": ["details", "details", "items", "thank_you", "signature"]})


@pytest.mark.parametrize("borders", ["lines", "grid", "none"])
def test_table_borders_are_selectable_and_the_document_stays_on_one_page(borders):
    pdf, pages = build("tax_invoice", {"style": {"table_borders": borders, "header_rule": borders != "none"}})
    assert pages == 1 and "₹ 5,900.00" in text_of(pdf)


def test_alignment_of_the_logo_and_the_signature_block():
    images = {"logo": Image_(png(400, 160, (200, 0, 0, 255))), "signature": Image_(png()), "stamp": Image_(png(100, 100))}
    for logo_align in ("left", "center", "right"):
        pdf, pages = build_receipt_pdf("receipt", "R-1", details(), parse_design({"logo": {"align": logo_align}, "signature": {"show": True}, "signature_align": "left"}), images)
        assert pages == 1
    with pytest.raises(ValidationError):
        parse_design({"signature_align": "justify"})


def test_even_a_heavily_customized_design_keeps_every_word_and_figure_and_uses_more_pages_rather_than_losing_content():
    design = {"labels": CUSTOM, "style": {"body_size": 12, "title_size": 30, "issuer_size": 22, "section_gap_mm": 14, "margin_x_mm": 25},
              "texts": {"terms": "Terms. " * 80, "description_note": "Note. " * 40, "footer": "Footer. " * 30, "header_text": "Tagline"}}  # fmt: skip
    pdf, pages = build("tax_invoice", design)
    text = " ".join(text_of(pdf).split())
    assert pages >= 1 and text.count("Terms.") == 80 and text.count("Note.") == 40 and "₹ 5,900.00" in text and "GST Tax Invoice" in text
    assert f"Sheet {pages} of {pages}" in text
