from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models
from auth import router as auth_router
from documents import router as docs_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(docs_router, prefix="/docs", tags=["Documents"])

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "DocuMind is running"}