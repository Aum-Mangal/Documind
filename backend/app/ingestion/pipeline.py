"""Turns one queued document into searchable chunks: read, chunk, embed, link entities, summarize."""
import asyncio
import logging

from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.ingestion.chunking import chunk_pages
from app.ingestion.progress import progress_bus
from app.knowledge.entities import extract as extract_entities
from app.knowledge.relations import extract_relations
from app.knowledge.store import apply_type_corrections, save_graph
from app.services.embeddings import embed_passages
from app.services.extraction import Page, extract_pages
from app.services.llm import LLMNotConfigured, track_usage
from app.services.ocr import ExtractionError
from app.services.quotas import add_usage_event, has_ai_allowance
from app.services.storage import get_storage
from app.services.summarizer import summarize

logger = logging.getLogger(__name__)

EMBED_BATCH = 64


def document_state(doc: Document) -> dict:
    """What progress streams and the documents API report about processing."""
    return {
        "id": doc.id,
        "status": doc.status,
        "stage": doc.stage,
        "progress": doc.progress,
        "error": doc.error,
        "page_count": doc.page_count,
    }


# The fields progress streams may see (others, like run_after, can be SQL expressions)
_PUBLIC_FIELDS = ("status", "stage", "progress", "error", "page_count")


async def set_state(session_factory: async_sessionmaker[AsyncSession], doc_id: int, **fields) -> None:
    async with session_factory() as session:
        await session.execute(update(Document).where(Document.id == doc_id).values(**fields, updated_at=func.now()))
        await session.commit()
    progress_bus.publish(doc_id, {"id": doc_id, **{k: v for k, v in fields.items() if k in _PUBLIC_FIELDS}})


def _summarize_or_none(text: str) -> str | None:
    # A failed summary shouldn't fail the document; it is still searchable without one
    try:
        return summarize(text)
    except LLMNotConfigured:
        return None
    except Exception:
        logger.exception("Summarization failed")
        return None


async def _load_pages(filename: str, storage_key: str | None, raw_text: str | None, max_pdf_pages: int) -> list[Page]:
    if storage_key:
        data = await asyncio.to_thread(get_storage().get, storage_key)
        return await asyncio.to_thread(extract_pages, data, filename, max_pdf_pages)
    if raw_text:
        # Documents uploaded before files were stored: rebuild chunks from the saved text
        return [Page(None, raw_text)]
    raise ExtractionError("This document has no stored file or text to process.")


async def process_document(session_factory: async_sessionmaker[AsyncSession], doc_id: int) -> None:
    settings = get_settings()
    async with session_factory() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            return
        user_id, filename, needs_summary = doc.user_id, doc.filename, not doc.summary
        storage_key, raw_text = doc.storage_key, doc.raw_text

    # Parsing and OCR can take minutes; don't hold a database connection meanwhile
    pages = await _load_pages(filename, storage_key, raw_text, settings.max_pdf_pages)

    await set_state(session_factory, doc_id, stage="chunking", progress=20)
    chunks = chunk_pages(pages, settings.chunk_target_tokens, settings.chunk_overlap_tokens)
    if not chunks:
        raise ExtractionError("No readable text was found in this file.")

    # The filename is prepended for embedding only, so every chunk carries a little document context
    header = f"{filename}\n\n"
    vectors = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start:start + EMBED_BATCH]
        vectors += await asyncio.to_thread(embed_passages, [header + c.content for c in batch])
        done = start + len(batch)
        await set_state(session_factory, doc_id, stage="embedding", progress=25 + int(60 * done / len(chunks)))

    full_text = "\n\n".join(p.text for p in pages if p.text)
    contents = [c.content for c in chunks]

    # Entities for the knowledge graph (local spaCy; no LLM yet)
    await set_state(session_factory, doc_id, stage="linking", progress=86)
    entities = await asyncio.to_thread(extract_entities, contents)

    # LLM work: relations between those entities, and the summary. Both are optional: the
    # document is fully searchable without them, so a used-up allowance or an LLM error
    # only leaves them out.
    async with session_factory() as session:
        allowed = await has_ai_allowance(session, user_id)
    summary, relations = None, []
    with track_usage() as usage:
        if allowed and settings.relation_extraction_enabled and entities:
            found = await asyncio.to_thread(extract_relations, contents, entities, settings.relation_max_chunks)
            apply_type_corrections(entities, found.types)
            relations = [r for r in found.relations if r.source in entities and r.target in entities]
        if allowed and needs_summary:
            await set_state(session_factory, doc_id, stage="summarizing", progress=92)
            summary = await asyncio.to_thread(_summarize_or_none, full_text)

    # Swap in the new chunks and graph and mark the document ready, in one transaction
    async with session_factory() as session, session.begin():
        doc = await session.get(Document, doc_id, with_for_update=True)
        if doc is None:
            return  # deleted while we were working
        # Deleting the chunks cascades to this document's entity mentions and relations
        await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
        chunk_rows = [
            Chunk(
                document_id=doc_id, user_id=user_id, ord=i,
                page_start=c.page_start, page_end=c.page_end,
                content=c.content, token_count=c.token_count, embedding=vector,
            )
            for i, (c, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        session.add_all(chunk_rows)
        await session.flush()
        await save_graph(session, user_id, doc_id, [c.id for c in chunk_rows], entities, relations)

        doc.raw_text = full_text
        doc.page_count = sum(1 for p in pages if p.number is not None) or None
        if summary:
            doc.summary = summary
        doc.status, doc.stage, doc.progress, doc.error, doc.locked_at = "ready", None, 100, None, None
        add_usage_event(session, user_id, "ingestion", usage)
        state = document_state(doc)

    progress_bus.publish(doc_id, state)
    logger.info("Document %s ready: %d chunks, %d entities, %d relations",
                doc_id, len(chunks), len(entities), len(relations))
