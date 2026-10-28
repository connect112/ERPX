"""
`{{placeholders}}` in designed emails: what exists, what a template uses, and filling them in safely.

Values are escaped for the place they land: text is HTML-escaped, an attribute is attribute-escaped, and a link or image
address must be http(s), mailto or tel (images http(s) only), so a student's name or a typed value can never add markup or a
script. A few component placeholders (`{{signature}}`, `{{brand_header}}`, `{{brand_footer}}`) stand for a whole block and are
swapped for it once; using one twice is reported.
"""

import html as html_lib
import re
from dataclasses import dataclass
from urllib.parse import urlparse

VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
PROP = re.compile(r"\{\{\s*prop:([a-z_][a-z0-9_]*)\s*\}\}")
COMPONENT_NAMES = ("signature", "brand_header", "brand_footer")

# (group, name, description, sample). The names that an ERPX email supplies come from its template definition
# (`packages/email/registry.py`); these add the groups and the ones Email Studio fills itself.
_GROUP_OF = {
    "full_name": "Account", "verification_url": "Account", "reset_url": "Account", "set_password_url": "Account", "login_url": "Account",
    "student_name": "Student", "student_email": "Student", "registration_id": "Student",
    "institution_name": "Institution", "institution_location": "Institution",
    "hackathon_title": "Event", "exam_title": "Event", "exam_url": "Event", "duration_minutes": "Event", "place": "Event",
    "internship_name": "Internship", "internship_position": "Internship", "internship_duration": "Internship",
    "internship_start_date": "Internship", "internship_end_date": "Internship", "program_type": "Internship",
    "company_name": "Company", "company_website": "Company", "company_email": "Company", "company_phone": "Company",
    "company_address": "Company", "brand_name": "Company", "logo_url": "Company", "authorized_signatory": "Company",
    "authorized_designation": "Company",
    "reference": "Documents", "letter_date": "Documents", "certificate_type": "Documents",
    "current_year": "System", "period_label": "System", "review_url": "System", "title": "System", "body": "System", "scope_label": "System",
}
GROUP_ORDER = ("Account", "Student", "Institution", "Event", "Internship", "Company", "Documents", "System")

# Values Email Studio supplies itself from the chosen brand and signature (a sender's own value wins).
BRAND_NAMES = (
    "company_name", "company_website", "company_email", "company_phone", "company_address", "brand_name", "logo_url",
    "authorized_signatory", "authorized_designation", "current_year",
)
# Whole-block placeholders and the names an image or link must come from
URL_NAMES = {"verification_url", "reset_url", "set_password_url", "login_url", "exam_url", "review_url", "company_website", "logo_url"}


@dataclass(frozen=True)
class PlaceholderInfo:
    name: str
    group: str
    description: str
    sample: str


def group_of(name: str) -> str:
    return _GROUP_OF.get(name, "System")


def placeholders_in(*texts: str | None) -> list[str]:
    """Every {{placeholder}} name used in these texts, in order of first use, without repeats."""
    seen: list[str] = []
    for text in texts:
        for match in VAR.finditer(text or ""):
            if match.group(1) not in seen:
                seen.append(match.group(1))
    return seen


def props_in(*texts: str | None) -> list[str]:
    seen: list[str] = []
    for text in texts:
        for match in PROP.finditer(text or ""):
            if match.group(1) not in seen:
                seen.append(match.group(1))
    return seen


def component_misuse(html: str) -> list[str]:
    """Problems with whole-block placeholders: used more than once (a duplicate header or signature)."""
    problems: list[str] = []
    for name in COMPONENT_NAMES:
        count = len(re.findall(r"\{\{\s*" + name + r"\s*\}\}", html or ""))
        if count > 1:
            problems.append("{{" + name + "}} is used " + str(count) + " times; use it once.")
    return problems


# ------------------------------------------------------------------ escaping

_SCHEMES_LINK = {"http", "https", "mailto", "tel"}
_SCHEMES_IMAGE = {"http", "https"}


