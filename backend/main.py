from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models
from auth import router as auth_router
from documents import router as docs_router

try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"[WARNING] Could not connect to database on startup: {e}")
    print("[WARNING] Server will still start — DB may be available later.")

app = FastAPI(title="DocuMind API", description="Document Intelligence Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(docs_router, prefix="/docs", tags=["Documents"])

@app.get("/")
def root():
    return {"status": "ok", "message": "DocuMind API is running", "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "DocuMind is running"}