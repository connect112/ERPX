"""
Making email HTML safe to store and send.

Designed HTML arrives from the browser (the visual editor's export) or from an import, so it is never trusted: scripts, event
handlers, forms, frames, risky links and risky CSS are removed, comments are dropped, and only the *body* is kept. The page around
it (doctype, meta tags and a small responsive style block) is written here, not taken from the input.

`{{placeholders}}` are left alone: they are filled in at send time, with values escaped for where they land
(see `placeholders.py`).
"""

import html as html_lib
import json
import re

import nh3

MAX_HTML_BYTES = 600_000
MAX_JSON_BYTES = 600_000
MAX_JSON_DEPTH = 40
MAX_JSON_NODES = 8000

_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "center", "code", "col", "colgroup", "div", "em", "h1", "h2", "h3", "h4", "h5",
    "h6", "hr", "i", "img", "li", "ol", "p", "pre", "s", "small", "span", "strike", "strong", "sub", "sup", "table", "tbody", "td",
    "tfoot", "th", "thead", "tr", "u", "ul",
}
_GLOBAL_ATTRS = {"style", "dir", "lang", "align", "valign", "width", "height", "bgcolor", "title", "role", "colspan", "rowspan"}
_ATTRS = {
    "*": _GLOBAL_ATTRS,
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height", "border"},
    "table": {"border", "cellpadding", "cellspacing"},
    "td": {"background"},
}
# CSS properties that may stay in a style attribute. Layout and type only; nothing that can position over the mail client.
_STYLE_PROPS = {
    "background", "background-color", "background-image", "background-position", "background-repeat", "background-size", "border",
    "border-bottom", "border-bottom-color", "border-bottom-left-radius", "border-bottom-right-radius", "border-bottom-style",
    "border-bottom-width", "border-collapse", "border-color", "border-left", "border-left-color", "border-left-style",
    "border-left-width", "border-radius", "border-right", "border-right-color", "border-right-style", "border-right-width",
    "border-spacing", "border-style", "border-top", "border-top-color", "border-top-left-radius", "border-top-right-radius",
    "border-top-style", "border-top-width", "border-width", "box-sizing", "color", "direction", "display", "font", "font-family",
    "font-size", "font-style", "font-variant", "font-weight", "height", "letter-spacing", "line-height", "list-style",
    "list-style-type", "margin", "margin-bottom", "margin-left", "margin-right", "margin-top", "max-height", "max-width",
    "min-height", "min-width", "mso-line-height-rule", "mso-padding-alt", "mso-table-lspace", "mso-table-rspace", "opacity",
    "overflow", "padding", "padding-bottom", "padding-left", "padding-right", "padding-top", "table-layout", "text-align",
    "text-decoration", "text-decoration-line", "text-indent", "text-transform", "vertical-align", "white-space", "width",
    "word-break", "word-spacing", "word-wrap", "overflow-wrap",
}
_DISPLAYS = {"block", "inline", "inline-block", "table", "table-cell", "table-row", "none", "list-item", "inline-table"}
_BAD_CSS = re.compile(r"(?i)(expression\s*\(|javascript:|vbscript:|@import|behavior\s*:|-moz-binding|\\[0-9a-f]{2,}|<|>)")
_SAFE_URL_FN = re.compile(r"(?i)^url\(\s*['\"]?(https://[^)'\"\s]+|\{\{[^)'\"\s]+\}\})['\"]?\s*\)$")
_PLACEHOLDER_START = re.compile(r"^\s*(https?://)?\{\{\s*[A-Za-z_]")
_URL_OK = re.compile(r"(?i)^(https?://|mailto:|tel:|#)")
_SRC_OK = re.compile(r"(?i)^https?://")


def _clean_style(value: str) -> str:
    """The declarations of a style attribute that are safe: a known property, and no scripts or unknown URLs in the value."""
    kept: list[str] = []
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        prop, _, val = declaration.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        if prop not in _STYLE_PROPS or not val or _BAD_CSS.search(val):
            continue
        if "url(" in val.lower() and not all(_SAFE_URL_FN.match(part.strip()) for part in re.findall(r"url\([^)]*\)", val, re.I)):
            continue
        if prop == "display" and val.lower() not in _DISPLAYS:
            continue
        kept.append(f"{prop}:{val}")
    return ";".join(kept)


def _attribute_filter(tag: str, attr: str, value: str) -> str | None:
    if attr == "style":
        return _clean_style(value) or None
    if attr == "href":
        v = value.strip()
        return v if (_URL_OK.match(v) or _PLACEHOLDER_START.match(v)) else None
    if attr in ("src", "background"):
        v = value.strip()
        return v if (_SRC_OK.match(v) or _PLACEHOLDER_START.match(v)) else None
    if attr == "target":
        return "_blank" if value in ("_blank", "_self") else None
    if attr == "role":
        return value if value in ("presentation", "article", "banner", "none") else None
    return value


def extract_body(document: str) -> str:
    """What is inside <body> (or the whole text when there is no body tag)."""
    match = re.search(r"<body\b[^>]*>(.*)</body\s*>", document, re.I | re.S)
    return match.group(1) if match else document


def body_style(document: str) -> str:
    """The cleaned style attribute of the <body> tag, so a page background colour survives."""
    match = re.search(r"<body\b[^>]*?\bstyle\s*=\s*(\"([^\"]*)\"|'([^']*)')", document, re.I | re.S)
    if not match:
        return ""
    return _clean_style(html_lib.unescape(match.group(2) or match.group(3) or ""))


