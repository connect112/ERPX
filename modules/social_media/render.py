"""
Deterministic artwork: every word, shape and the logo is drawn by code (Pillow), never by an image model.

An image model may supply a photo or background, which is then darkened under a scrim, but it never draws text or the
logo. So the words on a cover are exactly the words in the post, the approved logo is placed pixel for pixel (only
scaled), and the same input always gives the same picture.

The design is deliberately plain: one idea per cover, left-aligned type in one family (Inter), generous margins, one
accent colour, nothing decorative. Each render is validated, and a cover that can't pass is reported, never trimmed
quietly:
- text must fit its box at a readable size (no clipping, no shrinking below the minimum)
- text must reach the contrast ratio set in the design rules, measured against the lightest and darkest parts of
  the picture behind it
- headline length and total cover text must stay within the design rules
- on Reel covers and Stories, text must stay inside the safe area that the app's own interface doesn't cover
"""

import hashlib
import random
import io
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from modules.social_media import icons

FONT_PATH = Path(__file__).parent / "fonts" / "Inter-Variable.ttf"
FONT_FAMILY = "Inter"
TEMPLATES = ("editorial", "statement", "photo", "screenshot", "neon", "split", "solid")
CANVAS = {"image": (1080, 1350), "carousel": (1080, 1350), "reel": (1080, 1920), "story": (1080, 1920)}
MARGIN = 96
# Reel covers and Stories have the app's own controls at the top and bottom, and a Reel cover is cropped to 3:4 on the
# profile grid; text stays inside this vertical band.
TALL_SAFE_TOP = 250
TALL_SAFE_BOTTOM = 250
MIN_HEADLINE_PX = 56
# A single image may carry an answer line under its headline. The headline keeps the design rule's own limit; the answer line gets
# this much extra room (about one sentence), so the cover stays short without forcing the answer back into the caption.
SUPPORT_ALLOWANCE = 80
MIN_BODY_PX = 34
MIN_KICKER_PX = 26
MAX_SLIDES = 10


class RenderError(Exception):
    """Something can't be drawn as asked (text too long for its box, a missing image ...). Safe to show."""


@dataclass
class Palette:
    background: tuple[int, int, int]
    ink: tuple[int, int, int]
    primary: tuple[int, int, int]
    accent: tuple[int, int, int]
    muted: tuple[int, int, int]
    accent2: tuple[int, int, int] = (6, 180, 215)  # the second brand colour (the logo's cyan); the first accent is its green


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def palette_of(colors: dict) -> Palette:
    values = {key: hex_rgb(colors[key]) for key in ("background", "ink", "primary", "accent", "muted")}
    if colors.get("accent2"):
        values["accent2"] = hex_rgb(colors["accent2"])
    return Palette(**values)


# ---------------- colour maths ----------------


def _channel(value: float) -> float:
    value /= 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _backdrop_extremes(image: Image.Image, box: tuple[int, int, int, int]) -> list[tuple[int, int, int]]:
    """The lightest and darkest typical colours (5th and 95th percentile of brightness) behind a text box."""
    crop = image.crop(box).convert("RGB")
    grey = crop.convert("L")
    histogram = grey.histogram()
    total = sum(histogram)
    cumulative, low, high = 0, 0, 255
    for level, count in enumerate(histogram):
        cumulative += count
        if cumulative >= total * 0.05 and low == 0:
            low = level
        if cumulative >= total * 0.95:
            high = level
            break
    return [(low, low, low), (high, high, high)]


# ---------------- type ----------------


