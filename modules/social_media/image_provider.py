"""
Optional AI-made backgrounds. Off unless SOCIAL_IMAGE_API_KEY, SOCIAL_IMAGE_API_BASE_URL and SOCIAL_IMAGE_MODEL are all set.

The picture is only ever a background. The prompt asks for something abstract and quiet with no text, logos, people
or clichéd security imagery; the renderer then darkens it under a scrim and draws every word and the logo itself.
A generated picture is stored as synthetic and is never presented as genuine evidence.
"""

import base64

import httpx

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging_config import get_logger

logger = get_logger(__name__)
TIMEOUT = 120.0
SIZE = "1024x1536"


def configured() -> bool:
    return bool(settings.SOCIAL_IMAGE_API_KEY and settings.SOCIAL_IMAGE_API_BASE_URL and settings.SOCIAL_IMAGE_MODEL)


def build_prompt(brand: dict, rules: dict, direction: str) -> str:
    colors = brand.get("colors", {})
    avoid = "; ".join(rules.get("forbidden_visuals", []))
    return (
        "A calm, abstract, minimal background image for a cybersecurity education brand's social media post. "
        "Soft shapes or texture, plenty of empty space, one gentle focal area, muted colours drawn from "
        f"{colors.get('primary', '#1D4ED8')} and {colors.get('ink', '#0F172A')}. "
        "Absolutely no text, letters, numbers, logos, watermarks, people, hands, faces, screens or code. "
        f"Avoid: {avoid}. "
        f"{('Direction from the team: ' + direction.strip()) if direction.strip() else ''}"
    ).strip()


async def generate_background(prompt: str) -> bytes:
    """One image's bytes from the configured provider. Only inline image data is accepted: a link the provider returns
    is never fetched, so a provider can't point this server at an address of its choosing."""
    if not configured():
        raise ServiceUnavailableError(
            "AI backgrounds aren't set up on this server. Set SOCIAL_IMAGE_API_KEY, SOCIAL_IMAGE_API_BASE_URL and SOCIAL_IMAGE_MODEL, or use your own photo."
        )
    url = settings.SOCIAL_IMAGE_API_BASE_URL.rstrip("/") + "/v1/images/generations"
    headers = {"Authorization": f"Bearer {settings.SOCIAL_IMAGE_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": settings.SOCIAL_IMAGE_MODEL, "prompt": prompt, "size": SIZE, "n": 1}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("social_image_failed", status=exc.response.status_code)
        raise ServiceUnavailableError(f"The image service returned an error (status {exc.response.status_code}).") from None
    except (httpx.HTTPError, ValueError):
        logger.warning("social_image_failed", exc_info=True)
        raise ServiceUnavailableError("The image service didn't answer. Try again in a moment.") from None
    item = (data.get("data") or [{}])[0]
    encoded = item.get("b64_json")
    if not encoded:
        raise ServiceUnavailableError("The image service returned a link instead of image data, which isn't used. Choose a provider that returns image data.")
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ServiceUnavailableError("The image service's answer couldn't be read.") from None
