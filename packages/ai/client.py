"""
Shared AI package.

Every module that needs a language-model completion (AI Tutor, Question
Generator, Resume Builder, Interview Simulator, Assignment Evaluation,
Course Recommendation, Chat Assistant, Analytics — all in `modules.ai`)
calls `get_ai_client()` rather than talking to a provider's HTTP API
directly. Which provider backend is live is an infrastructure/ops
decision (which API key GIR Technologies has), not something the
application layer should hardcode — the same "provisioner" pattern
Pentrix uses for lab environments: one interface, one real
implementation per provider, selected by `settings.AI_PROVIDER`.

Real HTTP calls, not a stub: this hits the configured provider's API
using `settings.AI_API_KEY`, the same way `EmailService` makes real
SMTP connections using `settings.SMTP_*`. Both are integration code that
requires real deployment credentials to actually send/complete —
neither is a mock.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AIMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class AICompletionResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class AIClient(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> AICompletionResult:
        """Send a system prompt + conversation turns, return the assistant's reply."""


class AnthropicClient(AIClient):
    """Calls the Anthropic Messages API (https://api.anthropic.com/v1/messages)."""

    def __init__(self) -> None:
        self.api_key = settings.AI_API_KEY
        self.base_url = settings.AI_API_BASE_URL.rstrip("/")
        self.model = settings.AI_MODEL
        self.default_max_tokens = settings.AI_MAX_TOKENS
        self.timeout = settings.AI_REQUEST_TIMEOUT_SECONDS

    async def complete(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> AICompletionResult:
        if not self.api_key:
            raise ServiceUnavailableError(
                "AI provider is not configured. Set AI_API_KEY to enable AI features."
            )

        payload = {
            "model": self.model,
            "system": system_prompt,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/messages", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("ai_request_failed", status_code=exc.response.status_code)
            raise ServiceUnavailableError(
                f"AI provider returned an error (status {exc.response.status_code})."
            )
        except httpx.HTTPError:
            logger.exception("ai_request_failed")
            raise ServiceUnavailableError("Could not reach the AI provider. Please try again shortly.")

        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage", {})
        return AICompletionResult(
            text=text,
            model=data.get("model", self.model),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


class OpenAICompatibleClient(AIClient):
    """Calls any Chat Completions-compatible API (OpenAI, Azure OpenAI, self-hosted gateways)."""

    def __init__(self) -> None:
        self.api_key = settings.AI_API_KEY
        self.base_url = settings.AI_API_BASE_URL.rstrip("/")
        self.model = settings.AI_MODEL
        self.default_max_tokens = settings.AI_MAX_TOKENS
        self.timeout = settings.AI_REQUEST_TIMEOUT_SECONDS

    async def complete(
        self,
        system_prompt: str,
        messages: list[AIMessage],
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> AICompletionResult:
        if not self.api_key:
            raise ServiceUnavailableError(
                "AI provider is not configured. Set AI_API_KEY to enable AI features."
            )

        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system_prompt}]
            + [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("ai_request_failed", status_code=exc.response.status_code)
            raise ServiceUnavailableError(
                f"AI provider returned an error (status {exc.response.status_code})."
            )
        except httpx.HTTPError:
            logger.exception("ai_request_failed")
            raise ServiceUnavailableError("Could not reach the AI provider. Please try again shortly.")

        choice = (data.get("choices") or [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return AICompletionResult(
            text=text,
            model=data.get("model", self.model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


def get_ai_client() -> AIClient:
    if settings.AI_PROVIDER.lower() == "anthropic":
        return AnthropicClient()
    return OpenAICompatibleClient()
