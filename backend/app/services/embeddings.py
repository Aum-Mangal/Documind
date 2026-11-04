"""Local ONNX models: passage/query embeddings and a cross-encoder reranker.

Both load on first use and stay in memory. ONNX Runtime sessions are safe to call from
several threads, so the API and the ingestion worker share them.
"""
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.core.config import get_settings


@lru_cache
def get_embedder() -> TextEmbedding:
    return TextEmbedding(model_name=get_settings().embedding_model)


@lru_cache
def get_reranker() -> TextCrossEncoder:
    return TextCrossEncoder(model_name=get_settings().reranker_model)


def embed_passages(texts: list[str], batch_size: int = 32) -> list[np.ndarray]:
    # passage_embed applies the model's document-side formatting
    return list(get_embedder().passage_embed(texts, batch_size=batch_size))


def embed_query(text: str) -> np.ndarray:
    # query_embed adds bge's "Represent this sentence for searching relevant passages:" prefix
    return next(iter(get_embedder().query_embed(text)))


def rerank(query: str, passages: list[str]) -> list[float]:
    """Relevance score (a logit; higher is more relevant) of each passage to the query."""
    if not passages:
        return []
    return [float(x) for x in get_reranker().rerank(query, passages)]
