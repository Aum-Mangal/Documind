import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.models import Document, User
from app.services.extraction import clean_filename, extract_text
from app.services.graph import generate_document_graph, generate_global_graph
from app.services.ner import extract_entities
from app.services.ocr import ExtractionError
from app.services.rag import answer_question
from app.services.summarizer import summarize

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Documents"])


async def _get_owned_document(session: DbSession, doc_id: int, user: User) -> Document:
    result = await session.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    return data


def _summarize_or_none(text: str) -> str | None:
    # A failed summary shouldn't lose the upload; the document is still searchable without it
    try:
        return summarize(text)
    except Exception:
        logger.exception("Summarization failed")
        return None


@router.post("/documents")
async def upload_document(user: CurrentUser, session: DbSession, file: UploadFile = File(...)):
    filename = clean_filename(file.filename)
    file_bytes = await _read_upload(file)

    # Parsing, OCR and the LLM summary are slow and blocking; keep them off the event loop
    try:
        raw_text = await run_in_threadpool(extract_text, file_bytes, filename, settings.max_pdf_pages)
    except ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    summary = await run_in_threadpool(_summarize_or_none, raw_text)

    doc = Document(user_id=user.id, filename=filename, raw_text=raw_text, summary=summary)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    return {
        "message": "File uploaded successfully",
        "document_id": doc.id,
        "filename": doc.filename,
        "text_preview": raw_text[:300],
    }


@router.get("/documents")
async def list_documents(user: CurrentUser, session: DbSession):
    result = await session.execute(
        select(Document.id, Document.filename, Document.summary, Document.created_at)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    return [
        {"id": d.id, "filename": d.filename, "summary": d.summary, "created_at": d.created_at}
        for d in result
    ]


@router.get("/documents/{doc_id}/entities")
async def get_entities(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user)
    entities = await run_in_threadpool(extract_entities, doc.raw_text or "")
    return {"document_id": doc_id, "filename": doc.filename, "entities": entities}


@router.get("/documents/{doc_id}/graph")
async def get_document_graph(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user)
    return await run_in_threadpool(generate_document_graph, doc.raw_text or "")


@router.get("/graph")
async def get_global_graph(user: CurrentUser, session: DbSession):
    result = await session.execute(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    )
    return await run_in_threadpool(generate_global_graph, list(result.scalars()))


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=settings.max_question_chars)


@router.post("/documents/{doc_id}/chat")
async def chat_with_document(doc_id: int, request: ChatRequest, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user)
    if not doc.raw_text:
        raise HTTPException(status_code=400, detail="Document has no text")

    rag_result = await run_in_threadpool(answer_question, request.question, doc.raw_text)
    return {
        "document_id": doc_id,
        "question": request.question,
        "answer": rag_result.get("answer", ""),
        "sources": rag_result.get("sources", []),
        "confidence": rag_result.get("confidence", 85),
    }
