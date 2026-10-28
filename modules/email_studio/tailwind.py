"""
A documented subset of Tailwind CSS (v3 defaults) turned into inline styles, for React Email code imported into Email Studio.

Nothing here runs Tailwind. Each class name is looked up in the tables below and becomes ordinary inline CSS, which is the only
styling most email clients honour. A class that has no email-safe equivalent (flex, grid, shadows, hover:, md:, dark:, ...) is
*returned* in ``unsupported`` so the importer can tell the author, instead of being dropped without a word.

Supported: spacing (padding, margin), width/height and their min/max, text size/colour/weight/alignment/transform/decoration,
line height, letter spacing, font family, background colour, borders (width, side, style, colour), border radius, display,
vertical alignment, opacity, overflow, white-space, list style. Colours are the default Tailwind palette plus ``[#hex]`` /
``[rgb()]`` values; lengths are the default scale plus ``[12px]`` / ``[50%]`` values.
"""

import re
from contextvars import ContextVar

PALETTE: dict[str, dict[int, str]] = {}


def _shades(name: str, values: str) -> None:
    PALETTE[name] = dict(zip((50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950), values.split()))


_shades("slate", "#f8fafc #f1f5f9 #e2e8f0 #cbd5e1 #94a3b8 #64748b #475569 #334155 #1e293b #0f172a #020617")
_shades("gray", "#f9fafb #f3f4f6 #e5e7eb #d1d5db #9ca3af #6b7280 #4b5563 #374151 #1f2937 #111827 #030712")
_shades("zinc", "#fafafa #f4f4f5 #e4e4e7 #d4d4d8 #a1a1aa #71717a #52525b #3f3f46 #27272a #18181b #09090b")
_shades("neutral", "#fafafa #f5f5f5 #e5e5e5 #d4d4d4 #a3a3a3 #737373 #525252 #404040 #262626 #171717 #0a0a0a")
_shades("red", "#fef2f2 #fee2e2 #fecaca #fca5a5 #f87171 #ef4444 #dc2626 #b91c1c #991b1b #7f1d1d #450a0a")
_shades("orange", "#fff7ed #ffedd5 #fed7aa #fdba74 #fb923c #f97316 #ea580c #c2410c #9a3412 #7c2d12 #431407")
_shades("amber", "#fffbeb #fef3c7 #fde68a #fcd34d #fbbf24 #f59e0b #d97706 #b45309 #92400e #78350f #451a03")
_shades("yellow", "#fefce8 #fef9c3 #fef08a #fde047 #facc15 #eab308 #ca8a04 #a16207 #854d0e #713f12 #422006")
_shades("green", "#f0fdf4 #dcfce7 #bbf7d0 #86efac #4ade80 #22c55e #16a34a #15803d #166534 #14532d #052e16")
_shades("emerald", "#ecfdf5 #d1fae5 #a7f3d0 #6ee7b7 #34d399 #10b981 #059669 #047857 #065f46 #064e3b #022c22")
_shades("teal", "#f0fdfa #ccfbf1 #99f6e4 #5eead4 #2dd4bf #14b8a6 #0d9488 #0f766e #115e59 #134e4a #042f2e")
_shades("cyan", "#ecfeff #cffafe #a5f3fc #67e8f9 #22d3ee #06b6d4 #0891b2 #0e7490 #155e75 #164e63 #083344")
_shades("sky", "#f0f9ff #e0f2fe #bae6fd #7dd3fc #38bdf8 #0ea5e9 #0284c7 #0369a1 #075985 #0c4a6e #082f49")
_shades("blue", "#eff6ff #dbeafe #bfdbfe #93c5fd #60a5fa #3b82f6 #2563eb #1d4ed8 #1e40af #1e3a8a #172554")
_shades("indigo", "#eef2ff #e0e7ff #c7d2fe #a5b4fc #818cf8 #6366f1 #4f46e5 #4338ca #3730a3 #312e81 #1e1b4b")
_shades("violet", "#f5f3ff #ede9fe #ddd6fe #c4b5fd #a78bfa #8b5cf6 #7c3aed #6d28d9 #5b21b6 #4c1d95 #2e1065")
_shades("purple", "#faf5ff #f3e8ff #e9d5ff #d8b4fe #c084fc #a855f7 #9333ea #7e22ce #6b21a8 #581c87 #3b0764")
_shades("pink", "#fdf2f8 #fce7f3 #fbcfe8 #f9a8d4 #f472b6 #ec4899 #db2777 #be185d #9d174d #831843 #500724")
_shades("rose", "#fff1f2 #ffe4e6 #fecdd3 #fda4af #fb7185 #f43f5e #e11d48 #be123c #9f1239 #881337 #4c0519")

