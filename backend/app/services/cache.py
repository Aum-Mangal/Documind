"""Shared Redis client. Redis is optional: features that use it check `get_redis()` for None."""
from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis | None:
    global _redis
    url = get_settings().redis_url
    if url and _redis is None:
        _redis = Redis.from_url(url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
