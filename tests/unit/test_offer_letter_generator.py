"""
The offer letter generator's pure parts: how settings merge, the wording, and the PDF it draws -- real text, two pages for the
reference content, more pages (never clipped text) for long content, optional sections only when switched on, and nothing
financial unless the admin approved it.
"""

import io

import pytest
from PIL import Image
from pypdf import PdfReader

from modules.our_internships import letter_config as lc
from modules.our_internships.letter_pdf import Asset, AssetError, StudentFacts, build_letter_pdf, validate_asset

COMPANY = {
    "name": "GIR Technologies", "address": "Ameerpet, Hyderabad", "phone": "+91 81438 94179", "email": "info@girtechnologies.com",
    "website": "www.girtechnologies.com", "signatory_name": "ATLURI SRUJAN", "signatory_designation": "CEO",
}
PROGRAMME = {
    "position": "Intern", "duration": "3 months", "start_date": "2026-03-13", "end_date": "2026-06-12",
    "phases": [{"label": "Month 1", "title": "Training & Skill Development"}, {"label": "Month 2", "title": "Task Assignment & Development"}],
}
FACTS = StudentFacts("SABAVATH ABHISHEK NAIK", "Apollo University", "Murukambattu, Andhra Pradesh", "abhi@example.com")


def config(**content):
    return lc.effective({"company": COMPANY, "programme": PROGRAMME, "content": content}, None)


def png(color=(200, 30, 30, 255), size=(120, 60)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, color).save(out, "PNG")
    return out.getvalue()


def make(cfg, facts=FACTS, assets=None):
    pdf, pages = build_letter_pdf(cfg, facts, assets or {}, "Cyber Internship", "OFR-2026-AB12-001", "27 October 2026")
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == pages
    return [" ".join(p.extract_text().split()) for p in reader.pages], pdf


# ------------------------------------------------------------------ settings


def test_settings_merge_defaults_then_overrides_and_only_the_differences_are_kept():
    defaults = {"company": COMPANY, "content": {"terms": ["Be on time."]}}
    merged = lc.effective(defaults, {"programme": {"position": "Analyst"}, "content": {"terms": ["Be on time.", "Be kind."]}})
    assert merged.company.name == "GIR Technologies" and merged.programme.position == "Analyst" and merged.content.terms == ["Be on time.", "Be kind."]
    base = lc.deep_merge(lc.code_defaults(), defaults)
    assert lc.difference(base, merged.model_dump(mode="json")) == {"programme": {"position": "Analyst"}, "content": {"terms": ["Be on time.", "Be kind."]}}


def test_an_unknown_placeholder_is_refused_and_a_known_one_is_filled():
    with pytest.raises(ValueError, match="not recognised"):
        lc.effective({"content": {"closing": "Hello {{nickname}}"}}, None)
    assert lc.fill("Dear {{student_name}} {{nope}}", {"student_name": "Asha"}) == "Dear Asha {{nope}}"


def test_the_end_date_cannot_be_before_the_start_date():
    with pytest.raises(ValueError, match="end date"):
        lc.effective({"programme": {"start_date": "2026-06-01", "end_date": "2026-05-01"}}, None)


def test_a_new_organisation_starts_with_nothing_financial_and_a_to_do_list():
    cfg = lc.effective(None, None)
    assert cfg.content.financial_note.active is False
    todo = lc.program_problems(cfg, "")
    assert "Enter the company name." in todo and "Enter the internship start date." in todo and "Enter the internship programme name." in todo
    assert lc.program_problems(config(), "Cyber") == []


def test_a_note_that_is_switched_on_but_not_approved_blocks_generation():
    cfg = config(financial_note={"enabled": True, "approved": False, "amount": "INR 2,000"})
    assert any("not approved" in p for p in lc.program_problems(cfg, "x"))


def test_text_the_fonts_cannot_print_is_found():
    assert lc.unprintable("Résumé café") == []
    assert lc.unprintable("आशा") != []
    assert any("cannot print" in p for p in lc.check_printable(config(closing="Go → now")))


