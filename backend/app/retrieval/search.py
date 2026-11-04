"""Hybrid retrieval: pgvector similarity and Postgres full-text search, fused in one query.

Each side ranks its own top candidates; Reciprocal Rank Fusion (score = sum of 1 / (k + rank))
merges them without needing the two kinds of score to be comparable. A passage found by
both sides rises to the top; one found only by exact keywords (names, codes, numbers that
embeddings blur) still gets in.
"""
from dataclasses import dataclass

import numpy as np
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import EMBEDDING_DIM

# The usual RRF constant; it damps the advantage of the very top ranks
RRF_K = 60

_HYBRID_SQL = text("""
WITH vector_hits AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> :query_vector) AS rank
      FROM chunks
     WHERE :use_vector
       AND user_id = :user_id
       AND (CAST(:document_ids AS integer[]) IS NULL OR document_id = ANY(:document_ids))
     ORDER BY embedding <=> :query_vector
     LIMIT :limit
),
keyword_hits AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.query) DESC) AS rank
      FROM chunks c,
           -- Match ANY of the question's terms (plainto_tsquery would require all of them, which a
           -- natural-language question almost never satisfies); ts_rank_cd still favours passages
           -- that contain more of them, close together
           to_tsquery('english', replace(plainto_tsquery('english', :query_text)::text, ' & ', ' | ')) AS q(query)
     WHERE :use_keyword
       AND c.user_id = :user_id
       AND (CAST(:document_ids AS integer[]) IS NULL OR c.document_id = ANY(:document_ids))
       AND c.tsv @@ q.query
     ORDER BY ts_rank_cd(c.tsv, q.query) DESC
     LIMIT :limit
),
fused AS (
    SELECT id,
           sum(CASE WHEN source = 'keyword' THEN :keyword_weight ELSE 1.0 END / (:rrf_k + rank)) AS rrf,
           min(rank) FILTER (WHERE source = 'vector') AS vector_rank,
           min(rank) FILTER (WHERE source = 'keyword') AS keyword_rank
      FROM (SELECT id, rank, 'vector' AS source FROM vector_hits
            UNION ALL
            SELECT id, rank, 'keyword' AS source FROM keyword_hits) hits
     GROUP BY id
)
SELECT c.id AS chunk_id, c.document_id, d.filename, c.page_start, c.page_end, c.content,
       f.rrf, f.vector_rank, f.keyword_rank
  FROM fused f
  JOIN chunks c ON c.id = f.id
  JOIN documents d ON d.id = c.document_id
 ORDER BY f.rrf DESC, c.id
 LIMIT :limit
""").bindparams(
    bindparam("query_vector", type_=HALFVEC(EMBEDDING_DIM)),
    bindparam("document_ids", type_=ARRAY(Integer)),
)


@dataclass(frozen=True)
class Candidate:
    chunk_id: int
    document_id: int
    filename: str
    page_start: int | None
    page_end: int | None
    content: str
    rrf: float
    vector_rank: int | None
    keyword_rank: int | None


async def hybrid_search(
    session: AsyncSession,
    user_id: int,
    query_text: str,
    query_vector: np.ndarray,
    document_ids: list[int] | None = None,
    limit: int = 30,
    mode: str = "hybrid",
) -> list[Candidate]:
    """mode: 'hybrid' (both, fused), or 'vector' / 'keyword' alone, for evaluation."""
    if mode not in ("hybrid", "vector", "keyword"):
        raise ValueError(f"Unknown search mode: {mode}")
    # With a per-user filter, a plain HNSW scan can return too few rows; pgvector 0.8's
    # iterative scan keeps searching until the filter is satisfied. (A custom setting, so
    # older pgvector versions simply ignore it.)
    await session.execute(text("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)"))
    rows = await session.execute(_HYBRID_SQL, {
        "user_id": user_id,
        "query_text": query_text,
        "query_vector": query_vector,
        "document_ids": document_ids,
        "limit": limit,
        "rrf_k": RRF_K,
        "keyword_weight": get_settings().rrf_keyword_weight,
        "use_vector": mode != "keyword",
        "use_keyword": mode != "vector",
    })
    return [Candidate(**row._mapping) for row in rows]
