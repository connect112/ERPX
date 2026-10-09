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
import io
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_PATH = Path(__file__).parent / "fonts" / "Inter-Variable.ttf"
FONT_FAMILY = "Inter"
TEMPLATES = ("editorial", "statement", "photo", "screenshot")
CANVAS = {"image": (1080, 1350), "carousel": (1080, 1350), "reel": (1080, 1920), "story": (1080, 1920)}
MARGIN = 96
# Reel covers and Stories have the app's own controls at the top and bottom, and a Reel cover is cropped to 3:4 on the
# profile grid; text stays inside this vertical band.
TALL_SAFE_TOP = 250
TALL_SAFE_BOTTOM = 250
MIN_HEADLINE_PX = 56
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


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def palette_of(colors: dict) -> Palette:
    return Palette(**{key: hex_rgb(colors[key]) for key in ("background", "ink", "primary", "accent", "muted")})


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

    def texts(self) -> dict:
        return {"kicker": self.kicker, "headline": self.headline, "subline": self.subline, "credit": self.credit, "footer": self.footer_right, "index": self.index, "total": self.total}


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
    if post_format == "carousel":
        slides = content.get("slides") or []
        if not (2 <= len(slides) <= MAX_SLIDES):
            raise RenderError("A carousel needs 2 to 10 slides before its artwork can be made.")
        return [
            Spec(template, kicker if i == 0 else "", clean(slide.get("heading")), clean(slide.get("body")), credit if i == 0 else "", footer, i + 1, len(slides))
            for i, slide in enumerate(slides)
        ]
    headline = clean(design.get("headline")) or clean(content.get("headline")) or clean(title)
    if not headline:
        raise RenderError("Add a headline before making artwork.")
    return [Spec(template, kicker, headline, clean(design.get("subline")), credit, footer)]


def fingerprint(specs: list[Spec], design: dict) -> str:
    """A hash of exactly what an artwork shows. If the post's text or design changes, this no longer matches."""
    payload = {"specs": [s.texts() | {"template": s.template} for s in specs], "bg": design.get("background_asset_id"), "logo": bool(design.get("show_logo", True))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def current_fingerprint(post_format: str, content: dict, design: dict, title: str, pillar_label: str | None, brand: dict) -> str | None:
    """The fingerprint the post's text and design would give if rendered now (None if it can't be rendered)."""
    try:
        return fingerprint(specs_for(post_format, content, design, title, pillar_label, brand), design)
    except RenderError:
        return None


# ---------------- drawing ----------------


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


def _draw_block(ctx: _Ctx, fitted: Fitted, x: int, y: int, preferred: tuple[int, int, int], role: str, max_width: int) -> None:
    """Draw wrapped text at (x, y), choosing white or ink if the preferred colour lacks contrast with what is behind it."""
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


def _paste_logo(ctx: _Ctx, logo: Image.Image | None, y_bottom: int, dark_backdrop: bool) -> dict | None:
    """The approved logo, scaled and nothing else, on a light chip if the backdrop is dark. Returns where it went."""
    if logo is None:
        return None
    target_h = 96
    scale = target_h / logo.height
    size = (max(1, round(logo.width * scale)), target_h)
    if size[0] > 360:
        size = (360, max(1, round(logo.height * 360 / logo.width)))
    scaled = logo.resize(size, Image.LANCZOS)
    x, y = MARGIN, y_bottom - size[1]
    if dark_backdrop:
        pad = 14
        ctx.draw.rounded_rectangle((x - pad, y - pad, x + size[0] + pad, y + size[1] + pad), radius=18, fill=(255, 255, 255))
    ctx.image.paste(scaled, (x, y), scaled)
    return {"x": x, "y": y, "w": size[0], "h": size[1], "position": "bottom_left"}


def _footer(ctx: _Ctx, spec: Spec, logo: Image.Image | None, dark: bool, y_bottom: int, ink: tuple[int, int, int]) -> dict | None:
    placed = _paste_logo(ctx, logo, y_bottom, dark)
    right = spec.footer_right
    if spec.index and spec.total:
        right = f"{spec.index} / {spec.total}"
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
    dark_template = template in ("statement", "photo")
    if template == "statement":
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
    text_color = palette.background if template == "statement" else (255, 255, 255) if template == "photo" else palette.ink
    muted = (190, 198, 210) if dark_template else palette.muted
    accent = palette.accent if dark_template else palette.primary
    inner_w = w - 2 * MARGIN
    top = MARGIN + safe_top
    footer_bottom = h - MARGIN - safe_bottom
    footer_top = footer_bottom - 100
    y = top

    if spec.kicker:
        y += _tracked(ctx, spec.kicker, MARGIN, y, 28, muted if dark_template else palette.muted) + 18
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
            sub_fit = fit(spec.subline, inner_w, 260, 42, MIN_BODY_PX, 400, 5, 1.4, "supporting line")
            sub_h = sub_fit.height + 36
        if template == "photo":
            # type sits low, over the scrim
            room = footer_top - y - 60
            head = fit(spec.headline, inner_w, min(room - sub_h, int(h * 0.38)), 112, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline")
            block_h = head.height + sub_h
            y_head = footer_top - 40 - block_h
        else:
            room = footer_top - y - 40
            head = fit(spec.headline, inner_w, room - sub_h, 124, MIN_HEADLINE_PX, heading_weight, 6, 1.1, "headline")
            block_h = head.height + sub_h
            # optical centre of the free space, a little above the middle
            y_head = y + max(0, int((room - block_h) * 0.42))
        _draw_block(ctx, head, MARGIN, y_head, text_color, "headline", inner_w)
        if sub_fit:
            _draw_block(ctx, sub_fit, MARGIN, y_head + head.height + 28, muted, "subline", inner_w)

    logo = brand_logo if show_logo else None
    placed = _footer(ctx, spec, logo, dark_template, footer_bottom, muted if dark_template else palette.muted)
    return image, ctx, placed


def _dhash(image: Image.Image) -> str:
    small = image.convert("L").resize((9, 8), Image.LANCZOS)
    pixels = list(small.getdata())
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


def _trimmed(logo: Image.Image) -> Image.Image:
    """Cut away fully transparent margins around the logo. The logo's own pixels are not touched."""
    box = logo.getchannel("A").getbbox()
    return logo.crop(box) if box else logo


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