def safe_url(value: object, image: bool = False) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        scheme = urlparse(text).scheme.lower()
    except ValueError:
        return ""
    allowed = _SCHEMES_IMAGE if image else _SCHEMES_LINK
    return text if scheme in allowed else ""


def _in_tag(source: str, position: int) -> bool:
    return source.rfind("<", 0, position) > source.rfind(">", 0, position)


def _attribute_name(source: str, position: int) -> str:
    tag = source[source.rfind("<", 0, position) : position]
    match = re.search(r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*[\"'][^\"']*$", tag)
    return match.group(1).lower() if match else ""


def fill_html(markup: str, values: dict[str, object], blocks: dict[str, str] | None = None) -> str:
    """The HTML with its placeholders filled in. ``blocks`` holds the HTML of component placeholders. A name with no value is
    replaced by nothing; check `missing()` first when that matters."""
    out = markup
    for name, block in (blocks or {}).items():
        # a block placeholder on its own in a paragraph or cell replaces the whole paragraph
        out = re.sub(r"(?is)<p\b[^>]*>\s*\{\{\s*" + name + r"\s*\}\}\s*</p\s*>", lambda _m, b=block: b, out, count=1)
        out = re.sub(r"\{\{\s*" + name + r"\s*\}\}", lambda _m, b=block: b, out, count=1)
    parts: list[str] = []
    last = 0
    for match in VAR.finditer(out):
        parts.append(out[last : match.start()])
        value = values.get(match.group(1))
        raw = "" if value is None else str(value)
        if _in_tag(out, match.start()):
            attr = _attribute_name(out, match.start())
            if attr in ("href", "src", "background"):
                prefix = out[out.rfind("<", 0, match.start()) : match.start()]
                # the placeholder is the whole address (the address is checked), or it sits after a typed scheme/path
                whole = re.search(r"=\s*[\"']$", prefix) is not None
                raw = safe_url(raw, image=attr in ("src", "background")) if whole else raw
            parts.append(html_lib.escape(raw, quote=True))
        else:
            parts.append(html_lib.escape(raw, quote=False).replace("\n", "<br />"))
        last = match.end()
    parts.append(out[last:])
    return "".join(parts)


def fill_text(text: str, values: dict[str, object]) -> str:
    return VAR.sub(lambda m: "" if values.get(m.group(1)) is None else str(values.get(m.group(1))), text or "")


def fill_subject(subject: str, values: dict[str, object]) -> str:
    """One line, placeholders filled, no way to add a header: line breaks and control characters become spaces."""
    filled = fill_text(subject, values)
    return " ".join(re.sub(r"[\x00-\x1f\x7f  ]", " ", filled).split())


def fill_props(markup: str, props: dict[str, object]) -> str:
    """The {{prop:name}} tokens of an approved code template, replaced by the administrator's values (escaped for where they
    land, link properties checked)."""
    out: list[str] = []
    last = 0
    for match in PROP.finditer(markup):
        out.append(markup[last : match.start()])
        value = props.get(match.group(1), "")
        raw = "" if value is None else str(value)
        if _in_tag(markup, match.start()):
            attr = _attribute_name(markup, match.start())
            if attr in ("href", "src"):
                whole = re.search(r"=\s*[\"']$", markup[markup.rfind("<", 0, match.start()) : match.start()]) is not None
                raw = safe_url(raw, image=attr == "src") if whole else raw
            out.append(html_lib.escape(raw, quote=True))
        else:
            out.append(html_lib.escape(raw, quote=False).replace("\n", "<br />"))
        last = match.end()
    out.append(markup[last:])
    return "".join(out)


def missing(names: list[str], values: dict[str, object], required: tuple[str, ...] = ()) -> list[str]:
    """Placeholders the email uses that have no value (or, for required ones, an empty value)."""
    gone: list[str] = []
    for name in names:
        if name in COMPONENT_NAMES:
            continue
        value = values.get(name)
        if value is None or (name in required and str(value).strip() == ""):
            gone.append(name)
    return gone


def unsupported(names: list[str], allowed: set[str]) -> list[str]:
    return [n for n in names if n not in allowed and n not in COMPONENT_NAMES]
