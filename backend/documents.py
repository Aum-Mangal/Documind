from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from database import get_db
from models import Document, User
from auth import get_current_user
from config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, MAX_PDF_PAGES, MAX_QUESTION_CHARS
from docx import Document as DocxDocument
from services.summarizer import summarize
from services.ner import extract_entities
from services.rag import answer_question
from services.ocr import extract_text_from_pdf, extract_text_from_image, ExtractionError
from services.graph import generate_document_graph, generate_global_graph
from pydantic import BaseModel, Field
import io
import logging
import os
import re

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_FORMATS_MESSAGE = "Supported formats: PDF, DOCX, TXT, PNG, JPG, JPEG, WEBP"

# ── Upload validation ─────────────────────────────────
def _clean_filename(filename: str | None) -> str:
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "untitled"

def _matches_signature(ext: str, data: bytes) -> bool:
    """Checks the file's leading bytes so a renamed file can't pose as another type."""
    if ext == ".pdf":
        return data.startswith(b"%PDF-")
    if ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == ".docx":
        return data.startswith(b"PK\x03\x04")
    if ext == ".txt":
        return b"\x00" not in data[:8192]
    return False

async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is larger than {MAX_UPLOAD_MB} MB")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    return data

# ── Extract text from file (with OCR) ─────────────────
def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if not _matches_signature(ext, file_bytes):
        raise HTTPException(status_code=400, detail=SUPPORTED_FORMATS_MESSAGE)

    try:
        if ext == ".pdf":
            return extract_text_from_pdf(file_bytes, max_pages=MAX_PDF_PAGES)

        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            return extract_text_from_image(file_bytes)

        if ext == ".docx":
            docx = DocxDocument(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in docx.paragraphs])

        return file_bytes.decode("utf-8", errors="replace")
    except ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Text extraction failed for %s", filename)
        raise HTTPException(status_code=400, detail="Could not read this file. It may be corrupted.")

def _get_owned_document(db: Session, doc_id: int, user: User) -> Document:
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == user.id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

# ── Routes ───────────────────────────────────────────
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filename = _clean_filename(file.filename)
    file_bytes = await _read_upload(file)

    # Parsing, OCR and the LLM summary are slow and blocking; keep them off the event loop
    raw_text = await run_in_threadpool(extract_text, file_bytes, filename)
    summary = await run_in_threadpool(summarize, raw_text)

    doc = Document(
        user_id=user.id,
        filename=filename,
        raw_text=raw_text,
        summary=summary
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "message": "File uploaded successfully",
        "document_id": doc.id,
        "filename": doc.filename,
        "text_preview": raw_text[:300]
    }

@router.get("/documents")
def get_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.user_id == user.id).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "summary": d.summary,
            "created_at": d.created_at
        }
        for d in docs
    ]

@router.get("/documents/{doc_id}/entities")
def get_entities(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_owned_document(db, doc_id, user)
    entities = extract_entities(doc.raw_text or "")
    return {
        "document_id": doc_id,
        "filename": doc.filename,
        "entities": entities
    }

@router.get("/documents/{doc_id}/graph")
def get_document_graph_endpoint(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_owned_document(db, doc_id, user)
    return generate_document_graph(doc.raw_text or "")

@router.get("/graph/global")
def get_global_graph_endpoint(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.user_id == user.id).all()
    return generate_global_graph(docs)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)

@router.post("/documents/{doc_id}/chat")
def chat_with_document(
    doc_id: int,
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = _get_owned_document(db, doc_id, user)

    if not doc.raw_text:
        raise HTTPException(status_code=400, detail="Document has no text")

    rag_result = answer_question(request.question, doc.raw_text)
    return {
        "document_id": doc_id,
        "question": request.question,
        "answer": rag_result.get("answer", ""),
        "sources": rag_result.get("sources", []),
        "confidence": rag_result.get("confidence", 85)
    }
