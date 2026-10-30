"""
Cashfree Payment Gateway adapter (PG API, hosted checkout).

STATUS: written against Cashfree's documented contract (``x-api-version`` 2023-08-01 or later: ``POST /pg/orders``,
``GET /pg/orders/{order_id}/payments``, webhook signature = base64(HMAC-SHA256(timestamp + raw body, secret key))).
It has NOT yet been checked against the current documentation or run against the sandbox, because cashfree.com was not
reachable from the development environment. Do that before enabling it (docs/INTERN_ONBOARDING_PROGRESS.md).

Rules that hold whatever the gateway says: the secret never leaves this process (not logged, not returned), production
needs CASHFREE_ALLOW_PRODUCTION, and nothing here marks anything paid; the payment service does that only after it has
matched order id, amount and currency.
"""

import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from modules.internship_onboarding.providers.base import (
    CreatedOrder,
    PaymentProvider,
    ProviderError,
    ProviderPayment,
    WebhookEvent,
)

logger = get_logger(__name__)

BASE_URLS = {"sandbox": "https://sandbox.cashfree.com/pg", "production": "https://api.cashfree.com/pg"}
STATUS = {"SUCCESS": "success", "FAILED": "failed", "USER_DROPPED": "failed", "CANCELLED": "failed", "VOID": "failed"}
TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def _amount(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ProviderError("The gateway sent an amount that cannot be read.") from None


def _phone(raw: str | None) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10:
        raise ProviderError("A 10-digit mobile number is needed to pay online. Ask the internship team to update it.")
    return digits


class CashfreeProvider(PaymentProvider):
    name = "cashfree"

    def __init__(self, app_id: str, secret_key: str, environment: str, api_version: str, transport: httpx.AsyncBaseTransport | None = None):
        if environment not in BASE_URLS:
            raise ProviderError("CASHFREE_ENV must be sandbox or production.")
        if environment == "production" and not settings.CASHFREE_ALLOW_PRODUCTION:
            raise ProviderError("Live Cashfree payments are not authorised on this server.")
        if not app_id or not secret_key:
            raise ProviderError("Cashfree is not configured on this server.")
        self.environment = environment
        self._app_id = app_id
        self._secret = secret_key
        self._version = api_version
        self._transport = transport

    @classmethod
    def from_settings(cls) -> "CashfreeProvider":
        if not settings.CASHFREE_ENABLED:
            raise ProviderError("Online payment is not switched on for this server.")
        return cls(settings.CASHFREE_APP_ID, settings.CASHFREE_SECRET_KEY, settings.CASHFREE_ENV, settings.CASHFREE_API_VERSION)

    def __repr__(self) -> str:  # never show the secret, even in a debugger or a traceback
        return f"CashfreeProvider(environment={self.environment!r})"

    def _headers(self) -> dict[str, str]:
        return {
            "x-client-id": self._app_id,
            "x-client-secret": self._secret,
            "x-api-version": self._version,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, body: dict | None = None):
        url = BASE_URLS[self.environment] + path
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self._transport) as client:
                response = await client.request(method, url, headers=self._headers(), json=body)
        except httpx.HTTPError:
            logger.warning("cashfree_unreachable", path=path.split("/")[1] if "/" in path else path)
            raise ProviderError("The payment gateway could not be reached. Try again in a moment.") from None
        if response.status_code >= 400:
            code = ""
            try:
                code = str(response.json().get("code", ""))[:60]
            except ValueError:
                pass
            logger.warning("cashfree_error", status=response.status_code, code=code)
            raise ProviderError(f"The payment gateway refused the request ({response.status_code}{', ' + code if code else ''}).")
        try:
            return response.json()
        except ValueError:
            raise ProviderError("The payment gateway sent an unreadable reply.") from None

    async def create_order(
        self, *, merchant_order_id: str, amount: Decimal, currency: str, customer_id: str, customer_name: str,
        customer_email: str, customer_phone: str, return_url: str, expires_at: datetime, note: str,
    ) -> CreatedOrder:  # fmt: skip
        body = {
            "order_id": merchant_order_id,
            "order_amount": float(amount),
            "order_currency": currency,
            "customer_details": {
                "customer_id": customer_id[:50],
                "customer_name": customer_name[:100],
                "customer_email": customer_email[:100],
                "customer_phone": _phone(customer_phone),
            },
            "order_meta": {"return_url": return_url},
            "order_expiry_time": expires_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "order_note": note[:200],
        }
        data = await self._request("POST", "/orders", body)
        if data.get("order_id") != merchant_order_id or not data.get("payment_session_id"):
            raise ProviderError("The payment gateway returned an unexpected order.")
        if _amount(data.get("order_amount")) != amount or data.get("order_currency") != currency:
            raise ProviderError("The payment gateway returned a different amount.")
        return CreatedOrder(provider_order_id=str(data.get("cf_order_id", "")), payment_session_id=data["payment_session_id"], status=str(data.get("order_status", "")))

    async def order_payments(self, merchant_order_id: str) -> list[ProviderPayment]:
        data = await self._request("GET", f"/orders/{merchant_order_id}/payments")
        if not isinstance(data, list):
            raise ProviderError("The payment gateway sent an unexpected payment list.")
        return [self._payment(p) for p in data if isinstance(p, dict) and p.get("cf_payment_id") is not None]

    @staticmethod
    def _payment(p: dict) -> ProviderPayment:
        paid_at = None
        if p.get("payment_time"):
            try:
                paid_at = datetime.fromisoformat(str(p["payment_time"]))
            except ValueError:
                paid_at = None
        return ProviderPayment(
            provider_payment_id=str(p["cf_payment_id"]),
            status=STATUS.get(str(p.get("payment_status", "")).upper(), "pending"),
            amount=_amount(p.get("payment_amount")),
            currency=str(p.get("payment_currency") or ""),
            paid_at=paid_at,
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        lowered = {k.lower(): v for k, v in headers.items()}
        signature, timestamp = lowered.get("x-webhook-signature", ""), lowered.get("x-webhook-timestamp", "")
        if not signature or not timestamp:
            return False
        expected = base64.b64encode(hmac.new(self._secret.encode(), timestamp.encode() + raw_body, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(expected, signature):
            return False
        try:
            sent = int(timestamp) / (1000 if len(timestamp) > 11 else 1)
        except ValueError:
            return False
        age = datetime.now(timezone.utc).timestamp() - sent
        return -300 <= age <= settings.CASHFREE_WEBHOOK_MAX_AGE_HOURS * 3600

    def parse_webhook(self, raw_body: bytes) -> WebhookEvent:
        try:
            body = json.loads(raw_body)
            data = body["data"]
            order_id = str(data["order"]["order_id"])
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Unreadable notification.") from None
        payment = data.get("payment")
        return WebhookEvent(
            event_type=str(body.get("type", ""))[:60],
            merchant_order_id=order_id,
            payment=self._payment(payment) if isinstance(payment, dict) and payment.get("cf_payment_id") is not None else None,
        )
