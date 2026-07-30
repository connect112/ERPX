"""
Unit tests for the Redis response-cache helper (finding #16 / TD-2).

No real Redis: the client is monkeypatched with an in-memory fake (hit/miss
paths) or forced to None / made to raise (graceful-degradation paths). The
`client` fixture in the api suite already exercises the real
graceful-degradation path end-to-end when Redis is genuinely down.
"""

import uuid

import pytest
from pydantic import BaseModel

import app.core.cache as cache
from app.core.cache import _build_key, cache_response

pytestmark = pytest.mark.unit


class _Sample(BaseModel):
    total: int
    label: str


class _FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, key):
        self.get_calls += 1
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.set_calls += 1
        self.store[key] = value


def test_build_key_scopes_by_org_and_params_and_ignores_session_and_user():
    org = uuid.UUID("11111111-1111-1111-1111-111111111111")
    k1 = _build_key("p", {"organization_id": org, "as_of_date": "2026-01-01", "db": object(), "user": object()})
    # org appears in the key path; the digest reflects only scalar params
    assert str(org) in k1
    assert k1.startswith("erpx:cache:p:")
    # different org -> different key
    k2 = _build_key("p", {"organization_id": uuid.uuid4(), "as_of_date": "2026-01-01"})
    assert k1 != k2
    # different param -> different key
    k3 = _build_key("p", {"organization_id": org, "as_of_date": "2026-02-02"})
    assert k1 != k3
    # db/user identity must not affect the key (determinism)
    k4 = _build_key("p", {"organization_id": org, "as_of_date": "2026-01-01", "db": object(), "user": object()})
    assert k1 == k4


async def test_cache_miss_then_hit(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(cache, "_get_client", lambda: fake)
    calls = {"n": 0}

    @cache_response(ttl=60, prefix="test.sample")
    async def handler(*, organization_id):
        calls["n"] += 1
        return _Sample(total=calls["n"], label="x")

    org = uuid.uuid4()
    # miss: handler runs, model returned, value stored
    first = await handler(organization_id=org)
    assert isinstance(first, _Sample) and first.total == 1
    assert fake.set_calls == 1 and calls["n"] == 1
    # hit: handler NOT run again, cached dict returned (FastAPI would re-validate it)
    second = await handler(organization_id=org)
    assert calls["n"] == 1  # handler body skipped
    assert second == {"total": 1, "label": "x"}


async def test_graceful_degradation_when_redis_disabled(monkeypatch):
    # _get_client returns None (disabled / backoff) -> handler always runs, no error
    monkeypatch.setattr(cache, "_get_client", lambda: None)
    calls = {"n": 0}

    @cache_response(ttl=60, prefix="test.sample")
    async def handler(*, organization_id):
        calls["n"] += 1
        return _Sample(total=calls["n"], label="y")

    org = uuid.uuid4()
    r1 = await handler(organization_id=org)
    r2 = await handler(organization_id=org)
    assert isinstance(r1, _Sample) and isinstance(r2, _Sample)
    assert calls["n"] == 2  # no caching, handler ran both times


async def test_graceful_degradation_when_redis_get_raises(monkeypatch):
    class _BrokenRedis:
        async def get(self, key):
            raise ConnectionError("redis down")

        async def set(self, key, value, ex=None):
            raise ConnectionError("redis down")

    monkeypatch.setattr(cache, "_get_client", lambda: _BrokenRedis())
    calls = {"n": 0}

    @cache_response(ttl=60, prefix="test.sample")
    async def handler(*, organization_id):
        calls["n"] += 1
        return _Sample(total=calls["n"], label="z")

    # a raising Redis must not surface — handler runs and returns normally
    result = await handler(organization_id=uuid.uuid4())
    assert isinstance(result, _Sample) and result.total == 1
