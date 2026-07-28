"""
Shared WhatsApp package.

Every module that needs to send a WhatsApp message (CRM follow-up
reminders, admission confirmations, ...) imports `whatsapp_service` from
here rather than talking to Meta's API directly, mirroring
`packages.email` and `packages.sms`.

Real HTTP calls, not a stub — this hits the Meta WhatsApp Cloud API
(https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages)
using `settings.WHATSAPP_API_KEY` / `WHATSAPP_PHONE_NUMBER_ID`.

Free-form text messages (what `send_text` sends) only deliver within the
24-hour customer-service window opened by the recipient's last inbound
message to this number. Outside that window, Meta requires a
pre-approved message template instead — `send_template` is the
integration point for that; which templates exist and their approved
variable structure is an account-configuration concern, not something
this client can discover generically.
"""

import httpx

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

GRAPH_API_VERSION = "v18.0"


class WhatsAppService:
    def __init__(self) -> None:
        self.api_key = settings.WHATSAPP_API_KEY
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID

    @property
    def _base_url(self) -> str:
        return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}/messages"

    async def send_text(self, to_phone: str, message: str) -> bool:
        if not self.api_key or not self.phone_number_id:
            logger.warning("whatsapp_not_configured", to=to_phone)
            raise ServiceUnavailableError(
                "WhatsApp is not configured. Set WHATSAPP_API_KEY and WHATSAPP_PHONE_NUMBER_ID."
            )

        digits_only = "".join(ch for ch in to_phone if ch.isdigit() or ch == "+")
        payload = {
            "messaging_product": "whatsapp",
            "to": digits_only,
            "type": "text",
            "text": {"body": message},
        }
        return await self._post(payload, to_phone)

    async def send_template(
        self, to_phone: str, template_name: str, language_code: str, parameters: list[str]
    ) -> bool:
        if not self.api_key or not self.phone_number_id:
            logger.warning("whatsapp_not_configured", to=to_phone)
            raise ServiceUnavailableError(
                "WhatsApp is not configured. Set WHATSAPP_API_KEY and WHATSAPP_PHONE_NUMBER_ID."
            )

        digits_only = "".join(ch for ch in to_phone if ch.isdigit() or ch == "+")
        payload = {
            "messaging_product": "whatsapp",
            "to": digits_only,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in parameters],
                    }
                ],
            },
        }
        return await self._post(payload, to_phone)

    async def _post(self, payload: dict, to_phone: str) -> bool:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(self._base_url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "whatsapp_send_rejected", to=to_phone, status_code=exc.response.status_code,
                body=exc.response.text,
            )
            return False
        except httpx.HTTPError:
            logger.exception("whatsapp_send_failed", to=to_phone)
            return False
        return True


whatsapp_service = WhatsAppService()
