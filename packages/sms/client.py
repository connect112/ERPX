"""
Shared SMS package.

Every module that needs to send a plain-text SMS (CRM follow-up
reminders, attendance/leave alerts, OTP delivery, ...) imports
`sms_service` from here rather than talking to a provider's HTTP API
directly, mirroring `packages.email` and `packages.ai`.

Real HTTP calls, not a stub — this hits Fast2SMS's Quick SMS API
(https://docs.fast2sms.com/#quick-sms-transactional-route) using
`settings.SMS_PROVIDER_API_KEY`, the same way `EmailService` makes real
SMTP connections and `packages.ai` makes real LLM provider calls.
"""

import httpx

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"


class SMSService:
    def __init__(self) -> None:
        self.api_key = settings.SMS_PROVIDER_API_KEY
        self.sender_id = settings.SMS_SENDER_ID

    async def send(self, to_phone: str, message: str) -> bool:
        if not self.api_key:
            logger.warning("sms_not_configured", to=to_phone)
            raise ServiceUnavailableError(
                "SMS provider is not configured. Set SMS_PROVIDER_API_KEY to enable SMS."
            )

        digits_only = "".join(ch for ch in to_phone if ch.isdigit())[-10:]

        payload = {
            "route": "q",
            "message": message,
            "language": "english",
            "flash": 0,
            "numbers": digits_only,
            "sender_id": self.sender_id,
        }
        headers = {"authorization": self.api_key, "Content-Type": "application/x-www-form-urlencoded"}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(FAST2SMS_URL, data=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            logger.exception("sms_send_failed", to=to_phone)
            return False

        success = bool(data.get("return"))
        if not success:
            logger.warning("sms_send_rejected", to=to_phone, response=data)
        return success


sms_service = SMSService()
