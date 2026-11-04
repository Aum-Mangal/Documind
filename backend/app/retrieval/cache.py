"""Caches for retrieval: query embeddings and whole answers.

An answer is cached under a key that includes a version of the documents it searched (how
many are ready and when the newest changed), so uploading, reprocessing or deleting a
document makes older cached answers unreachable without any explicit invalidation.
"""
import asyncio
import base64
import hashlib
import json
from dataclasses import asdict

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document
from app.retrieval.answer import Answer, Source
from app.services.cache import get_cache
from app.services.embeddings import embed_query


def _digest(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()


def normalise_question(question: str) -> str:
    return " ".join(question.lower().split())


async def cached_query_embedding(text: str) -> np.ndarray:
    settings = get_settings()
    key = f"emb:v1:{_digest(settings.embedding_model, text)}"
    cache = get_cache()
    if settings.query_embedding_cache_seconds > 0 and (hit := await cache.get(key)):
        return np.frombuffer(base64.b64decode(hit), dtype=np.float32)
    vector = (await asyncio.to_thread(embed_query, text)).astype(np.float32)
    if settings.query_embedding_cache_seconds > 0:
        await cache.set(key, base64.b64encode(vector.tobytes()).decode(), settings.query_embedding_cache_seconds)
    return vector


async def corpus_version(session: AsyncSession, user_id: int, document_ids: list[int] | None) -> str:
    query = select(func.count(), func.max(Document.updated_at)).where(
        Document.user_id == user_id, Document.status == "ready"
    )
    if document_ids:
        query = query.where(Document.id.in_(document_ids))
    count, latest = (await session.execute(query)).one()
    return f"{count}:{latest.isoformat() if latest else '-'}"


def answer_cache_key(user_id: int, document_ids: list[int] | None, version: str, question: str) -> str:
    scope = sorted(document_ids) if document_ids else None
    return f"answer:v1:{_digest(user_id, scope, version, normalise_question(question))}"


async def load_cached_answer(key: str) -> Answer | None:
    raw = await get_cache().get(key)
    if not raw:
        return None
    data = json.loads(raw)
    return Answer(
        text=data["text"],
        sources=[Source(**s) for s in data["sources"]],
        abstained=data["abstained"],
        search_query=data["search_query"],
    )


async def store_cached_answer(key: str, answer: Answer) -> None:
    ttl = get_settings().answer_cache_seconds
    if ttl > 0:
        await get_cache().set(key, json.dumps(asdict(answer)), ttl)