_BASIC = {"black": "#000000", "white": "#ffffff", "transparent": "transparent", "current": "currentColor", "inherit": "inherit"}
_TEXT_SIZES = {
    "xs": ("12px", "16px"), "sm": ("14px", "20px"), "base": ("16px", "24px"), "lg": ("18px", "28px"), "xl": ("20px", "28px"),
    "2xl": ("24px", "32px"), "3xl": ("30px", "36px"), "4xl": ("36px", "40px"), "5xl": ("48px", "1"), "6xl": ("60px", "1"),
    "7xl": ("72px", "1"), "8xl": ("96px", "1"), "9xl": ("128px", "1"),
}
_WEIGHTS = {"thin": "100", "extralight": "200", "light": "300", "normal": "400", "medium": "500", "semibold": "600", "bold": "700", "extrabold": "800", "black": "900"}
_LEADING = {"none": "1", "tight": "1.25", "snug": "1.375", "normal": "1.5", "relaxed": "1.625", "loose": "2"}
_TRACKING = {"tighter": "-0.05em", "tight": "-0.025em", "normal": "0em", "wide": "0.025em", "wider": "0.05em", "widest": "0.1em"}
_RADIUS = {"none": "0px", "sm": "2px", "": "4px", "md": "6px", "lg": "8px", "xl": "12px", "2xl": "16px", "3xl": "24px", "full": "9999px"}
_MAX_W = {"none": "none", "xs": "320px", "sm": "384px", "md": "448px", "lg": "512px", "xl": "576px", "2xl": "672px", "3xl": "768px", "4xl": "896px", "5xl": "1024px", "6xl": "1152px", "7xl": "1280px", "full": "100%"}
_FAMILIES = {
    "sans": "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",
    "serif": "Georgia,Cambria,'Times New Roman',Times,serif",
    "mono": "Menlo,Monaco,Consolas,'Courier New',monospace",
}
_DISPLAY = {"block": "block", "inline-block": "inline-block", "inline": "inline", "hidden": "none", "table": "table", "table-cell": "table-cell", "table-row": "table-row"}
_SIDES = {"t": "top", "r": "right", "b": "bottom", "l": "left"}
_CORNERS = {
    "tl": ("top-left",), "tr": ("top-right",), "bl": ("bottom-left",), "br": ("bottom-right",),
    "t": ("top-left", "top-right"), "b": ("bottom-left", "bottom-right"), "l": ("top-left", "bottom-left"), "r": ("top-right", "bottom-right"),
}

_ARBITRARY = re.compile(r"^\[([^\[\]]+)\]$")
_LENGTH = re.compile(r"^-?\d*\.?\d+(px|rem|em|%|vw|vh)?$")
_COLOR_VALUE = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([\d\s.,%/]+\)|hsla?\([\d\s.,%/]+\))$")


class Unsupported(Exception):
    pass


# Colours from the template's own <Tailwind config> (theme.colors / theme.extend.colors), for the build in progress.
_EXTRA_COLORS: ContextVar[dict[str, str]] = ContextVar("tailwind_extra_colors", default={})
_ARBITRARY_PROPERTY = re.compile(r"^\[([a-z][a-z-]*):([^\[\]:;{}]+)\]$")
_SAFE_VALUE = re.compile(r"^[\w\s#%.,()/+-]+$")


def _arbitrary(value: str) -> str | None:
    match = _ARBITRARY.match(value)
    return match.group(1).replace("_", " ") if match else None