# ------------------------------------------------------------------ the letter


def test_the_reference_content_makes_a_two_page_searchable_letter():
    cfg = config(guardian_required=True, documents=["A signed copy of this offer letter", "College ID card copy"], terms=["Follow all company policies."])
    pages, _ = make(cfg)
    assert len(pages) == 2
    first, second = pages
    assert "GIR Technologies" in first and "Ameerpet, Hyderabad" in first
    assert "TO, SABAVATH ABHISHEK NAIK Apollo University Murukambattu, Andhra Pradesh" in first
    assert "Subject: Internship Offer Letter - GIR Technologies" in first
    assert "After reviewing your performance during our recent Hackathon" in first
    assert "Position: Intern" in first and "Start Date: 13-03-2026" in first and "End Date: 12-06-2026" in first
    assert "Program Type: Unpaid Internship" in first
    assert "Month 1: Training & Skill Development" in first and "Month 2: Task Assignment & Development" in first
    assert "Documentation:" in second and "College ID card copy" in second and "Terms & Conditions:" in second
    assert "I, SABAVATH ABHISHEK NAIK, hereby accept the internship offer from GIR Technologies" in second
    assert "Signature of Student:" in second and "Signature of Parent/Guardian:" in second
    assert "ATLURI SRUJAN CEO GIR Technologies" in second


def test_the_selection_reason_changes_the_introduction_without_inventing_results():
    assert "recent Workshop" in make(config(selection_reason="workshop"))[0][0]
    assert "technical evaluation" in make(config(selection_reason="technical_evaluation"))[0][0]
    assert "selected by GIR Technologies" in make(config(selection_reason="direct_selection"))[0][0]
    custom = make(config(selection_reason="custom", custom_reason="Your work on the capstone impressed us."))[0][0]
    assert "Your work on the capstone impressed us." in custom and "Hackathon" not in custom
    own = make(config(introduction="Welcome aboard, {{student_name}}!"))[0][0]
    assert "Welcome aboard, SABAVATH ABHISHEK NAIK!" in own


def test_the_guardian_lines_appear_only_when_required():
    assert "Parent/Guardian" not in make(config(guardian_required=False))[0][1]
    assert "Parent/Guardian" in make(config(guardian_required=True))[0][1]


def test_the_financial_note_is_printed_only_when_switched_on_and_approved():
    note = {"enabled": True, "approved": True, "amount": "INR 2,000/-", "purpose": "tools and software", "refund_terms": "The charge is non-refundable"}
    text = " ".join(make(config(financial_note=note))[0])
    assert "INR 2,000/-" in text and "non-refundable" in text
    for off in ({"enabled": False, "approved": True}, {"enabled": True, "approved": False}):
        text = " ".join(make(config(financial_note={**note, **off}))[0])
        assert "INR" not in text and "refundable" not in text
    assert "INR" not in " ".join(make(config())[0])  # nothing financial by default


def test_a_paid_internship_shows_the_stipend_and_phases_can_be_any_length():
    programme = {**PROGRAMME, "program_type": "paid", "stipend": "INR 5,000 per month", "phases": [{"label": f"Week {i}", "title": f"Topic {i}"} for i in range(1, 7)]}
    text = make(lc.effective({"company": COMPANY, "programme": programme}, None))[0][0]
    assert "Program Type: Paid Internship" in text and "Stipend: INR 5,000 per month" in text and "Week 6: Topic 6" in text


def test_long_content_flows_onto_more_pages_and_nothing_is_cut():
    terms = [f"Clause {i}: " + "The intern agrees to follow the rules of the programme. " * 6 for i in range(1, 25)]
    pages, _ = make(config(terms=terms, notes=["Please keep this letter safe."]))
    assert len(pages) >= 3
    joined = " ".join(pages)
    assert "Clause 1:" in joined and "Clause 24:" in joined and "Please keep this letter safe." in joined
    assert "Acknowledgement and Acceptance" in joined and "Signature of Student:" in joined
    assert all(f"Page {i + 1} of {len(pages)}" in p for i, p in enumerate(pages))  # the footer is on every page