def sanitize_fragment(markup: str) -> str:
    """Safe email HTML with everything unsafe removed."""
    return nh3.clean(
        markup,
        tags=_TAGS,
        attributes=_ATTRS,
        attribute_filter=_attribute_filter,
        filter_style_properties=_STYLE_PROPS,
        url_schemes={"http", "https", "mailto", "tel"},
        strip_comments=True,
        link_rel="noopener noreferrer",
        clean_content_tags={"script", "style", "title", "head"},
    )


_SHELL_STYLE = (
    "body{margin:0;padding:0;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}"
    "table{border-collapse:collapse}img{border:0;max-width:100%;height:auto}"
    "@media only screen and (max-width:600px){.erpx-container{width:100%!important}img{height:auto!important}}"
    "@media (prefers-color-scheme:dark){li::marker{color:#c4c4c4}}"
)


def wrap_document(fragment: str, title: str = "", preheader: str = "", page_style: str = "", lang: str = "en") -> str:
    """A complete email page around safe body HTML. The wrapper is ours, so it carries no input from the template author."""
    hidden = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{html_lib.escape(preheader)}'
        + "&nbsp;&zwnj;" * 30
        + "</div>"
        if preheader.strip()
        else ""
    )
    style_attr = f' style="{html_lib.escape(page_style, quote=True)}"' if page_style else ""
    return (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
        f'<html dir="ltr" lang="{html_lib.escape(lang, quote=True)}"><head>'
        '<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        '<meta name="x-apple-disable-message-reformatting" />'
        '<meta name="color-scheme" content="light dark" />'
        f"<title>{html_lib.escape(title)}</title><style>{_SHELL_STYLE}</style></head>"
        f"<body{style_attr}>{hidden}{fragment}</body></html>"
    )


def sanitize_document(markup: str, title: str = "", preheader: str = "") -> str:
    """Take designed or imported HTML (a full page or a fragment) and return a safe, complete email page."""
    if len(markup.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("The email is too large (over 600 KB of HTML).")
    return wrap_document(sanitize_fragment(extract_body(markup)), title, preheader, body_style(markup))


# ------------------------------------------------------------------ plain text


def html_to_text(markup: str) -> str:
    """A readable plain-text version of email HTML: links keep their address, blocks become paragraphs."""
    body = extract_body(markup)
    body = re.sub(r"(?is)<(script|style|head|title)\b.*?</\1\s*>", "", body)
    body = re.sub(r'(?is)<a\b[^>]*?href\s*=\s*"([^"]*)"[^>]*>(.*?)</a\s*>', lambda m: _link_text(m.group(1), m.group(2)), body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?i)</(p|div|h[1-6]|tr|li|table|blockquote)\s*>", "\n", body)
    body = re.sub(r"(?i)<hr\b[^>]*>", "\n----\n", body)
    body = re.sub(r"(?i)</t[dh]\s*>", " ", body)
    body = re.sub(r"(?s)<[^>]+>", "", body)
    text = html_lib.unescape(body).replace("\xa0", " ").replace("‌", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def _link_text(href: str, inner: str) -> str:
    label = re.sub(r"(?s)<[^>]+>", "", inner).strip()
    href = html_lib.unescape(href).strip()
    if not label or label == href:
        return href
    return f"{label} ({href})"


# ------------------------------------------------------------------ the editor's saved document


def validate_editor_json(doc: object) -> dict:
    """Check a saved editor document before it is stored or rendered: the right shape, bounded size and depth, and no script
    addresses in any attribute. Returns the document (unchanged) or raises ValueError."""
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        raise ValueError("The saved design is not a valid editor document.")
    if len(json.dumps(doc)) > MAX_JSON_BYTES:
        raise ValueError("The design is too large.")
    count = 0

    def walk(node: object, depth: int) -> None:
        nonlocal count
        if depth > MAX_JSON_DEPTH:
            raise ValueError("The design is nested too deeply.")
        if not isinstance(node, dict):
            raise ValueError("The saved design has an invalid block.")
        count += 1
        if count > MAX_JSON_NODES:
            raise ValueError("The design has too many blocks.")
        if not isinstance(node.get("type"), str):
            raise ValueError("The saved design has a block without a type.")
        for key in ("attrs",):
            attrs = node.get(key)
            if attrs is not None and not isinstance(attrs, dict):
                raise ValueError("The saved design has invalid settings on a block.")
            for name, value in (attrs or {}).items():
                if isinstance(value, str) and re.match(r"(?i)\s*(javascript|vbscript|data):", value):
                    raise ValueError(f"The design contains an unsafe link in '{name}'.")
        for mark in node.get("marks") or []:
            if not isinstance(mark, dict) or not isinstance(mark.get("type"), str):
                raise ValueError("The saved design has an invalid format mark.")
            for name, value in (mark.get("attrs") or {}).items():
                if isinstance(value, str) and re.match(r"(?i)\s*(javascript|vbscript|data):", value):
                    raise ValueError(f"The design contains an unsafe link in '{name}'.")
        content = node.get("content")
        if content is not None:
            if not isinstance(content, list):
                raise ValueError("The saved design has invalid content.")
            for child in content:
                walk(child, depth + 1)

    walk(doc, 0)
    return doc
