from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
import models
from auth import router as auth_router
from documents import router as docs_router
import os

try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[WARNING] Could not connect to database on startup: {e}")
    print("[WARNING] Server will still start — DB may be available later.")

app = FastAPI(title="DocuMind API", description="Document Intelligence & Knowledge Graph Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Database / Server error: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*"}
    )

# ── API Routes ──────────────────────────────────────────
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(docs_router, prefix="/docs", tags=["Documents"])

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "DocuMind is running"}

@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database is connected and ready"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Database connection failed: {str(e)}"},
            headers={"Access-Control-Allow-Origin": "*"}
        )

# ── Serve Built React Single Page Application (SPA) ────
# Look in ../frontend/dist or /app/frontend/dist
possible_dist_dirs = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend/dist")),
    "/app/frontend/dist"
]

frontend_dist = next((d for d in possible_dist_dirs if os.path.exists(d) and os.path.isdir(d)), None)

if frontend_dist:
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Exclude API endpoints from SPA fallback
        if full_path.startswith(("auth", "docs", "health", "db-check")):
            raise HTTPException(status_code=404, detail="API route not found")

        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)

        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "ok", "message": "DocuMind API is running"}
else:
    @app.get("/")
    def root():
        return {"status": "ok", "message": "DocuMind API is running", "docs": "/docs"}