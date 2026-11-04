import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings
from app.services.cache import get_redis
from app.services.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def liveness():
    """The process is up. Used by Docker and hosting health checks."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(session: DbSession):
    """Every dependency the app is configured to use is reachable."""
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Readiness: database check failed")
        checks["database"] = "error"

    redis = get_redis()
    if redis is not None:
        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception:
            logger.exception("Readiness: redis check failed")
            checks["redis"] = "error"

    if get_settings().storage_enabled:
        try:
            await run_in_threadpool(get_storage().check)
            checks["storage"] = "ok"
        except Exception:
            logger.exception("Readiness: storage check failed")
            checks["storage"] = "error"

    ready = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ok" if ready else "error", "checks": checks})