@lru_cache(maxsize=64)
def font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    if not FONT_PATH.exists():
        raise RenderError("The artwork font is missing from this server.")
    loaded = ImageFont.truetype(str(FONT_PATH), size)
    loaded.set_variation_by_axes([min(32, max(14, size // 3)), weight])
    return loaded


def wrap(text: str, typeface: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """Greedy word wrap that also breaks a word longer than the line, so nothing can run past the box."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            while typeface.getlength(word) > width:
                cut = len(word)
                while cut > 1 and typeface.getlength(word[:cut]) > width:
                    cut -= 1
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:cut])
                word = word[cut:]
            trial = f"{current} {word}".strip()
            if typeface.getlength(trial) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


@dataclass
class Fitted:
    lines: list[str]
    size: int
    weight: int
    line_height: int

    @property
    def height(self) -> int:
        return self.line_height * len(self.lines)

    def width(self) -> int:
        face = font(self.size, self.weight)
        return int(max((face.getlength(line) for line in self.lines), default=0))


def fit(text: str, width: int, height: int, max_size: int, min_size: int, weight: int, max_lines: int, spacing: float, role: str) -> Fitted:
    """The largest size (between max and min) at which the text fits the box; an error if even the smallest doesn't."""
    for size in range(max_size, min_size - 1, -2):
        face = font(size, weight)
        lines = wrap(text, face, width)
        line_height = int(size * spacing)
        if len(lines) <= max_lines and line_height * len(lines) <= height:
            return Fitted(lines, size, weight, line_height)
    raise RenderError(
        f"The {role} is too long to fit at a readable size ({min_size}px). Shorten it; nothing is trimmed automatically."
    )


# ---------------- what gets drawn ----------------


def clean(text: str | None) -> str:
    return re.sub(r"[ \t]+", " ", (text or "").replace("\r", "")).strip()


@dataclass
class Spec:
    """Everything drawn on one image, decided before drawing (the texts are also what the post is checked against)."""

    template: str
    kicker: str
    headline: str
    subline: str
    credit: str
    footer_right: str
    index: int | None = None  # a carousel slide: 1-based position
    total: int | None = None
    seed: int = 0  # decides the look of the neon template (pattern, light, text position); the same for every slide of a post
    emphasis: str = ""  # words of the headline that get a highlighter marker behind them
    numeral: str = ""  # "02": a step number taken from a heading like "Step 2: ..." and drawn large above it
    icon: str = ""  # the illustration tile (see icons.py); when set the picture also gets the pill label and the swipe cue

    def texts(self) -> dict:
        return {"kicker": self.kicker, "headline": self.headline, "subline": self.subline, "credit": self.credit, "footer": self.footer_right, "index": self.index, "total": self.total, "emphasis": self.emphasis, "numeral": self.numeral, "icon": self.icon}


COVER_FRAME_MAX = 70  # a headline longer than this stays inside the first slide instead of getting its own cover
_STEP = re.compile(r"^(?:step\s*)?(\d{1,2})\s*[:.)\u2013-]\s*(\S.*)$", re.I)


def _plain(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _step_number(heading: str) -> tuple[str, str]:
    """"Step 2: Learn the basics" -> ("02", "Learn the basics"); anything else is left alone."""
    match = _STEP.match(heading)
    return (f"{int(match.group(1)):02d}", match.group(2)) if match else ("", heading)


def specs_for(post_format: str, content: dict, design: dict, title: str, pillar_label: str | None, brand: dict) -> list[Spec]:
    """One Spec per image: a single cover, or one per carousel slide. Raises RenderError if there is nothing to draw."""
    template = design.get("template") or "editorial"
    if template not in TEMPLATES:
        raise RenderError("Choose one of the available templates.")
    kicker = clean(design.get("kicker")) if design.get("kicker") is not None else clean(pillar_label)
    footer = ""
    if design.get("show_handle", True):
        footer = clean(brand.get("handle")) or clean(brand.get("tagline"))
    credit = clean(design.get("credit"))
    explicit = design.get("variant")
    seed = int(explicit) if isinstance(explicit, int) and not isinstance(explicit, bool) else int(hashlib.sha1(f"{title}|{content.get('headline') or ''}".encode()).hexdigest()[:8], 16)
    emphasis = clean(content.get("emphasis"))
    show_icon = bool(design.get("show_icon"))
    chosen = clean(content.get("icon"))
    if chosen not in icons.ICONS:
        chosen = ""
    if post_format == "carousel":
        slides = content.get("slides") or []
        if not (2 <= len(slides) <= MAX_SLIDES):
            raise RenderError("A carousel needs 2 to 10 slides before its artwork can be made.")
        parts: list[tuple[str, str, str, str]] = []  # (headline, body, numeral, icon) of every image
        main_icon = (chosen or icons.icon_for(clean(content.get("headline")), *[clean(sl.get("heading")) for sl in slides])) if show_icon else ""
        cover = clean(design.get("headline")) or clean(content.get("headline"))
        closing = clean(content.get("cta"))
        framed = bool(design.get("carousel_frame"))
        cover_wanted = framed and cover and len(cover) <= COVER_FRAME_MAX and _plain(cover) != _plain(slides[0].get("heading")) and len(slides) < MAX_SLIDES
        if cover_wanted:
            parts.append((cover, clean(content.get("support_line")) or ("" if show_icon else "Swipe to read"), "", main_icon))
        for slide in slides:
            numeral, heading = _step_number(clean(slide.get("heading")))
            slide_icon = icons.icon_for(heading, clean(slide.get("body")), default=main_icon) if show_icon else ""
            parts.append((heading, clean(slide.get("body")), numeral, slide_icon))
        if framed and closing and len(closing) <= 140 and len(parts) < MAX_SLIDES:
            # The closing slide: a short headline (the call to action if it is short, else "Save this for later."), the call to
            # action in full under it, and where to follow.
            short = len(closing.split()) <= 7
            handle = clean(brand.get("handle"))
            sub = ("" if short else closing) + (f" Follow {handle} for more." if handle else "")
            parts.append((closing if short else "Save this for later.", sub.strip(), "", main_icon))
        return [
            Spec(template, kicker if i == 0 else "", h, b, credit if i == 0 else "", footer, i + 1, len(parts), seed, emphasis, n, ic)
            for i, (h, b, n, ic) in enumerate(parts)
        ]
    headline = clean(design.get("headline")) or clean(content.get("headline")) or clean(title)
    if not headline:
        raise RenderError("Add a headline before making artwork.")
    # The answer line: the design's own supporting line, else the one the studio wrote for the post.
    subline = clean(design.get("subline")) if design.get("subline") is not None else clean(content.get("support_line"))
    single_icon = (chosen or icons.icon_for(headline, subline)) if show_icon else ""
    return [Spec(template, kicker, headline, subline, credit, footer, None, None, seed, emphasis, "", single_icon)]


def fingerprint(specs: list[Spec], design: dict) -> str:
    """A hash of exactly what an artwork shows. If the post's text or design changes, this no longer matches."""
    payload = {"specs": [s.texts() | {"template": s.template} for s in specs], "bg": design.get("background_asset_id"), "logo": bool(design.get("show_logo", True)), "variant": design.get("variant")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def current_fingerprint(post_format: str, content: dict, design: dict, title: str, pillar_label: str | None, brand: dict) -> str | None:
    """The fingerprint the post's text and design would give if rendered now (None if it can't be rendered)."""
    try:
        return fingerprint(specs_for(post_format, content, design, title, pillar_label, brand), design)
    except RenderError:
        return None


# ---------------- drawing ----------------


# ---------------- the brand-dark "neon" look: a circuit motif and glow that differ from post to post ----------------

ANCHORS = (0.14, 0.42, 0.70)  # where the headline block sits in the free space: high, middle, low
GLOWS = ((0.86, 0.10), (0.10, 0.08), (0.92, 0.44))  # soft light, kept away from the footer so a black-background logo blends in


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


# ---------------- flat colour looks: "solid" (the whole picture one brand colour) and "split" (a colour panel over a dark base) ----------------

INK_ON_COLOUR = (8, 12, 10)
MUTED_ON_COLOUR = (24, 34, 28)


def _flat_colour(palette: Palette, seed: int) -> tuple[int, int, int]:
    """One of the brand colours (green, lime, cyan), chosen per post, so the same look is not the same colour twice in a row."""
    return (palette.accent, palette.accent2, palette.primary)[(seed // 2) % 3]


HERO_D = 720  # diameter of the big flat circle on a cover; it bleeds off the right and bottom edges


def _hero_circle(image: Image.Image, cx: int, cy: int, d: int, fill: tuple[int, int, int]) -> None:
    """A flat circle with smooth edges (drawn at double size and scaled down); parts outside the picture are simply cut off."""
    w, h = image.size
    big = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(big).ellipse(((cx - d // 2) * 2, (cy - d // 2) * 2, (cx + d // 2) * 2, (cy + d // 2) * 2), fill=255)
    image.paste(fill, (0, 0), big.resize((w, h), Image.LANCZOS))


def _readable(ctx: "_Ctx", x: int, y: int, preferred: tuple[int, int, int]) -> tuple[int, int, int]:
    """The preferred colour, or white or black if what is behind (x, y) would make it hard to see."""
    behind = ctx.image.getpixel((min(max(x, 0), ctx.w - 1), min(max(y, 0), ctx.h - 1)))[:3]
    return max((preferred, (255, 255, 255), (0, 0, 0)), key=lambda c: (contrast_ratio(c, behind) >= ctx.min_ratio, c == preferred, contrast_ratio(c, behind)))


def _gradient_bar(ctx: "_Ctx", x: int, y: int, width: int, height: int, start: tuple[int, int, int], end: tuple[int, int, int]) -> None:
    for i in range(width):
        ctx.draw.line((x + i, y, x + i, y + height - 1), fill=_mix(start, end, i / max(1, width - 1)))


def _neon_base(canvas: tuple[int, int], palette: Palette, seed: int, safe_top: int) -> Image.Image:
    """Dark background, a faint glow and a few thin circuit traces in the top corner. The shapes come from `seed`, so every post
    gets its own pattern while staying recognisably the same brand. Everything is drawn at low strength: text stays readable."""
    w, h = canvas
    rng = random.Random(seed)
    base = Image.new("RGB", canvas, palette.ink)
    gx, gy = GLOWS[seed % len(GLOWS)]
    glow = Image.new("RGBA", canvas, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    radius = int(w * 0.42)
    cx, cy = int(w * gx), int(h * gy)
    gd.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*_mix(palette.accent, palette.accent2, 0.5), 58))
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 2))
    base.paste(glow, (0, 0), glow)

    traces = Image.new("RGBA", canvas, (0, 0, 0, 0))
    td = ImageDraw.Draw(traces)
    x0, x1 = int(w * 0.50), w - 56
    y0, y1 = safe_top + 56, safe_top + int(h * 0.19)
    for n in range(rng.randint(5, 8)):
        colour = (*(palette.accent if n % 2 == 0 else palette.accent2), 96)
        x = x1 - rng.randint(0, 40)
        y = rng.randint(y0, y1)
        for _ in range(rng.randint(2, 4)):
            step = rng.randint(50, 150)
            nx = max(x0, x - step)
            td.line((x, y, nx, y), fill=colour, width=4)
            x = nx
            turn = rng.choice((-1, 0, 1))
            if turn and x > x0 + 30:
                dy = turn * rng.randint(30, 70)
                ny = min(y1, max(y0, y + dy))
                nx2 = max(x0, x - abs(ny - y))
                td.line((x, y, nx2, ny), fill=colour, width=4)
                x, y = nx2, ny
        r = rng.randint(8, 13)
        if rng.random() < 0.7:
            td.ellipse((x - r, y - r, x + r, y + r), outline=colour, width=4)
        else:
            td.rectangle((x - r, y - r, x + r, y + r), fill=colour)
    base.paste(traces, (0, 0), traces)
    return base


@dataclass
class Rendered:
    png: bytes
    width: int
    height: int
    sha256: str
    metrics: dict
    validation: dict
    slide: int = 0


@dataclass
class _Ctx:
    image: Image.Image
    draw: ImageDraw.ImageDraw
    palette: Palette
    rules: dict
    safe_top: int
    safe_bottom: int
    checks: list[dict] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    min_ratio: float = 4.5

    @property
    def w(self) -> int:
        return self.image.width

    @property
    def h(self) -> int:
        return self.image.height


def _marked_words(lines: list[str], phrase: str) -> set[tuple[int, int]]:
    """(line, word) positions of the first place the phrase appears in the wrapped lines, ignoring case and punctuation."""
    words = [(li, wi, re.sub(r"[^\w]", "", w).lower()) for li, line in enumerate(lines) for wi, w in enumerate(line.split())]
    target = [re.sub(r"[^\w]", "", w).lower() for w in phrase.split()]
    target = [t for t in target if t]
    if not target:
        return set()
    for start in range(len(words) - len(target) + 1):
        if [w[2] for w in words[start:start + len(target)]] == target:
            return {(w[0], w[1]) for w in words[start:start + len(target)]}
    return set()


def _draw_block(ctx: _Ctx, fitted: Fitted, x: int, y: int, preferred: tuple[int, int, int], role: str, max_width: int, marker: tuple[tuple[int, int, int], str] | None = None) -> None:
    """Draw wrapped text at (x, y), choosing white or ink if the preferred colour lacks contrast with what is behind it.
    `marker` = (colour, phrase): the phrase gets a highlighter-style box in that colour with black or white text on it."""
    face = font(fitted.size, fitted.weight)
    box = (max(0, x - 8), max(0, y - 8), min(ctx.w, x + max_width + 8), min(ctx.h, y + fitted.height + 8))
    backdrops = _backdrop_extremes(ctx.image, box)
    candidates = [preferred, (255, 255, 255), ctx.palette.ink, (0, 0, 0)]
    chosen, best = preferred, 0.0
    for candidate in candidates:
        worst = min(contrast_ratio(candidate, b) for b in backdrops)
        if worst >= ctx.min_ratio:
            chosen, best = candidate, worst
            break
        if worst > best:
            chosen, best = candidate, worst
    marked = _marked_words(fitted.lines, marker[1]) if marker else set()
    if marked and marker:
        on_marker = max(((0, 0, 0), (255, 255, 255)), key=lambda c: contrast_ratio(c, marker[0]))
        pad = max(6, fitted.size // 10)
        for i, line in enumerate(fitted.lines):
            words = line.split()
            top = y + i * fitted.line_height
            cursor = 0
            segments: list[tuple[int, str, bool]] = []  # (x offset, text, marked)
            for wi, word in enumerate(words):
                offset = int(face.getlength(line[:cursor])) if cursor else 0
                segments.append((offset, word, (i, wi) in marked))
                cursor += len(word) + 1
            run = [seg for seg in segments if seg[2]]
            if run:
                left = x + run[0][0] - pad
                right = x + run[-1][0] + int(face.getlength(run[-1][1].rstrip(".,;:!?)\"'"))) + pad
                ctx.draw.rounded_rectangle((left, top + int(fitted.size * 0.06), right, top + int(fitted.line_height * 0.98)), radius=max(6, fitted.size // 8), fill=marker[0])
            for offset, word, is_marked in segments:
                ctx.draw.text((x + offset, top), word, font=face, fill=on_marker if is_marked else chosen)
    else:
        for i, line in enumerate(fitted.lines):
            ctx.draw.text((x, y + i * fitted.line_height), line, font=face, fill=chosen)
    ctx.blocks.append(
        {
            "role": role,
            "text": "\n".join(fitted.lines),
            "size_px": fitted.size,
            "box": [x, y, x + fitted.width(), y + fitted.height],
            "contrast": round(best, 2),
            "contrast_ok": best >= ctx.min_ratio,
            "inside_safe_area": y >= ctx.safe_top and y + fitted.height <= ctx.h - ctx.safe_bottom or role == "footer",
        }
    )


def _tracked(ctx: _Ctx, text: str, x: int, y: int, size: int, color: tuple[int, int, int]) -> int:
    """Upper-case kicker with a little letter-spacing; returns its height."""
    face = font(size, 600)
    upper = text.upper()
    width = int(sum(face.getlength(c) + size * 0.08 for c in upper))
    # Measure what is behind the text before drawing on it.
    backdrops = _backdrop_extremes(ctx.image, (x, y, min(ctx.w, x + width), y + size))
    ratio = 0.0
    for candidate in (color, ctx.palette.ink, (255, 255, 255), (0, 0, 0)):
        worst = min(contrast_ratio(candidate, b) for b in backdrops)
        if worst > ratio:
            color, ratio = candidate, worst
        if worst >= ctx.min_ratio:
            color, ratio = candidate, worst
            break
    cursor = float(x)
    for char in upper:
        ctx.draw.text((cursor, y), char, font=face, fill=color)
        cursor += face.getlength(char) + size * 0.08
    ctx.blocks.append(
        {
            "role": "kicker",
            "text": upper,
            "size_px": size,
            "box": [x, y, int(cursor), y + int(size * 1.2)],
            "contrast": round(ratio, 2),
            "contrast_ok": ratio >= ctx.min_ratio,
            "inside_safe_area": y >= ctx.safe_top,
        }
    )
    return int(size * 1.2)


def _dimmed(image: Image.Image, factor: float) -> Image.Image:
    return image if factor >= 1.0 else Image.eval(image, lambda v: int(v * factor))


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.LANCZOS, centering=(0.5, 0.5))


def _logo_has_dark_background(logo: Image.Image) -> bool:
    """True for a logo that comes with its own solid dark background (a black rectangle): it belongs on a dark design as it is."""
    w, h = logo.size
    corners = [logo.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    return all(c[3] > 250 and luminance(c[:3]) < 0.03 for c in corners)


def _black_to_transparent(logo: Image.Image) -> Image.Image:
    """Turns a logo's black background into transparency, so its glow blends into a dark design instead of showing as a box.
    Each pixel is treated as colour over black: the brightest channel is the opacity and the colour is that pixel at full strength."""
    rgba = logo.convert("RGBA")
    pixels = []
    for r, g, b, a in rgba.getdata():
        m = max(r, g, b)
        if m < 8 or a == 0:
            pixels.append((0, 0, 0, 0))
        else:
            pixels.append((min(255, r * 255 // m), min(255, g * 255 // m), min(255, b * 255 // m), m * a // 255))
    out = Image.new("RGBA", rgba.size)
    out.putdata(pixels)
    return out


def _paste_logo(ctx: _Ctx, logo: Image.Image | None, y_bottom: int, dark_backdrop: bool) -> dict | None:
    """The approved logo, scaled and nothing else, on a light chip if the backdrop is dark (unless the logo already has its own
    dark background). Returns where it went."""
    if logo is None:
        return None
    own_dark = bool(logo.info.get(OWN_DARK_BACKGROUND))
    blend = bool(dark_backdrop and own_dark)  # on a dark design its black melts into the design
    plate = bool(own_dark and not dark_backdrop)  # on a light or colour design it sits on a clean black rounded plate, like a badge
    target_h, max_w = 112, 360
    if blend:
        dark_backdrop = False
        target_h, max_w = 150, 400  # such a logo has fine detail (a tagline), so it needs more room to be readable
    elif plate:
        target_h, max_w = 128, 380
    scale = target_h / logo.height
    size = (max(1, round(logo.width * scale)), target_h)
    if size[0] > max_w:
        size = (max_w, max(1, round(logo.height * max_w / logo.width)))
    scaled = logo.resize(size, Image.LANCZOS)
    if blend:
        scaled = _black_to_transparent(scaled)
    x, y = MARGIN, y_bottom - size[1]
    if dark_backdrop or plate:
        pad = 14
        ctx.draw.rounded_rectangle((x - pad, y - pad, x + size[0] + pad, y + size[1] + pad), radius=18, fill=(0, 0, 0) if plate else (255, 255, 255))
    ctx.image.paste(scaled, (x, y), scaled)
    return {"x": x, "y": y, "w": size[0], "h": size[1], "position": "bottom_left"}


def _footer(ctx: _Ctx, spec: Spec, logo: Image.Image | None, dark: bool, y_bottom: int, ink: tuple[int, int, int]) -> dict | None:
    placed = _paste_logo(ctx, logo, y_bottom, dark)
    right = spec.footer_right
    if spec.index and spec.total:
        right = f"{spec.index} / {spec.total}"
    if spec.icon and spec.index == 1 and spec.total and spec.total > 1:
        # the cover tells you to swipe: the word and an arrow
        cue = fit("Swipe", ctx.w // 2 - MARGIN, 60, 32, MIN_KICKER_PX, 600, 1, 1.2, "swipe cue")
        arrow_x = ctx.w - MARGIN - 40
        text_x = arrow_x - 16 - cue.width()
        _draw_block(ctx, cue, text_x, y_bottom - cue.height, ink, "footer", cue.width())
        cy = y_bottom - cue.height // 2
        arrow = _readable(ctx, arrow_x + 18, cy, ink)
        ctx.draw.line((arrow_x, cy, arrow_x + 38, cy), fill=arrow, width=5)
        ctx.draw.line((arrow_x + 24, cy - 13, arrow_x + 38, cy, arrow_x + 24, cy + 13), fill=arrow, width=5, joint="curve")
        return placed
    if right:
        fitted = fit(right, ctx.w // 2 - MARGIN, 60, 30, MIN_KICKER_PX, 500, 1, 1.2, "footer text")
        x = ctx.w - MARGIN - fitted.width()
        _draw_block(ctx, fitted, x, y_bottom - fitted.height, ink, "footer", fitted.width())
    return placed


def _scrim(image: Image.Image, strength: float = 0.88) -> Image.Image:
    """A dark gradient rising from the bottom so type stays readable over any picture."""
    w, h = image.size
    overlay = Image.new("L", (1, h))
    for y in range(h):
        t = max(0.0, (y - h * 0.15) / (h * 0.85))
        overlay.putpixel((0, y), int(255 * strength * min(1.0, t**1.4)))
    mask = overlay.resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), (8, 10, 16)), image.convert("RGB"), mask)


def _draw_image(spec: Spec, brand_logo: Image.Image | None, background: Image.Image | None, palette: Palette, rules: dict, canvas: tuple[int, int], post_format: str, show_logo: bool, dim: float = 1.0) -> tuple[Image.Image, _Ctx, dict | None]:
    w, h = canvas
    tall = h > w * 1.4
    safe_top = TALL_SAFE_TOP if tall else 0
    safe_bottom = TALL_SAFE_BOTTOM if tall else 0
    template = spec.template
    dark_template = template in ("statement", "photo", "neon", "split")
    footer_bottom = h - MARGIN - safe_bottom
    footer_top = footer_bottom - 100
    flat = _flat_colour(palette, spec.seed)
    panel_bottom = footer_bottom - 198  # "split": the colour panel ends above the logo
    if template == "neon":
        image = _neon_base(canvas, palette, spec.seed, safe_top)
    elif template == "solid":
        image = Image.new("RGB", canvas, flat)
    elif template == "split":
        image = Image.new("RGB", canvas, palette.ink)
        ImageDraw.Draw(image).rectangle((0, 0, w, panel_bottom), fill=flat)
    elif template == "statement":
        image = Image.new("RGB", canvas, palette.ink)
    elif template == "photo":
        if background is None:
            raise RenderError("The Photo template needs a picture. Choose one from the library.")
        image = _scrim(_dimmed(_cover(background, canvas), dim))
    elif template == "screenshot" and background is None:
        raise RenderError("The Screenshot template needs a screenshot. Choose one from the library.")
    else:
        image = Image.new("RGB", canvas, palette.background)
    ctx = _Ctx(image, ImageDraw.Draw(image), palette, rules, safe_top, safe_bottom, min_ratio=float(rules.get("min_contrast_ratio", 4.5)))
    text_color = palette.background if template == "statement" else (255, 255, 255) if template in ("photo", "neon") else palette.ink
    muted = (190, 198, 210) if dark_template else palette.muted
    accent = palette.accent if dark_template else palette.primary
    footer_ink = muted
    if template in ("solid", "split"):
        text_color, muted, accent = INK_ON_COLOUR, MUTED_ON_COLOUR, INK_ON_COLOUR
        footer_ink = MUTED_ON_COLOUR if template == "solid" else (190, 198, 210)
    inner_w = w - 2 * MARGIN
    top = MARGIN + safe_top
    y = top

    pro = bool(spec.icon)
    cover = not spec.index or spec.index == 1
    pro_inner = pro and bool(spec.index) and spec.index > 1
    if spec.kicker and pro:
        face = font(26, 600)
        label_w = int(sum(face.getlength(c) + 26 * 0.08 for c in spec.kicker.upper()))
        pill = (MARGIN, y, MARGIN + label_w + 52, y + 26 + 30)
        ctx.draw.rounded_rectangle(pill, radius=(pill[3] - pill[1]) // 2, outline=accent, width=3)
        _tracked(ctx, spec.kicker, MARGIN + 26, y + 13, 26, muted)
        y += (pill[3] - pill[1]) + 40
    elif spec.kicker:
        y += _tracked(ctx, spec.kicker, MARGIN, y, 28, muted) + 18
        if template == "neon":
            _gradient_bar(ctx, MARGIN, y, 120, 8, palette.accent, palette.accent2)
        else:
            ctx.draw.rectangle((MARGIN, y, MARGIN + 96, y + 8), fill=accent)
        y += 8 + 44

    heading_weight = 700
    sub_fit = None
    if template == "screenshot":
        shot_h = int((footer_top - y) * 0.56)
        shot_box = (inner_w, shot_h)
        shot = ImageOps.contain(background.convert("RGB"), shot_box, method=Image.LANCZOS)
        sx = MARGIN + (inner_w - shot.width) // 2
        ctx.draw.rectangle((sx - 3, y - 3, sx + shot.width + 3, y + shot.height + 3), outline=palette.muted, width=2)
        ctx.image.paste(shot, (sx, y))
        y += shot.height + 28
        if spec.credit:
            credit = fit(spec.credit, inner_w, 50, 28, MIN_KICKER_PX, 500, 1, 1.2, "credit line")
            _draw_block(ctx, credit, MARGIN, y, palette.muted, "credit", inner_w)
            y += credit.height + 24
        head = fit(spec.headline, inner_w, footer_top - y - 20, 72, MIN_HEADLINE_PX, heading_weight, 3, 1.14, "headline")
        _draw_block(ctx, head, MARGIN, y, text_color, "headline", inner_w)
        if spec.subline:
            y2 = y + head.height + 16
            sub_fit = fit(spec.subline, inner_w, footer_top - y2 - 10, 38, MIN_BODY_PX, 400, 2, 1.35, "supporting line")
            _draw_block(ctx, sub_fit, MARGIN, y2, muted, "subline", inner_w)
    else:
        has_sub = bool(spec.subline)
        sub_h = 0
        if has_sub:
            sub_fit = fit(spec.subline, inner_w, 300 if pro_inner else 260, 50 if pro_inner else 42, MIN_BODY_PX, 400, 6 if pro_inner else 5, 1.4, "supporting line")
            sub_h = sub_fit.height + 36
        hero_d = 0
        hero_cx = hero_cy = 0
        if pro and template != "photo":
            # The illustrated look keeps all text clear of the logo (and its badge) and leaves room for the illustration on a cover.
            clear = panel_bottom - 36 if template == "split" else footer_bottom - 214
            if pro_inner:
                free_top = top + 132 + 28
                y_head = free_top + int((clear - free_top) * 0.26) + (60 if spec.numeral else 0)
                avail = clear - y_head
                if has_sub:
                    sub_fit = fit(spec.subline, inner_w, min(340, int(avail * 0.55)), 54, MIN_BODY_PX, 400, 6, 1.4, "supporting line")
                    sub_h = sub_fit.height + 36
                head = fit(spec.headline, inner_w, avail - sub_h, 140, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline")
            else:
                y_head = y + 6
                avail = clear - y_head
                biggest = 148 if (cover and spec.total) else 124
                hero_cx, hero_cy = w - 150, h - 230 - safe_bottom
                try:
                    # the headline stays above the big circle
                    head = fit(spec.headline, inner_w, hero_cy - HERO_D // 2 - 36 - y_head - sub_h, biggest, MIN_HEADLINE_PX, 800, 6, 1.08, "headline")
                    hero_d = HERO_D
                except RenderError:
                    head = fit(spec.headline, inner_w, avail - sub_h - 290, biggest, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline") if avail - sub_h - 290 > 0 else fit(spec.headline, inner_w, avail - sub_h, biggest, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline")
            block_h = head.height + sub_h
            room = clear - y - 40
        elif template == "photo":
            # type sits low, over the scrim
            room = footer_top - y - 60
            head = fit(spec.headline, inner_w, min(room - sub_h, int(h * 0.38)), 112, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline")
            block_h = head.height + sub_h
            y_head = footer_top - 40 - block_h
        else:
            room = (panel_bottom if template == "split" else footer_top) - y - 40
            head = fit(spec.headline, inner_w, room - sub_h, 148 if (pro and cover and spec.total) else 124, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline")
            block_h = head.height + sub_h
            # optical centre of the free space, a little above the middle
            varied = template in ("neon", "solid", "split")
            anchor = ANCHORS[(spec.seed // 4) % len(ANCHORS)] if varied else 0.42
            if varied and spec.index:
                # carousel slides: the heading starts at the same height on every slide, so the text doesn't jump when swiping
                y_head = y + int(room * 0.22)
            elif pro and cover:
                y_head = y + 6  # text high, the illustration below it
            else:
                y_head = y + max(0, int((room - block_h) * anchor))
            if pro_inner:
                # centred between the tile row and the footer, a little above the middle; the same height on every slide
                free_top = top + 132 + 28
                y_head = free_top + int((footer_bottom - 214 - free_top) * 0.20)
                if spec.numeral:
                    y_head += 60
        hero_on_dark = False
        if hero_d:
            if template in ("neon", "statement"):
                hero_fill, hero_on_dark = (palette.accent, palette.accent2)[(spec.seed // 2) % 2], False
            elif template == "split":
                hero_fill, hero_on_dark = palette.ink, True
            else:
                hero_fill, hero_on_dark = INK_ON_COLOUR, True
            _hero_circle(ctx.image, hero_cx, hero_cy, hero_d, hero_fill)
        marker = None
        if spec.emphasis:
            marker = ((INK_ON_COLOUR if template in ("solid", "split") else palette.accent), spec.emphasis)
        if spec.numeral:
            numeral_size = 104
            if y_head - numeral_size - 8 < y:
                y_head = y + numeral_size + 8
            ctx.draw.text((MARGIN, y_head - numeral_size - 8), spec.numeral, font=font(numeral_size, 800), fill=(INK_ON_COLOUR if template in ("solid", "split") else (palette.accent if dark_template else palette.primary)))
        _draw_block(ctx, head, MARGIN, y_head, text_color, "headline", inner_w, marker)
        text_bottom = y_head + head.height
        if sub_fit:
            _draw_block(ctx, sub_fit, MARGIN, y_head + head.height + 28, muted, "subline", inner_w)
            text_bottom += 28 + sub_fit.height
        if pro:
            g0, g1 = palette.accent, palette.accent2
            if spec.index and spec.index > 1:
                icons.draw_tile(ctx.image, spec.icon, w - MARGIN - 132, top, 132, g0, g1)
            elif hero_d:
                size = 340
                ix, iy = hero_cx - 90 - size // 2, hero_cy - 110 - size // 2
                # on a light circle the icon is flat black, on a dark circle it carries the brand gradient
                icons.draw_icon(ctx.image, spec.icon, ix, iy, size, *((g0, g1) if hero_on_dark else (INK_ON_COLOUR, INK_ON_COLOUR)))
            else:
                # On the left the tile must clear the logo; on the right there is more room, down to the footer line.
                on_left = spec.seed % 2 == 0
                region_bottom = (panel_bottom if template == "split" else footer_bottom - (214 if on_left else 96)) - 24
                free = region_bottom - text_bottom - 44
                size = min(free, 560)
                if size >= 190:
                    tx = MARGIN if on_left else w - MARGIN - size
                    icons.draw_tile(ctx.image, spec.icon, tx, text_bottom + 44 + (free - size) // 2, size, g0, g1)

    if spec.index and spec.total and spec.total > 1:
        # carousel progress: a bar along the bottom edge that fills as you swipe, so every slide says where it is in the set
        bar = INK_ON_COLOUR if template in ("solid",) else (palette.accent if dark_template else palette.primary)
        ctx.draw.rectangle((0, h - 12, int(w * spec.index / spec.total), h), fill=bar)

    logo = brand_logo if show_logo else None
    placed = _footer(ctx, spec, logo, dark_template, footer_bottom, footer_ink if template in ("solid", "split") else (muted if dark_template else palette.muted))
    return image, ctx, placed


def _dhash(image: Image.Image) -> str:
    small = image.convert("L").resize((9, 8), Image.LANCZOS)
    pixels = list(small.tobytes())  # 8-bit greyscale: one byte per pixel (works on every Pillow version)
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return f"{bits:016x}"


def _metrics(image: Image.Image, spec: Spec, ctx: _Ctx, placed_logo: dict | None) -> dict:
    mean = image.resize((1, 1), Image.BOX).getpixel((0, 0))
    return {
        "template": spec.template,
        "dominant": "#%02x%02x%02x" % mean,
        "luminance": round(luminance(mean), 3),
        "dhash": _dhash(image),
        "text_chars": len(spec.headline) + len(spec.subline),
        "headline": spec.headline,
        "headline_px": next((b["size_px"] for b in ctx.blocks if b["role"] == "headline"), None),
        "logo": placed_logo["position"] if placed_logo else None,
    }


def _validate(spec: Spec, ctx: _Ctx, canvas: tuple[int, int], placed_logo: dict | None, cover: bool, brand_has_logo: bool) -> dict:
    rules = ctx.rules
    problems: list[str] = []
    notes: list[str] = []
    headline_words = len(spec.headline.split())
    if rules.get("max_headline_words") and headline_words > rules["max_headline_words"]:
        problems.append(f"The headline has {headline_words} words; the design rules allow {rules['max_headline_words']}.")
    limit = int(rules.get("max_cover_text_chars", 90))
    allowed = limit if cover and not spec.index else limit * 3
    if cover and not spec.index and spec.subline:
        allowed += SUPPORT_ALLOWANCE
        if len(spec.headline) > limit:
            problems.append(f"The headline has {len(spec.headline)} characters; the design rules allow {limit} for the cover.")
    used = len(spec.headline) + len(spec.subline)
    if used > allowed:
        problems.append(f"There are {used} characters of text on this image; the design rules allow {allowed}.")
    low = [b for b in ctx.blocks if not b.get("contrast_ok", True)]
    for b in low:
        problems.append(f"The {b['role']} text has contrast {b['contrast']}:1; at least {ctx.min_ratio}:1 is required.")
    outside = [b for b in ctx.blocks if not b.get("inside_safe_area", True)]
    if outside:
        problems.append("Some text is outside the area the Instagram interface leaves clear.")
    if brand_has_logo and not placed_logo:
        notes.append("The logo was left off this design.")
    if not brand_has_logo:
        notes.append("No approved logo is uploaded, so none is shown.")
    return {
        "ok": not problems,
        "problems": problems,
        "notes": notes,
        "dimensions": list(canvas),
        "fonts": [FONT_FAMILY],
        "text_fits": True,
        "min_font_px": min((b["size_px"] for b in ctx.blocks), default=None),
        "min_contrast": min((b["contrast"] for b in ctx.blocks if "contrast" in b), default=None),
        "blocks": [{k: b[k] for k in ("role", "size_px", "contrast")} for b in ctx.blocks],
        "rendered_text": {"headline": spec.headline, "subline": spec.subline, "kicker": spec.kicker},
    }


OWN_DARK_BACKGROUND = "own_dark_background"


def _trimmed(logo: Image.Image) -> Image.Image:
    """Cut away fully transparent margins around the logo. The logo's own pixels are not touched. Whether the logo brings its own
    dark background is decided before the cut: afterwards a dark mark would look as if it did."""
    own_dark = _logo_has_dark_background(logo)
    box = logo.getchannel("A").getbbox()
    out = logo.crop(box) if box else logo
    out.info[OWN_DARK_BACKGROUND] = own_dark
    return out


def load_image(raw: bytes, what: str) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:  # noqa: BLE001 - any decoder problem means the stored file is unusable
        raise RenderError(f"The {what} couldn't be read. Upload it again.") from None
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.mode or image.info.get("transparency") else "RGB")
    return image


def render(
    post_format: str,
    content: dict,
    design: dict,
    title: str,
    pillar_label: str | None,
    brand: dict,
    rules: dict,
    logo_bytes: bytes | None,
    background_bytes: bytes | None,
) -> tuple[list[Rendered], str]:
    """Draw the post's images. Returns them and the fingerprint of what they show."""
    specs = specs_for(post_format, content, design, title, pillar_label, brand)
    canvas = CANVAS.get(post_format, CANVAS["image"])
    palette = palette_of(brand["colors"])
    logo = _trimmed(load_image(logo_bytes, "logo").convert("RGBA")) if logo_bytes else None
    background = load_image(background_bytes, "picture") if background_bytes else None
    show_logo = bool(design.get("show_logo", True))
    out: list[Rendered] = []
    for i, spec in enumerate(specs):
        image, ctx, placed = _draw_image(spec, logo, background, palette, rules, canvas, post_format, show_logo)
        if spec.template == "photo" and any(not b.get("contrast_ok", True) for b in ctx.blocks):
            # A busy picture can make type hard to read; darken it step by step until the contrast is enough.
            for factor in (0.8, 0.65, 0.5, 0.38):
                image, ctx, placed = _draw_image(spec, logo, background, palette, rules, canvas, post_format, show_logo, dim=factor)
                if all(b.get("contrast_ok", True) for b in ctx.blocks):
                    break
        validation = _validate(spec, ctx, canvas, placed, cover=(i == 0), brand_has_logo=logo is not None)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()
        out.append(Rendered(data, image.width, image.height, hashlib.sha256(data).hexdigest(), _metrics(image, spec, ctx, placed), validation, slide=i))
    return out, fingerprint(specs, design)
