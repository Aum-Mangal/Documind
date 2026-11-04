import asyncio
import hashlib
import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import defer

from app.api.deps import CurrentUser, DbSession
from app.core import rate_limit
from app.core.config import get_settings
from app.db.models import Document, User
from app.db.session import SessionLocal
from app.ingestion.pipeline import document_state
from app.ingestion.progress import progress_bus
from app.ingestion.worker import worker
from app.services.extraction import clean_filename, file_extension, validate_upload
from app.services.graph import generate_document_graph, generate_global_graph
from app.services.ner import extract_entities
from app.services.ocr import ExtractionError
from app.services.quotas import ensure_storage_allowance
from app.services.storage import get_storage

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Documents"])

TERMINAL_STATUSES = {"ready", "failed"}
SSE_KEEPALIVE_SECONDS = 15


def serialize_document(doc: Document) -> dict:
    return {
        **document_state(doc),
        "filename": doc.filename,
        "summary": doc.summary,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


async def _get_owned_document(session: DbSession, doc_id: int, user: User, *, with_text: bool = False) -> Document:
    query = select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    if not with_text:
        query = query.options(defer(Document.raw_text))
    doc = (await session.execute(query)).scalars().first()
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


def _duplicate_response(doc: Document) -> JSONResponse:
    # 200 rather than 202: nothing new was queued
    return JSONResponse(status_code=200, content=jsonable_encoder({"document": serialize_document(doc), "duplicate": True}))


async def _find_duplicate(session: DbSession, user: User, sha256: str) -> Document | None:
    query = select(Document).where(Document.user_id == user.id, Document.sha256 == sha256).options(defer(Document.raw_text))
    return (await session.execute(query)).scalars().first()


# ── Upload and manage ────────────────────────────────

@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(user: CurrentUser, session: DbSession, file: UploadFile = File(...)):
    await rate_limit.enforce(
        "upload", str(user.id), settings.upload_per_hour, 3600,
        "You've uploaded a lot of files in the last hour. Try again later.",
    )
    filename = clean_filename(file.filename)
    data = await _read_upload(file)
    try:
        mime_type = validate_upload(data, filename)
    except ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    sha256 = hashlib.sha256(data).hexdigest()
    if existing := await _find_duplicate(session, user, sha256):
        return _duplicate_response(existing)
    await ensure_storage_allowance(session, user.id, len(data))

    doc = Document(
        user_id=user.id, filename=filename, mime_type=mime_type, size_bytes=len(data),
        sha256=sha256, status="queued",
    )
    session.add(doc)
    try:
        await session.flush()  # assigns doc.id for the storage key
        doc.storage_key = f"users/{user.id}/documents/{doc.id}/original{file_extension(filename)}"
        await run_in_threadpool(get_storage().put, doc.storage_key, data, mime_type)
        await session.commit()
    except IntegrityError:
        # The same file was uploaded twice at once; the other request won
        await session.rollback()
        if existing := await _find_duplicate(session, user, sha256):
            return _duplicate_response(existing)
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Storing upload failed")
        raise HTTPException(status_code=503, detail="Could not store the file. Please try again.") from e

    await session.refresh(doc)
    worker.wake()
    return {"document": serialize_document(doc), "duplicate": False}


@router.get("/documents")
async def list_documents(user: CurrentUser, session: DbSession):
    result = await session.execute(
        select(Document).where(Document.user_id == user.id)
        .options(defer(Document.raw_text))
        .order_by(Document.created_at.desc(), Document.id.desc())
    )
    return [serialize_document(d) for d in result.scalars()]


@router.get("/documents/{doc_id}")
async def get_document(doc_id: int, user: CurrentUser, session: DbSession):
    return serialize_document(await _get_owned_document(session, doc_id, user))


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user)
    storage_key = doc.storage_key
    await session.delete(doc)  # chunks cascade in the database
    await session.commit()
    if storage_key:
        try:
            await run_in_threadpool(get_storage().delete, storage_key)
        except Exception:
            logger.exception("Could not delete stored file %s", storage_key)
    progress_bus.publish(doc_id, {"id": doc_id, "status": "deleted"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{doc_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user)
    if doc.status not in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="This document is already being processed")
    doc.status, doc.stage, doc.progress, doc.error = "queued", None, 0, None
    doc.attempts, doc.locked_at, doc.run_after = 0, None, func.now()
    await session.commit()
    await session.refresh(doc)
    worker.wake()
    return serialize_document(doc)


@router.get("/documents/{doc_id}/file")
async def download_original(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user)
    if not doc.storage_key:
        raise HTTPException(status_code=404, detail="The original file isn't stored for this document")
    data = await run_in_threadpool(get_storage().get, doc.storage_key)
    return Response(
        content=data,
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename)}"},
    )


# ── Live processing progress (server-sent events) ────

async def _read_state(doc_id: int) -> dict | None:
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id, options=[defer(Document.raw_text)])
        return document_state(doc) if doc else None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


@router.get("/documents/{doc_id}/events")
async def document_events(doc_id: int, request: Request, user: CurrentUser, session: DbSession):
    await _get_owned_document(session, doc_id, user)
    # Don't hold a pooled connection for the life of the stream
    await session.close()

    async def stream():
        async with progress_bus.subscribe(doc_id) as queue:
            # Read after subscribing, so a change between the two can't be missed
            state = await _read_state(doc_id)
            if state is None:
                yield _sse({"id": doc_id, "status": "deleted"})
                return
            yield _sse(state)
            while state["status"] not in TERMINAL_STATUSES and not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_SECONDS)
                except TimeoutError:
                    # Quiet for a while: re-check the database (another instance may be doing the work)
                    latest = await _read_state(doc_id)
                    if latest is None:
                        yield _sse({"id": doc_id, "status": "deleted"})
                        return
                    if latest != state:
                        state = latest
                        yield _sse(state)
                    else:
                        yield ": keep-alive\n\n"
                    continue
                if event.get("status") == "deleted":
                    yield _sse(event)
                    return
                state = {**state, **event}
                yield _sse(state)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Entities and graphs ──────────────────────────────

@router.get("/documents/{doc_id}/entities")
async def get_entities(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user, with_text=True)
    entities = await run_in_threadpool(extract_entities, doc.raw_text or "")
    return {"document_id": doc_id, "filename": doc.filename, "entities": entities}


@router.get("/documents/{doc_id}/graph")
async def get_document_graph(doc_id: int, user: CurrentUser, session: DbSession):
    doc = await _get_owned_document(session, doc_id, user, with_text=True)
    return await run_in_threadpool(generate_document_graph, doc.raw_text or "")


@router.get("/graph")
async def get_global_graph(user: CurrentUser, session: DbSession):
    result = await session.execute(
        select(Document).where(Document.user_id == user.id, Document.status == "ready")
        .order_by(Document.created_at.desc())
    )
    return await run_in_threadpool(generate_global_graph, list(result.scalars()))
