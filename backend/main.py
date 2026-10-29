from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from config import CORS_ORIGINS, ENABLE_API_DOCS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
import models
from auth import router as auth_router
from documents import router as docs_router
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("documind")

try:
    models.Base.metadata.create_all(bind=engine)
except Exception:
    logger.warning("Could not connect to database on startup; server will still start", exc_info=True)

app = FastAPI(
    title="DocuMind API",
    description="Document Intelligence & Knowledge Graph Platform",
    docs_url="/api-docs" if ENABLE_API_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Multipart overhead on top of the file itself
_MAX_UPLOAD_REQUEST_BYTES = MAX_UPLOAD_BYTES + 1024 * 1024

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    # Reject oversized uploads before the body is read and spooled to disk
    if request.url.path == "/docs/upload":
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > _MAX_UPLOAD_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": f"File is larger than {MAX_UPLOAD_MB} MB"})
    return await call_next(request)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    # This response bypasses CORSMiddleware, so add the header for allowed origins ourselves
    headers = {}
    origin = request.headers.get("origin")
    if origin and origin in CORS_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    return JSONResponse(status_code=500, content={"detail": "Internal server error"}, headers=headers)

# ── API Routes ──────────────────────────────────────────
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(docs_router, prefix="/docs", tags=["Documents"])

API_PREFIXES = {"auth", "docs", "health", "db-check"}

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "DocuMind is running"}

@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database is connected and ready"}
    except Exception:
        logger.exception("Database check failed")
        return JSONResponse(status_code=503, content={"status": "error", "message": "Database unavailable"})

# ── Serve Built React Single Page Application (SPA) ────
# Look in ../frontend/dist or /app/frontend/dist
possible_dist_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend/dist")),
    "/app/frontend/dist"
]

frontend_dist = next((d for d in possible_dist_dirs if os.path.exists(d) and os.path.isdir(d)), None)

if frontend_dist:
    dist_root = Path(frontend_dist).resolve()
    assets_dir = dist_root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Exclude API endpoints from SPA fallback
        if full_path.split("/", 1)[0] in API_PREFIXES:
            raise HTTPException(status_code=404, detail="API route not found")

        # Resolve the path and refuse anything outside the build folder (e.g. "../../backend/.env")
        candidate = (dist_root / full_path).resolve()
        if candidate.is_relative_to(dist_root) and candidate.is_file():
            return FileResponse(candidate)

        index_file = dist_root / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return {"status": "ok", "message": "DocuMind API is running"}
else:
    @app.get("/")
    def root():
        return {"status": "ok", "message": "DocuMind API is running"}
