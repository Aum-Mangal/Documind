"""A small key-value cache: Redis when REDIS_URL is set, otherwise in process memory.

Used for rate-limit counters, revoked tokens and cached answers/embeddings. If Redis is
unreachable, reads miss and counters return 0, so the app keeps working (limits and
revocations simply aren't enforced until Redis is back) instead of rejecting everyone.
"""
import logging
import time

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis | None:
    global _redis
    url = get_settings().redis_url
    if url and _redis is None:
        _redis = Redis.from_url(url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
    return _redis


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    def _live(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at <= time.monotonic():
            del self._data[key]
            return None
        return value

    async def get(self, key: str) -> str | None:
        return self._live(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if len(self._data) > 10_000:
            self._purge()
        self._data[key] = (value, time.monotonic() + ttl_seconds)

    async def exists(self, key: str) -> bool:
        return self._live(key) is not None

    async def incr_window(self, key: str, ttl_seconds: int) -> int:
        count = int(self._live(key) or 0) + 1
        expires_at = self._data[key][1] if key in self._data else time.monotonic() + ttl_seconds
        self._data[key] = (str(count), expires_at)
        return count

    def clear(self) -> None:
        self._data.clear()

    def _purge(self) -> None:
        for key in list(self._data):
            self._live(key)


class RedisCache:
    def __init__(self, client: Redis) -> None:
        self.client = client
        self._last_error_log = 0.0

    def _warn(self) -> None:
        # One warning a minute is enough while Redis is down
        now = time.monotonic()
        if now - self._last_error_log > 60:
            self._last_error_log = now
            logger.warning("Redis unavailable; continuing without it", exc_info=True)

    async def get(self, key: str) -> str | None:
        try:
            return await self.client.get(key)
        except Exception:
            self._warn()
            return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            await self.client.set(key, value, ex=ttl_seconds)
        except Exception:
            self._warn()

    async def exists(self, key: str) -> bool:
        try:
            return bool(await self.client.exists(key))
        except Exception:
            self._warn()
            return False

    async def incr_window(self, key: str, ttl_seconds: int) -> int:
        # SET NX starts the window with its expiry; INCR counts. Two commands, one round trip.
        try:
            async with self.client.pipeline(transaction=False) as pipe:
                pipe.set(key, 0, ex=ttl_seconds, nx=True)
                pipe.incr(key)
                _, count = await pipe.execute()
            return int(count)
        except Exception:
            self._warn()
            return 0


_cache: MemoryCache | RedisCache | None = None


def get_cache() -> MemoryCache | RedisCache:
    global _cache
    if _cache is None:
        redis = get_redis()
        _cache = RedisCache(redis) if redis is not None else MemoryCache()
    return _cache


async def close_redis() -> None:
    global _redis, _cache
    if _redis is not None:
        await _redis.aclose()
    _redis = None
    _cache = None
