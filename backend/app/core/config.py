from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def to_asyncpg_url(url: str) -> str:
    """Normalise any Postgres URL (Supabase, Neon, Render, docker) to the asyncpg driver."""
    parts = urlsplit(url)
    if parts.scheme.split("+")[0] not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql://user:pass@host:5432/db)")
    query = dict(parse_qsl(parts.query))
    # asyncpg takes `ssl` instead of libpq's `sslmode`, and doesn't understand channel_binding
    if "sslmode" in query:
        query["ssl"] = query.pop("sslmode")
    query.pop("channel_binding", None)
    return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), parts.fragment))


class DatabaseSettings(BaseSettings):
    """The subset Alembic needs, so migrations run without app secrets."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str
    # Migrations need a direct connection: a transaction-mode pooler (Neon's "-pooler" host)
    # doesn't support everything Alembic does. Falls back to DATABASE_URL.
    migration_database_url: str | None = None

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _use_asyncpg(cls, value: str | None) -> str | None:
        return to_asyncpg_url(value) if value else None

    @property
    def migrations_url(self) -> str:
        return self.migration_database_url or self.database_url


class Settings(DatabaseSettings):
    environment: Literal["development", "test", "production"] = "development"

    # ── Auth ─────────────────────────────────────────
    secret_key: str = Field(min_length=32)
    access_token_ttl_hours: int = 24

    # ── Database pool ────────────────────────────────
    db_pool_size: int = 5
    db_max_overflow: int = 5
    # Set when DATABASE_URL goes through PgBouncer in transaction mode (Neon's pooled host):
    # prepared statements can't be cached across a pooler that swaps server connections
    db_pgbouncer: bool = False
    # Open a connection per use instead of keeping idle ones, so a serverless database
    # (Neon) can scale to zero between requests. Costs a TLS handshake per session.
    db_null_pool: bool = False

    # ── Logging and errors ───────────────────────────
    log_format: Literal["text", "json"] = "text"
    log_level: str = "INFO"
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0

    # ── Redis (optional) ─────────────────────────────
    redis_url: str | None = None

    # ── S3-compatible object storage (optional) ──────
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str = "documind"
    s3_region: str = "auto"
    # Where uploads go when S3 isn't configured (relative paths are inside backend/)
    local_storage_dir: str = "data/uploads"

    # ── Ingestion worker ─────────────────────────────
    worker_enabled: bool = True
    # Safety-net check for queued work; the worker is normally woken by uploads directly
    worker_idle_poll_seconds: int = 300
    ingest_max_attempts: int = 3
    # A job still marked processing after this long is assumed crashed and picked up again
    ingest_stale_minutes: int = 15
    chunk_target_tokens: int = 300
    chunk_overlap_tokens: int = 50

    # ── Retrieval ────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    reranker_enabled: bool = True
    retrieval_candidates: int = 30
    # Weight of the keyword ranking in Reciprocal Rank Fusion (the vector ranking has weight 1)
    rrf_keyword_weight: float = 0.5
    # How many of the fused results the cross-encoder rescores (its cost grows linearly)
    rerank_candidates: int = 10
    answer_sources: int = 5
    # Reranker scores are logits: unrelated passages score about -11, paraphrased matches -6 to -4,
    # clear matches above 0. For questions across the whole library, if even the best passage
    # scores below this we decline without calling the LLM. Kept low: vague questions and
    # list-like text (CVs, brochures) score around -9 to -11 while still being answerable, and the
    # LLM declines reliably when the sources lack the answer. Never applied to chosen documents.
    min_rerank_score: float = -10.5
    # Chosen documents with at most this many chunks are given to the LLM whole (~3,600 tokens)
    whole_document_chunks: int = 12
    chat_history_messages: int = 6

    # ── Knowledge graph ──────────────────────────────
    # Ask the LLM for relations between entities in the most entity-dense passages of each document
    relation_extraction_enabled: bool = True
    relation_max_chunks: int = 6
    # Weight, in Reciprocal Rank Fusion, of passages that mention entities named in the question.
    # Off by default: in the evaluation it lowered hybrid recall@1 (82% -> 73%) and didn't change
    # hybrid+rerank, because every passage naming a common entity qualifies. See eval/results.
    rrf_graph_weight: float = 0.0

    # ── Rate limits (per window; 0 disables one) ─────
    rate_limits_enabled: bool = True
    # Behind a proxy (Hugging Face Spaces, Caddy) the client IP is in X-Forwarded-For
    trust_proxy_headers: bool = False
    signup_per_hour: int = 5          # per IP
    login_per_minute: int = 20        # per IP
    login_per_email_per_15min: int = 10
    chat_per_minute: int = 20         # per user
    upload_per_hour: int = 60         # per user

    # ── Quotas (0 disables one) ──────────────────────
    daily_token_quota: int = 200_000  # LLM tokens per user per UTC day
    max_documents_per_user: int = 200
    max_storage_mb_per_user: int = 500

    # ── Caching ──────────────────────────────────────
    answer_cache_seconds: int = 3600
    query_embedding_cache_seconds: int = 86400

    # ── LLM ──────────────────────────────────────────
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"

    # ── HTTP ─────────────────────────────────────────
    # Origins allowed to call the API from another domain. Empty when the frontend is same-origin.
    cors_origins: Annotated[list[str], NoDecode] = []
    enable_api_docs: bool = False

    # ── Limits ───────────────────────────────────────
    max_upload_mb: int = 20
    max_pdf_pages: int = 200
    max_question_chars: int = 2000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def storage_enabled(self) -> bool:
        return bool(self.s3_endpoint_url)

    @property
    def local_storage_path(self) -> Path:
        path = Path(self.local_storage_dir)
        return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
