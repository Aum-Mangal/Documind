import asyncio
import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import rate_limit
from app.core.config import get_settings
from app.core.security import create_access_token, decode_token
from app.services import cache as cache_module
from app.services.cache import MemoryCache, RedisCache
from app.services.llm import record_usage, track_usage


def run(coro):
    return asyncio.run(coro)


# ── Memory cache ─────────────────────────────────────

def test_memory_cache_values_expire(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: now[0])
    c = MemoryCache()
    run(c.set("k", "v", 10))
    assert run(c.get("k")) == "v" and run(c.exists("k"))
    now[0] += 11
    assert run(c.get("k")) is None and not run(c.exists("k"))


def test_memory_cache_window_counter_resets_after_its_ttl(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: now[0])
    c = MemoryCache()
    assert [run(c.incr_window("w", 60)) for _ in range(3)] == [1, 2, 3]
    now[0] += 30
    assert run(c.incr_window("w", 60)) == 4  # same window: the expiry isn't pushed back
    now[0] += 31
    assert run(c.incr_window("w", 60)) == 1


# ── Redis cache ──────────────────────────────────────

class BrokenRedis:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ConnectionError("redis is down")
        return fail


def test_redis_outage_fails_open():
    c = RedisCache(BrokenRedis())
    assert run(c.get("k")) is None
    assert run(c.exists("k")) is False
    assert run(c.incr_window("k", 60)) == 0  # counts nothing, so nobody is rate limited
    run(c.set("k", "v", 60))  # doesn't raise


@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="set TEST_REDIS_URL to test against Redis")
def test_redis_cache_against_a_real_server():
    from redis.asyncio import Redis

    async def go():
        client = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
        c = RedisCache(client)
        try:
            await client.delete("test:k", "test:w")
            await c.set("test:k", "v", 5)
            assert await c.get("test:k") == "v" and await c.exists("test:k")
            assert [await c.incr_window("test:w", 5) for _ in range(3)] == [1, 2, 3]
            assert 0 < await client.ttl("test:w") <= 5
        finally:
            await client.delete("test:k", "test:w")
            await client.aclose()

    run(go())


# ── Rate limits ──────────────────────────────────────

def test_rate_limit_allows_up_to_the_limit_then_rejects():
    async def go():
        for _ in range(3):
            await rate_limit.enforce("t", "alice", 3, 60, "slow down")
        with pytest.raises(HTTPException) as excinfo:
            await rate_limit.enforce("t", "alice", 3, 60, "slow down")
        return excinfo.value

    error = run(go())
    assert error.status_code == 429 and error.detail == "slow down"
    assert 1 <= int(error.headers["Retry-After"]) <= 61


def test_rate_limits_are_per_identity_and_per_name():
    async def go():
        for _ in range(2):
            await rate_limit.enforce("a", "alice", 2, 60, "x")
        await rate_limit.enforce("a", "bob", 2, 60, "x")    # different identity
        await rate_limit.enforce("b", "alice", 2, 60, "x")  # different limit
        with pytest.raises(HTTPException):
            await rate_limit.enforce("a", "alice", 2, 60, "x")

    run(go())


def test_identities_are_case_insensitive_and_hashed():
    async def go():
        await rate_limit.enforce("c", "Alice@Example.com", 1, 60, "x")
        with pytest.raises(HTTPException):
            await rate_limit.enforce("c", "alice@example.com", 1, 60, "x")

    run(go())
    keys = list(cache_module.get_cache()._data)
    assert keys and not any("alice" in k for k in keys)


def test_zero_disables_a_limit():
    async def go():
        for _ in range(50):
            await rate_limit.enforce("z", "alice", 0, 60, "x")

    run(go())


def _request(headers=None, host="10.0.0.1"):
    scope = {"type": "http", "headers": [(k.encode(), v.encode()) for k, v in (headers or {}).items()],
             "client": (host, 1234)}
    return Request(scope)


def test_client_ip_ignores_forwarded_headers_unless_trusted(monkeypatch):
    request = _request({"x-forwarded-for": "203.0.113.9, 10.0.0.1"})
    assert rate_limit.client_ip(request) == "10.0.0.1"
    monkeypatch.setattr(get_settings(), "trust_proxy_headers", True)
    assert rate_limit.client_ip(request) == "203.0.113.9"


# ── LLM usage tracking ───────────────────────────────

def test_usage_is_tracked_across_worker_threads():
    async def go():
        with track_usage() as usage:
            await asyncio.to_thread(record_usage, 100, 20)
            await asyncio.to_thread(record_usage, 50, 5)
        record_usage(999, 999)  # outside any tracker: ignored
        return usage

    usage = run(go())
    assert (usage.prompt_tokens, usage.completion_tokens, usage.calls, usage.total_tokens) == (150, 25, 2, 175)


# ── Tokens and logout ────────────────────────────────

def test_tokens_carry_a_unique_id():
    a, b = decode_token(create_access_token(1)), decode_token(create_access_token(1))
    assert a.token_id and b.token_id and a.token_id != b.token_id
    assert a.expires_at > a.expires_at.now(a.expires_at.tzinfo)


def test_logout_revokes_the_token(client):
    token = create_access_token(1)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    # Rejected before any database lookup
    assert client.get("/api/documents", headers=headers).status_code == 401
    assert client.post("/api/auth/logout", headers=headers).status_code == 401


def test_logout_requires_a_token(client):
    assert client.post("/api/auth/logout").status_code == 401
