"""The interface every payment gateway adapter implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class ProviderError(Exception):
    """The gateway refused or could not be reached. The message is safe to show to staff (no secrets, no raw payloads)."""


@dataclass(frozen=True)
class CreatedOrder:
    provider_order_id: str
    payment_session_id: str
    status: str


@dataclass(frozen=True)
class ProviderPayment:
    provider_payment_id: str
    status: str  # success | failed | pending
    amount: Decimal
    currency: str
    paid_at: datetime | None = None


@dataclass(frozen=True)
class WebhookEvent:
    event_type: str
    merchant_order_id: str
    payment: ProviderPayment | None


class PaymentProvider(ABC):
    name: str
    environment: str

    @abstractmethod
    async def create_order(
        self, *, merchant_order_id: str, amount: Decimal, currency: str, customer_id: str, customer_name: str,
        customer_email: str, customer_phone: str, return_url: str, expires_at: datetime, note: str,
    ) -> CreatedOrder: ...  # fmt: skip

    @abstractmethod
    async def order_payments(self, merchant_order_id: str) -> list[ProviderPayment]: ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool: ...

    @abstractmethod
    def parse_webhook(self, raw_body: bytes) -> WebhookEvent: ...
