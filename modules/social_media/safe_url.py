"""
Links that come from outside (Instagram's own answers, a feed, a person typing one in) are only ever shown or followed if they are
plain https addresses on the expected sites. A `javascript:` or `data:` address, an address with a password in it, or an https
address on some other site is dropped rather than kept, so it can't end up behind a link a team member clicks.
"""

from urllib.parse import urlsplit

INSTAGRAM_PAGE_HOSTS = ("instagram.com",)
INSTAGRAM_IMAGE_HOSTS = ("instagram.com", "cdninstagram.com", "fbcdn.net")


def safe_url(value: object, hosts: tuple[str, ...] | None = None, limit: int = 1000) -> str | None:
    """The address if it is a plain https address (on one of `hosts`, or a subdomain of one), otherwise None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > limit or any(ch.isspace() or ord(ch) < 32 for ch in text):
        return None
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if parts.scheme != "https" or parts.username or parts.password or "." not in host:
        return None
    if hosts is not None and not any(host == h or host.endswith("." + h) for h in hosts):
        return None
    return text


def instagram_page(value: object) -> str | None:
    """A link to a page on instagram.com (a post's permalink)."""
    return safe_url(value, INSTAGRAM_PAGE_HOSTS, 500)


def instagram_image(value: object) -> str | None:
    """A link to a picture on Instagram's own servers."""
    return safe_url(value, INSTAGRAM_IMAGE_HOSTS, 1000)
