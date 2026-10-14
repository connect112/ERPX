"""
Small, flat, brand-coloured icons for the artwork, drawn in code (no image files, nothing fetched, nothing AI-made).

Each icon is a shape drawn in white on a black mask in a 100 x 100 box at 4x size and scaled down, so its edges are smooth. The mask
is then filled with the brand gradient (the logo's green to cyan) and set on a dark rounded tile with a fine dot grid. The icon is
chosen from the post's own words, so a post about phishing gets an envelope and a post about logs gets a stack of log lines.
It is decoration: it never carries information the text does not already carry.
"""

import re

from PIL import Image, ImageDraw

SS = 4  # supersampling factor
ICONS = ("shield", "lock", "key", "magnifier", "mail", "network", "logs", "bug", "bolt", "terminal")

_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"phish|e-?mail|inbox|sender|scam|spam|smish|vish", "mail"),
    (r"password|passkey|credential|login|log in|mfa|2fa|authenticat|otp|brute", "key"),
    (r"encrypt|crypto|tls|ssl|https|vpn|hash|certificate", "lock"),
    (r"siem|\blogs?\b|logging|soc\b|monitor|telemetry|splunk|elk|detect", "logs"),
    (r"vulnerab|\bcve|exploit|malware|ransom|virus|trojan|bug\b|zero.?day|payload", "bug"),
    (r"patch|update|alert|urgent|incident|breach|outage", "bolt"),
    (r"network|packet|port\b|firewall|nmap|scan|dns|wireshark|router|topolog|zero.?trust", "network"),
    (r"command|linux|bash|shell|script|terminal|cli\b|kali|lab\b", "terminal"),
    (r"pentest|hunt|investigat|osint|recon|audit|forensic|analy", "magnifier"),
)


def icon_for(*texts: str, default: str = "shield") -> str:
    """The icon that fits the words, or the default (a shield)."""
    blob = " ".join(t for t in texts if t).lower()
    for pattern, name in _KEYWORDS:
        if re.search(pattern, blob):
            return name
    return default


def _line(d: ImageDraw.ImageDraw, points: list[tuple[float, float]], width: float, fill: int, s: float) -> None:
    pts = [(x * s, y * s) for x, y in points]
    d.line(pts, fill=fill, width=round(width * s), joint="curve")
    r = width * s / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _mask(name: str, size: int) -> Image.Image:
    """The icon as an L mask of `size` x `size` (255 = icon)."""
    big = size * SS
    s = big / 100
    img = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        return (x0 * s, y0 * s, x1 * s, y1 * s)

    def rrect(x0, y0, x1, y1, r, fill=255, outline=None, width=0):
        d.rounded_rectangle(box(x0, y0, x1, y1), radius=r * s, fill=fill, outline=outline, width=round(width * s))

    if name == "shield":
        d.polygon([(x * s, y * s) for x, y in [(50, 5), (88, 19), (88, 47), (82, 66), (68, 82), (50, 95), (32, 82), (18, 66), (12, 47), (12, 19)]], fill=255)
        _line(d, [(31, 49), (44, 62), (70, 35)], 10, 0, s)
    elif name == "lock":
        d.arc(box(30, 10, 70, 60), 180, 360, fill=255, width=round(10 * s))
        d.rectangle(box(30, 34, 40, 50), fill=255)
        d.rectangle(box(60, 34, 70, 50), fill=255)
        rrect(18, 42, 82, 94, 9)
        d.ellipse(box(43, 59, 57, 73), fill=0)
        d.rectangle(box(47, 66, 53, 82), fill=0)
    elif name == "key":
        d.ellipse(box(8, 30, 52, 74), outline=255, width=round(11 * s))
        d.rectangle(box(48, 45, 92, 56), fill=255)
        d.rectangle(box(72, 54, 81, 70), fill=255)
        d.rectangle(box(83, 54, 92, 66), fill=255)
    elif name == "magnifier":
        d.ellipse(box(10, 10, 62, 62), outline=255, width=round(11 * s))
        _line(d, [(55, 55), (88, 88)], 14, 255, s)
    elif name == "mail":
        rrect(8, 22, 92, 80, 9)
        _line(d, [(14, 30), (50, 58), (86, 30)], 7, 0, s)
        d.ellipse(box(66, 4, 98, 36), fill=0)
        d.ellipse(box(71, 9, 93, 31), fill=255)
    elif name == "network":
        for x, y in ((18, 22), (82, 22), (18, 78), (82, 78)):
            _line(d, [(50, 50), (x, y)], 5, 255, s)
        d.ellipse(box(36, 36, 64, 64), fill=255)
        for x, y in ((18, 22), (82, 22), (18, 78), (82, 78)):
            d.ellipse(box(x - 10, y - 10, x + 10, y + 10), fill=255)
    elif name == "logs":
        for top in (14, 40, 66):
            rrect(10, top, 90, top + 22, 6)
            d.ellipse(box(19, top + 8, 27, top + 16), fill=0)
            _line(d, [(40, top + 11), (74, top + 11)], 4.5, 0, s)
    elif name == "bug":
        for dy in (-14, 4, 22):
            _line(d, [(36, 50 + dy), (14, 44 + dy)], 5, 255, s)
            _line(d, [(64, 50 + dy), (86, 44 + dy)], 5, 255, s)
        _line(d, [(44, 22), (36, 8)], 4.5, 255, s)
        _line(d, [(56, 22), (64, 8)], 4.5, 255, s)
        d.ellipse(box(38, 12, 62, 36), fill=255)
        d.ellipse(box(30, 32, 70, 92), fill=255)
        _line(d, [(50, 40), (50, 86)], 4, 0, s)
    elif name == "bolt":
        d.polygon([(x * s, y * s) for x, y in [(58, 4), (20, 55), (45, 55), (38, 96), (80, 40), (55, 40)]], fill=255)
    elif name == "terminal":
        rrect(8, 16, 92, 84, 10, fill=None, outline=255, width=7)
        _line(d, [(27, 38), (42, 50), (27, 62)], 7, 255, s)
        _line(d, [(50, 66), (72, 66)], 7, 255, s)
    else:
        return _mask("shield", size)
    return img.resize((size, size), Image.LANCZOS)