def test_long_names_wrap_instead_of_overflowing():
    name = "Venkata Satya Sai Subrahmanya Lakshmi Narasimha Rao Bandaru Ravichandra"
    college = "Sri Venkateswara University College of Engineering and Technology for Women"
    pages, _ = make(config(), StudentFacts(name, college, "Tirupati", "x@y.com"))
    assert name in pages[0] and college in pages[0]


def test_special_characters_in_names_are_kept_and_markup_is_not_interpreted():
    pages, _ = make(config(), StudentFacts("José <b>Müller</b> & Sons", "St. Mary's", "Köln", "x@y.com"))
    assert "José <b>Müller</b> & Sons" in pages[0]


def test_each_letter_contains_only_its_own_students_details():
    a, _ = make(config(), StudentFacts("Asha Rao", "College A", "City A", "a@x.com"))
    b, _ = make(config(), StudentFacts("Ravi Kumar", "College B", "City B", "b@x.com"))
    assert "Asha Rao" in a[0] and "Ravi" not in " ".join(a) and "College B" not in " ".join(a)
    assert "Ravi Kumar" in b[0] and "Asha" not in " ".join(b)


def test_images_are_placed_and_the_pdf_still_reads_as_text():
    colors = {"logo": (200, 30, 30, 255), "watermark": (30, 200, 30, 255), "signature": (30, 30, 200, 255), "stamp": (200, 200, 30, 255)}
    assets = {k: Asset(k, "image/png", png(c)) for k, c in colors.items()}  # different pictures, since identical ones are stored once
    cfg = config()
    cfg.branding.signature.show_stamp = True
    pages, pdf = make(cfg, assets=assets)
    reader = PdfReader(io.BytesIO(pdf))
    assert "GIR Technologies" in pages[0] and len(reader.pages[0].images) >= 2  # logo + watermark
    assert len(reader.pages[1].images) == 4  # watermark, signature, stamp and the small logo of a later page


def test_a_hidden_logo_and_watermark_are_left_out():
    assets = {k: Asset(k, "image/png", png()) for k in ("logo", "watermark")}
    cfg = config()
    cfg.branding.logo.show = False
    cfg.branding.watermark.show = False
    _, pdf = make(cfg, assets=assets)
    assert all(len(p.images) == 0 for p in PdfReader(io.BytesIO(pdf)).pages)


def test_the_watermark_can_be_limited_to_the_first_page():
    assets = {"watermark": Asset("watermark", "image/png", png())}
    cfg = config()
    cfg.branding.watermark.pages = "first"
    _, pdf = make(cfg, assets=assets)
    pages = PdfReader(io.BytesIO(pdf)).pages
    assert len(pages[0].images) == 1 and len(pages[1].images) == 0


# ------------------------------------------------------------------ uploaded images


def test_only_real_images_are_accepted():
    assert validate_asset("logo", png()) == "image/png"
    with pytest.raises(AssetError, match="not an image"):
        validate_asset("logo", b"%PDF-1.4 definitely not a picture")
    with pytest.raises(AssetError, match="empty"):
        validate_asset("logo", b"")
    with pytest.raises(AssetError, match="4 MB"):
        validate_asset("logo", b"x" * (4 * 1024 * 1024 + 1))


def test_an_svg_logo_is_accepted_and_drawn():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="#1f3a8a"/></svg>'
    assert validate_asset("logo", svg) == "image/svg+xml"
    pages, _ = make(config(), assets={"logo": Asset("logo", "image/svg+xml", svg), "watermark": Asset("watermark", "image/svg+xml", svg)})
    assert "GIR Technologies" in pages[0]
    with pytest.raises(AssetError):
        validate_asset("logo", b"<svg><not-closed")
