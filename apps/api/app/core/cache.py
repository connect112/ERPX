"""
Redis response caching for read-only aggregate endpoints (finding #16 / TD-2).

A single reusable `@cache_response(...)` decorator caches the JSON body of
expensive **read-only** GET handlers (dashboards, analytics, financial
reports) in Redis — using ONLY the Redis instance the app already runs
(Celery broker / rate-limit store); no new cache technology.

Design guarantees:

- **Org/param-scoped keys.** The cache key is derived from the handler's
  own injected arguments — `organization_id` (so tenants never share a
  cache entry) plus every scalar path/query parameter (`as_of_date`,
  `period_from`, `campaign_id`, …). The DB session and the `User` object
  are never part of the key.
- **Behaviour-identical.** On a miss the handler runs untouched and its
  Pydantic model is returned to FastAPI exactly as before; the cache stores
  `model.model_dump(mode="json")`. On a hit the stored dict is returned and
  FastAPI re-validates it through the endpoint's `response_model` and
  serialises it on the identical code path — so a cached response is
  byte-for-byte what an uncached one would have been. RBAC/permission
  dependencies (`require_permissions`) run during dependency resolution,
  *before* this decorator, so they are always enforced — even on a hit.
- **Graceful degradation.** Every Redis interaction is wrapped so that any
  failure (Redis down, timeout, malformed entry) transparently falls back
  to running the handler. A short circuit-breaker backoff avoids hammering
  a downed Redis and keeps the app fast when the cache is unavailable.
- **Never caches mutations.** Only apply to idempotent GET handlers; the
  decorator has no effect on request bodies and is never placed on
  POST/PUT/PATCH/DELETE, auth, or permission logic.
"""

from __future__ import annotations

import functools
import hashlib
import json
import time
import uuid
from datetime import date, datetime
from typing import Any, Awaitable, Callable, TypeVar

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_KEY_NAMESPACE = "erpx:cache"
_SCALAR_TYPES = (str, int, float, bool, uuid.UUID, date, datetime)
# Injected handler args that must never contribute to (or leak into) a key.
_NON_KEY_ARGS = frozenset({"db", "user", "request", "response"})

# Circuit breaker: after a Redis failure, skip Redis entirely for this many
# seconds so a downed cache neither slows requests nor gets hammered.
_BACKOFF_SECONDS = 30.0
_backoff_until = 0.0

_client: aioredis.Redis | None = None

T = TypeVar("T")


def _get_client() -> aioredis.Redis | None:
    """Return the shared async Redis client, or None if caching is disabled
    or currently in circuit-breaker backoff."""
    global _client
    if not settings.CACHE_ENABLED:
        return None
    if time.monotonic() < _backoff_until:
        return None
    if _client is None:
        try:
            _client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
        except Exception as exc:  # pragma: no cover - defensive
            _trip_backoff()
            logger.warning("cache_client_init_failed", error=str(exc))
            return None
    return _client


def _trip_backoff() -> None:
    global _backoff_until
    _backoff_until = time.monotonic() + _BACKOFF_SECONDS


def _build_key(prefix: str, kwargs: dict[str, Any]) -> str:
    org_id = kwargs.get("organization_id")
    parts: list[str] = []
    for name in sorted(kwargs):
        if name in _NON_KEY_ARGS or name == "organization_id":
            continue
        value = kwargs[name]
        if value is None or isinstance(value, _SCALAR_TYPES):
            parts.append(f"{name}={value}")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{_KEY_NAMESPACE}:{prefix}:{org_id}:{digest}"


def cache_response(*, ttl: int, prefix: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[Any]]]:
    """Cache a read-only async GET handler's response in Redis for `ttl`
    seconds under `prefix`. See the module docstring for the guarantees."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)  # preserves the signature FastAPI introspects
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = _get_client()
            if client is None:
                return await func(*args, **kwargs)

            key = _build_key(prefix, kwargs)

            try:
                cached = await client.get(key)
            except Exception as exc:
                _trip_backoff()
                logger.warning("cache_get_failed", prefix=prefix, error=str(exc))
                return await func(*args, **kwargs)

            if cached is not None:
                try:
                    return json.loads(cached)
                except (ValueError, TypeError):
                    # Corrupt entry — ignore it and recompute.
                    logger.warning("cache_decode_failed", prefix=prefix)

            result = await func(*args, **kwargs)

            try:
                payload = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
                await client.set(key, json.dumps(payload), ex=ttl)
            except Exception as exc:
                _trip_backoff()
                logger.warning("cache_set_failed", prefix=prefix, error=str(exc))

            return result

        return wrapper

    return decorator


async def invalidate_prefix(prefix: str, organization_id: uuid.UUID | str) -> int:
    """Delete every cached entry for `prefix` scoped to one organization.

    Provided for callers that want explicit post-mutation invalidation. The
    aggregate endpoints currently rely on short TTLs instead (see the audit
    doc for why precise cross-module invalidation is deferred). Returns the
    number of keys deleted; degrades to 0 on any Redis failure.
    """
    client = _get_client()
    if client is None:
        return 0
    pattern = f"{_KEY_NAMESPACE}:{prefix}:{organization_id}:*"
    try:
        deleted = 0
        async for key in client.scan_iter(match=pattern):
            deleted += await client.delete(key)
        return deleted
    except Exception as exc:
        _trip_backoff()
        logger.warning("cache_invalidate_failed", prefix=prefix, error=str(exc))
        return 0
