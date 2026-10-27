"""The offer letter engine: validating an uploaded PDF, printing details on it, and the email wording."""

import io

import pytest
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from modules.our_internships.offer_letter import (
    DEFAULT_BODY,
    MAX_PAGES,
    OfferField,
    OfferLayout,
    TemplateError,
    attachment_name,
    build_offer_pdf,
    inspect_template,
    render_offer_email,
    safe_text,
    unknown_placeholders,
)


def _pdf(pages=1, size=(595, 842), label="OFFER OF INTERNSHIP") -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=size)
    for i in range(pages):
        c.drawString(72, size[1] - 72, f"{label} page {i + 1}")
        c.showPage()
    c.save()
    return out.getvalue()


def _text(pdf: bytes, page=0) -> str:
    return PdfReader(io.BytesIO(pdf)).pages[page].extract_text()


def _layout(*fields: OfferField) -> OfferLayout:
    return OfferLayout(fields=list(fields))


NAME = OfferField(key="name", x=0.5, y=0.4, align="center", font="serif_bold")


# ------------------------------------------------------------ the uploaded template


def test_a_pdf_is_accepted_and_its_pages_counted():
    assert inspect_template(_pdf(3)) == 3


@pytest.mark.parametrize(
    "raw, message",
    [
        (b"", "empty"),
        (b"just some text", "not a PDF"),
        (b"%PDF-1.4 but not really a pdf", "could not be read"),
    ],
)
def test_files_that_are_not_usable_say_why(raw, message):
    with pytest.raises(TemplateError, match=message):
        inspect_template(raw)


def test_a_pdf_over_10_mb_is_refused():
    with pytest.raises(TemplateError, match="larger than 10 MB"):
        inspect_template(b"%PDF-" + b"x" * (10 * 1024 * 1024))


def test_a_password_protected_pdf_is_refused():
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(_pdf())))
    writer.encrypt("secret")
    out = io.BytesIO()
    writer.write(out)
    with pytest.raises(TemplateError, match="password"):
        inspect_template(out.getvalue())


def test_too_many_pages_are_refused():
    with pytest.raises(TemplateError, match=f"at most {MAX_PAGES}"):
        inspect_template(_pdf(MAX_PAGES + 1))


# ------------------------------------------------------------------- the layout


def test_a_layout_must_place_the_name_and_each_detail_only_once():
    with pytest.raises(ValidationError, match="name"):
        _layout(OfferField(key="date"))
    with pytest.raises(ValidationError, match="only once"):
        _layout(NAME, OfferField(key="name"))
    assert _layout().fields == []  # nothing placed yet is fine while it is being set up


def test_field_values_are_kept_inside_sensible_limits():
    for bad in ({"x": 1.2}, {"y": -0.1}, {"font_size": 0.5}, {"color": "red"}, {"page": 0}, {"font": "comic"}):
        with pytest.raises(ValidationError):
            OfferField(key="name", **bad)


# ------------------------------------------------------------------- printing


def test_details_are_printed_on_the_template_and_the_rest_of_it_is_kept():
    layout = _layout(NAME, OfferField(key="reference", x=0.1, y=0.9), OfferField(key="institution", x=0.1, y=0.5))
    pdf = build_offer_pdf(
        _pdf(), layout, {"name": "Asha Rao", "reference": "OFR-2026-AB12-001", "institution": "Sri Venkateswara College"}
    )
    text = _text(pdf)
    assert "OFFER OF INTERNSHIP" in text  # the author's letter is untouched
    assert "Asha Rao" in text and "OFR-2026-AB12-001" in text and "Sri Venkateswara College" in text


def test_each_field_goes_on_its_own_page_and_other_pages_are_left_alone():
    layout = _layout(NAME, OfferField(key="date", page=2, x=0.2, y=0.2))
    pdf = build_offer_pdf(_pdf(2), layout, {"name": "Asha Rao", "date": "27 October 2026"})
    assert "Asha Rao" in _text(pdf, 0) and "27 October 2026" not in _text(pdf, 0)
    assert "27 October 2026" in _text(pdf, 1) and "Asha Rao" not in _text(pdf, 1)


def test_a_field_with_no_value_is_skipped_rather_than_printed_blank_or_as_none():
    layout = _layout(NAME, OfferField(key="reference", x=0.1, y=0.9))
    pdf = build_offer_pdf(_pdf(), layout, {"name": "Asha Rao", "reference": ""})
    assert "None" not in _text(pdf)


