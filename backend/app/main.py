import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, chat, documents, health
from app.core.config import BACKEND_DIR, get_settings
from app.core.logging import configure_logging, new_request_id, request_id
from app.db.session import engine
from app.ingestion.worker import worker
from app.services.cache import close_redis
from app.services.llm import LLMNotConfigured
from app.services.storage import S3Storage, get_storage

settings = get_settings()
configure_logging(settings.log_format, settings.log_level)
logger = logging.getLogger("documind")

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,  # no emails, IPs or request bodies in error reports
    )


async def _prepare_storage() -> None:
    storage = get_storage()
    if not isinstance(storage, S3Storage):
        await run_in_threadpool(storage.check)
        logger.info("Storing uploads on disk in %s", settings.local_storage_path)
        return
    # Object storage may still be booting under docker compose; retry briefly
    for attempt in range(1, 16):
        try:
            await run_in_threadpool(storage.ensure_bucket)
            logger.info("Storage bucket '%s' is ready", settings.s3_bucket)
            return
        except Exception:
            if attempt == 15:
                logger.exception("Storage unavailable; uploads that need it will fail until it is reachable")
                return
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _prepare_storage()
    if settings.worker_enabled:
        worker.start()
    yield
    await worker.stop()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="DocuMind API",
    description="Document Intelligence & Knowledge Graph Platform",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.enable_api_docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Multipart overhead on top of the file itself
_MAX_UPLOAD_REQUEST_BYTES = settings.max_upload_bytes + 1024 * 1024


@app.middleware("http")
async def assign_request_id(request: Request, call_next):
    # Every log line for this request carries the ID, and the client gets it back to quote
    token = request_id.set(new_request_id(request.headers.get("x-request-id")))
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id.get()
        return response
    finally:
        request_id.reset(token)


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    # Reject oversized uploads before the body is read and spooled to disk
    if request.method == "POST" and request.url.path == "/api/documents":
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > _MAX_UPLOAD_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": f"File is larger than {settings.max_upload_mb} MB"})
    return await call_next(request)


def _cors_headers(request: Request) -> dict[str, str]:
    # Responses from exception handlers bypass CORSMiddleware, so add the header ourselves
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


@app.exception_handler(LLMNotConfigured)
async def llm_not_configured_handler(request: Request, exc: LLMNotConfigured):
    logger.error("LLM call attempted but GROQ_API_KEY is not set")
    return JSONResponse(
        status_code=503, content={"detail": "AI features are not configured on this server"}, headers=_cors_headers(request)
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"}, headers=_cors_headers(request))


# ── API routes ──────────────────────────────────────────
api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(auth.router)
api.include_router(documents.router)
api.include_router(chat.router)
app.include_router(api)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def api_not_found(path: str):
    # Unknown /api paths return JSON 404 instead of falling through to the SPA
    raise HTTPException(status_code=404, detail="API route not found")


# ── Serve the built React single-page app ───────────────
possible_dist_dirs = [BACKEND_DIR.parent / "frontend" / "dist", Path("/app/frontend/dist")]
frontend_dist = next((d.resolve() for d in possible_dist_dirs if d.is_dir()), None)

if frontend_dist:
    if (frontend_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Resolve the path and refuse anything outside the build folder (e.g. "../../backend/.env")
        candidate = (frontend_dist / full_path).resolve()
        if candidate.is_relative_to(frontend_dist) and candidate.is_file():
            return FileResponse(candidate)

        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return {"status": "ok", "message": "DocuMind API is running"}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"status": "ok", "message": "DocuMind API is running"}