def _gradient(size: int, start: tuple[int, int, int], end: tuple[int, int, int]) -> Image.Image:
    """Diagonal gradient, top-left `start` to bottom-right `end`."""
    ramp = Image.linear_gradient("L").resize((size, size))  # top black to bottom white
    across = ramp.rotate(90).resize((size, size))
    t = Image.blend(ramp, across, 0.5)
    return Image.composite(Image.new("RGB", (size, size), end), Image.new("RGB", (size, size), start), t)


def draw_icon(canvas: Image.Image, name: str, x: int, y: int, size: int, start: tuple[int, int, int], end: tuple[int, int, int]) -> None:
    """The bare icon, filled with the gradient, with its top-left corner at (x, y)."""
    mask = _mask(name, size)
    canvas.paste(_gradient(size, start, end), (x, y), mask)


def draw_tile(canvas: Image.Image, name: str, x: int, y: int, size: int, start: tuple[int, int, int], end: tuple[int, int, int], tile: tuple[int, int, int] = (13, 18, 16)) -> None:
    """The icon on a dark rounded tile with a fine dot grid and a thin gradient edge. `size` is the whole tile."""
    SSX = 2
    big = size * SSX
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    radius = int(big * 0.2)
    border = max(2, size // 90) * SSX
    d.rounded_rectangle((0, 0, big - 1, big - 1), radius=radius, fill=(*tile, 255))
    gap = max(14, size // 12) * SSX
    dot = max(1, size // 160) * SSX
    for gx in range(gap, big - gap // 2, gap):
        for gy in range(gap, big - gap // 2, gap):
            d.ellipse((gx - dot, gy - dot, gx + dot, gy + dot), fill=(255, 255, 255, 22))
    # thin gradient edge: draw the gradient through a ring-shaped mask
    ring = Image.new("L", (big, big), 0)
    rd = ImageDraw.Draw(ring)
    rd.rounded_rectangle((0, 0, big - 1, big - 1), radius=radius, fill=255)
    rd.rounded_rectangle((border, border, big - 1 - border, big - 1 - border), radius=max(1, radius - border), fill=0)
    edge = _gradient(big, start, end)
    layer.paste(edge, (0, 0), ring.point(lambda v: int(v * 0.55)))
    icon_size = int(big * 0.52)
    mask = _mask(name, icon_size)
    offset = (big - icon_size) // 2
    layer.paste(_gradient(icon_size, start, end), (offset, offset), mask)
    tile_img = layer.resize((size, size), Image.LANCZOS)
    canvas.paste(tile_img, (x, y), tile_img)
