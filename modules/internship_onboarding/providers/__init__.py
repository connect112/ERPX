"""Payment providers behind one interface. Adding a gateway (Razorpay, ...) is a new adapter, not a new flow."""

from modules.internship_onboarding.providers.base import PaymentProvider, ProviderError, ProviderPayment, WebhookEvent


def get_provider(name: str) -> PaymentProvider:
    if name == "cashfree":
        from modules.internship_onboarding.providers.cashfree import CashfreeProvider

        return CashfreeProvider.from_settings()
    raise ProviderError(f"Unknown payment provider: {name}")


__all__ = ["PaymentProvider", "ProviderError", "ProviderPayment", "WebhookEvent", "get_provider"]