def test_the_page_size_does_not_matter_because_positions_are_fractions():
    landscape = build_offer_pdf(_pdf(size=(842, 595)), _layout(NAME), {"name": "Asha Rao"})
    letter = build_offer_pdf(_pdf(size=(612, 792)), _layout(NAME), {"name": "Asha Rao"})
    assert "Asha Rao" in _text(landscape) and "Asha Rao" in _text(letter)
    assert [float(x) for x in PdfReader(io.BytesIO(landscape)).pages[0].mediabox[2:]] == [842.0, 595.0]


def test_a_rotated_page_is_stamped_where_it_is_seen():
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(_pdf())))
    writer.pages[0].rotate(90)
    out = io.BytesIO()
    writer.write(out)
    pdf = build_offer_pdf(out.getvalue(), _layout(NAME), {"name": "Asha Rao"})
    assert "Asha Rao" in _text(pdf)


def test_a_long_name_shrinks_to_fit_instead_of_running_off_the_page():
    layout = _layout(OfferField(key="name", x=0.0, y=0.4, max_width=0.3, font_size=0.05))
    long_name = "Venkata Subrahmanya Satya Sai Rama Krishna Prasad Rao"
    pdf = build_offer_pdf(_pdf(), layout, {"name": long_name})
    assert long_name in " ".join(_text(pdf).split())


def test_names_with_accents_or_unsupported_letters_are_printed_as_plain_letters_not_boxes():
    assert safe_text("José  Müller") == "Jose Muller"
    assert safe_text("శ్రీనివాస్ Rao") == "Rao"
    assert safe_text("శ్రీనివాస్") == ""  # nothing drawable: the field is skipped, not printed as boxes
    pdf = build_offer_pdf(_pdf(), _layout(NAME), {"name": "José Müller"})
    assert "Jose Muller" in _text(pdf)


# -------------------------------------------------------------------- the email


def test_the_email_fills_its_placeholders_in_the_subject_and_body():
    values = {"full_name": "Asha Rao", "internship_title": "Cyber Internship", "institution": "SVC", "reference": "OFR-1"}
    subject, text, html = render_offer_email("Offer: {{ internship_title }}", "Hi {{full_name}}, ref {{reference}}.", values)
    assert subject == "Offer: Cyber Internship"
    assert text == "Hi Asha Rao, ref OFR-1."
    assert "Hi Asha Rao" in html


def test_the_standard_wording_is_used_when_nothing_was_written():
    values = {"full_name": "Asha Rao", "internship_title": "Cyber Internship", "institution": "SVC", "reference": "OFR-1"}
    subject, text, _ = render_offer_email(None, None, values)
    assert "Cyber Internship" in subject
    assert "Dear Asha Rao" in text and "OFR-1" in text
    assert "{{" not in text and "{{" in DEFAULT_BODY


def test_text_in_the_body_cannot_inject_html_into_the_email():
    _, _, html = render_offer_email("Hi", "<script>alert(1)</script> {{full_name}}", {"full_name": "<b>Asha</b>"})
    assert "<script>" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html


def test_paragraphs_and_line_breaks_are_kept_in_the_html():
    _, _, html = render_offer_email("Hi", "First paragraph.\n\nSecond line one\nSecond line two", {})
    assert html.count("<p ") == 2 and "<br>" in html


def test_a_subject_is_always_one_line():
    subject, _, _ = render_offer_email("Offer\nfor {{full_name}}", None, {"full_name": "Asha\nRao"})
    assert "\n" not in subject and subject == "Offer for Asha Rao"


def test_unknown_placeholders_are_found_so_a_typo_is_caught_when_saving():
    assert unknown_placeholders("Hi {{full_name}}", "{{fullname}} and {{ reference }} and {{nope}}") == ["fullname", "nope"]
    assert unknown_placeholders("", "plain text") == []


def test_the_attachment_name_is_safe_and_never_empty():
    assert attachment_name("Asha Rao") == "Internship_Offer_Asha_Rao.pdf"
    assert attachment_name("../../etc/passwd") == "Internship_Offer_etc_passwd.pdf"
    assert attachment_name("శ్రీ") == "Internship_Offer_student.pdf"