def _length(value: str, allow_auto: bool = False, allow_fraction: bool = True) -> str:
    """A Tailwind length token (4, 0.5, px, 1/2, full, [12px]) as CSS."""
    arbitrary = _arbitrary(value)
    if arbitrary is not None:
        if _LENGTH.match(arbitrary):
            return arbitrary if re.search(r"[a-z%]$", arbitrary) else arbitrary + "px"
        raise Unsupported
    if value == "px":
        return "1px"
    if value == "full":
        return "100%"
    if value == "auto" and allow_auto:
        return "auto"
    if allow_fraction and re.match(r"^\d+/\d+$", value):
        a, b = value.split("/")
        if int(b) == 0:
            raise Unsupported
        return f"{round(int(a) / int(b) * 100, 6):g}%"
    if re.match(r"^\d+(\.5)?$", value) and float(value) <= 96:
        number = float(value) * 4
        return f"{number:g}px"
    raise Unsupported


def _color(value: str) -> str:
    arbitrary = _arbitrary(value)
    if arbitrary is not None:
        if _COLOR_VALUE.match(arbitrary.replace(" ", "")) or arbitrary.lower() in _BASIC:
            return arbitrary
        raise Unsupported
    opacity = None
    if "/" in value:  # text-red-500/50
        value, _, raw = value.partition("/")
        if not raw.isdigit() or not 0 <= int(raw) <= 100:
            raise Unsupported
        opacity = int(raw) / 100
    extra = _EXTRA_COLORS.get()
    if value in _BASIC:
        found = _BASIC[value]
    elif value in extra:
        found = extra[value]
    else:
        match = re.match(r"^([a-z]+)-(\d{2,3})$", value)
        if not match or match.group(1) not in PALETTE or int(match.group(2)) not in PALETTE[match.group(1)]:
            raise Unsupported
        found = PALETTE[match.group(1)][int(match.group(2))]
    if opacity is not None and found.startswith("#") and len(found) == 7:
        r, g, b = int(found[1:3], 16), int(found[3:5], 16), int(found[5:7], 16)
        return f"rgba({r},{g},{b},{opacity:g})"
    return found


def _is_color(value: str) -> bool:
    try:
        _color(value)
        return True
    except Unsupported:
        return False


