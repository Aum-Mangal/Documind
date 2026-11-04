"""Fixed-window rate limits backed by the shared cache (Redis, or memory without it).

A fixed window can let up to twice the limit through around a window boundary. That is
an acceptable trade for two cache commands per check on a free Redis tier.
"""
import hashlib
import time

from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.services.cache import get_cache


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce(name: str, identity: str, limit: int, window_seconds: int, message: str) -> None:
    """Counts one request for `identity`; raises 429 once `limit` is exceeded in the window."""
    if not get_settings().rate_limits_enabled or limit <= 0:
        return
    window = int(time.time() // window_seconds)
    # Hash identities so emails and IPs aren't stored in Redis in the clear
    ident = hashlib.sha256(identity.lower().encode()).hexdigest()[:24]
    key = f"rl:{name}:{ident}:{window}"
    count = await get_cache().incr_window(key, window_seconds + 5)
    if count > limit:
        retry_after = int(window_seconds - time.time() % window_seconds) + 1
        raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(retry_after)})