def resolve(class_name: str, colors: dict[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Inline styles for a Tailwind class list, and the classes that could not be turned into email-safe CSS. ``colors`` are extra
    colour names from the template's own Tailwind config."""
    styles: dict[str, str] = {}
    unsupported: list[str] = []
    token = _EXTRA_COLORS.set(colors or {})
    try:
        return _resolve(class_name, styles, unsupported)
    finally:
        _EXTRA_COLORS.reset(token)


def _resolve(class_name: str, styles: dict[str, str], unsupported: list[str]) -> tuple[dict[str, str], list[str]]:
    classes = [c for c in class_name.split() if c]
    # Tailwind applies p, then px/py, then pt/pr/pb/pl (and likewise for margin, border, radius): do the same, whatever the order written.
    classes.sort(key=_rank)
    for raw in classes:
        name = raw[1:] if raw.startswith("!") else raw
        if ":" in name and not name.startswith("["):
            unsupported.append(raw)  # md:, hover:, dark: ... have no inline equivalent
            continue
        try:
            _apply(name, styles)
        except Unsupported:
            unsupported.append(raw)
    return styles, unsupported


def _rank(name: str) -> int:
    base = name.lstrip("!-")
    head = base.split("-", 1)[0]
    if head in ("p", "m", "border", "rounded"):
        return 0
    if head in ("px", "py", "mx", "my"):
        return 1
    if head in ("pt", "pr", "pb", "pl", "mt", "mr", "mb", "ml") or re.match(r"^border-[trbl](-|$)", base) or re.match(r"^rounded-(t|r|b|l|tl|tr|bl|br)(-|$)", base):
        return 2
    return 0


def _apply(name: str, out: dict[str, str]) -> None:
    negative = name.startswith("-")
    body = name[1:] if negative else name
    prop_match = _ARBITRARY_PROPERTY.match(name)
    if prop_match:  # [border-left:1px_solid_#eee]: any email-safe CSS property
        from modules.email_studio.sanitize import _clean_style

        prop, value = prop_match.group(1), prop_match.group(2).replace("_", " ").strip()
        if not _SAFE_VALUE.match(value) or not _clean_style(f"{prop}:{value}"):
            raise Unsupported
        out[prop] = value
        return

    # spacing --------------------------------------------------------------
    match = re.match(r"^(p|m)([xytrbl]?)-(.+)$", body)
    if match:
        kind, axis, token = match.groups()
        if kind == "p" and (negative or token == "auto"):
            raise Unsupported
        value = _length(token, allow_auto=(kind == "m"), allow_fraction=False)
        if negative:
            if value == "auto":
                raise Unsupported
            value = "-" + value if not value.startswith("-") else value
        prop = "padding" if kind == "p" else "margin"
        if axis == "":
            out[prop] = value
        elif axis == "x":
            out[f"{prop}-left"] = out[f"{prop}-right"] = value
        elif axis == "y":
            out[f"{prop}-top"] = out[f"{prop}-bottom"] = value
        else:
            out[f"{prop}-{_SIDES[axis]}"] = value
        return
    if negative:
        raise Unsupported

    # sizing ---------------------------------------------------------------
    for prefix, prop in (("w", "width"), ("h", "height"), ("min-w", "min-width"), ("min-h", "min-height")):
        if body.startswith(prefix + "-"):
            token = body[len(prefix) + 1:]
            if prefix == "w" and token == "auto" or prefix == "h" and token == "auto":
                out[prop] = "auto"
            else:
                out[prop] = _length(token, allow_fraction=prefix in ("w", "h"))
            return
    if body.startswith("max-w-"):
        token = body[6:]
        out["max-width"] = _MAX_W[token] if token in _MAX_W else _length(token, allow_fraction=False)
        return
    if body.startswith("max-h-"):
        out["max-height"] = _length(body[6:], allow_fraction=False)
        return

    # text -----------------------------------------------------------------
    if body.startswith("text-"):
        token = body[5:]
        if token in ("left", "center", "right", "justify"):
            out["text-align"] = token
        elif token in _TEXT_SIZES:
            out["font-size"], out["line-height"] = _TEXT_SIZES[token]
        elif token in ("ellipsis", "clip", "wrap", "nowrap", "balance", "pretty"):
            raise Unsupported
        else:
            arbitrary = _arbitrary(token)
            if arbitrary is not None and _LENGTH.match(arbitrary) and not _is_color(token):
                out["font-size"] = arbitrary if re.search(r"[a-z%]$", arbitrary) else arbitrary + "px"
            else:
                out["color"] = _color(token)
        return
    if body.startswith("font-"):
        token = body[5:]
        if token in _WEIGHTS:
            out["font-weight"] = _WEIGHTS[token]
        elif token in _FAMILIES:
            out["font-family"] = _FAMILIES[token]
        else:
            raise Unsupported
        return
    if body.startswith("leading-"):
        token = body[8:]
        if token in _LEADING:
            out["line-height"] = _LEADING[token]
        elif _arbitrary(token) in ("normal", "inherit"):
            out["line-height"] = _arbitrary(token) or ""
        elif re.match(r"^\[\d*\.?\d+\]$", token):
            out["line-height"] = token[1:-1]  # a bare number is a multiple of the font size
        else:
            out["line-height"] = _length(token, allow_fraction=False)
        return
    if body.startswith("tracking-"):
        token = body[9:]
        if token in _TRACKING:
            out["letter-spacing"] = _TRACKING[token]
        else:
            out["letter-spacing"] = _length(token, allow_fraction=False)
        return
    simple = {
        "italic": ("font-style", "italic"), "not-italic": ("font-style", "normal"), "underline": ("text-decoration", "underline"),
        "no-underline": ("text-decoration", "none"), "line-through": ("text-decoration", "line-through"),
        "uppercase": ("text-transform", "uppercase"), "lowercase": ("text-transform", "lowercase"), "capitalize": ("text-transform", "capitalize"),
        "normal-case": ("text-transform", "none"), "whitespace-nowrap": ("white-space", "nowrap"), "whitespace-normal": ("white-space", "normal"),
        "whitespace-pre": ("white-space", "pre"), "whitespace-pre-wrap": ("white-space", "pre-wrap"), "break-words": ("word-wrap", "break-word"),
        "break-all": ("word-break", "break-all"), "align-top": ("vertical-align", "top"), "align-middle": ("vertical-align", "middle"),
        "align-bottom": ("vertical-align", "bottom"), "align-baseline": ("vertical-align", "baseline"), "overflow-hidden": ("overflow", "hidden"),
        "overflow-visible": ("overflow", "visible"), "box-border": ("box-sizing", "border-box"), "box-content": ("box-sizing", "content-box"),
        "list-none": ("list-style-type", "none"), "list-disc": ("list-style-type", "disc"), "list-decimal": ("list-style-type", "decimal"),
        "border-collapse": ("border-collapse", "collapse"), "table-fixed": ("table-layout", "fixed"), "table-auto": ("table-layout", "auto"),
    }
    if body in simple:
        out[simple[body][0]] = simple[body][1]
        return
    if body in _DISPLAY:
        out["display"] = _DISPLAY[body]
        return

    # colours, borders, radius, opacity -----------------------------------
    if body.startswith("bg-"):
        out["background-color"] = _color(body[3:])
        return
    if body.startswith("opacity-"):
        token = body[8:]
        if not token.isdigit() or int(token) > 100:
            raise Unsupported
        out["opacity"] = f"{int(token) / 100:g}"
        return
    if body.startswith("rounded"):
        rest = body[len("rounded"):]
        corner = None
        match = re.match(r"^-(tl|tr|bl|br|t|r|b|l)(?:-(.+))?$", rest)
        if match:
            corner, rest = match.group(1), ("-" + match.group(2)) if match.group(2) else ""
        size = rest[1:] if rest.startswith("-") else rest
        if rest and not rest.startswith("-"):
            raise Unsupported
        if size in _RADIUS:
            value = _RADIUS[size]
        else:
            arbitrary = _arbitrary(size)
            if arbitrary is None or not _LENGTH.match(arbitrary):
                raise Unsupported
            value = arbitrary if re.search(r"[a-z%]$", arbitrary) else arbitrary + "px"
        if corner is None:
            out["border-radius"] = value
        else:
            for part in _CORNERS[corner]:
                out[f"border-{part}-radius"] = value
        return
    if body.startswith("border-spacing-"):
        out["border-spacing"] = _length(body[15:], allow_fraction=False)
        return
    if body == "border" or body.startswith("border-"):
        _border(body, out)
        return
    raise Unsupported


def _border(body: str, out: dict[str, str]) -> None:
    rest = body[len("border"):]
    side = None
    match = re.match(r"^-([trbl])(?:-(.+))?$", rest)
    if match:
        side, rest = match.group(1), ("-" + match.group(2)) if match.group(2) else ""
    token = rest[1:] if rest.startswith("-") else rest
    prefix = f"border-{_SIDES[side]}" if side else "border"
    if rest and not rest.startswith("-"):
        raise Unsupported
    if token == "" or token in ("0", "2", "4", "8"):
        width = "1px" if token == "" else f"{token}px"
        out[f"{prefix}-width"] = width
        out.setdefault(f"{prefix}-style" if side else "border-style", "solid")
        if "border-color" not in out and not side:
            out["border-color"] = PALETTE["gray"][200]
        return
    if token in ("solid", "dashed", "dotted", "double", "none", "hidden"):
        out["border-style" if not side else f"{prefix}-style"] = token
        return
    arbitrary = _arbitrary(token)
    if arbitrary is not None and _LENGTH.match(arbitrary) and not _is_color(token):
        out[f"{prefix}-width"] = arbitrary if re.search(r"[a-z%]$", arbitrary) else arbitrary + "px"
        out.setdefault("border-style" if not side else f"{prefix}-style", "solid")
        return
    color = _color(token)
    out["border-color" if not side else f"{prefix}-color"] = color
