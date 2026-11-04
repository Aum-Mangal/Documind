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

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg(cls, value: str) -> str:
        return to_asyncpg_url(value)


class Settings(DatabaseSettings):
    environment: Literal["development", "test", "production"] = "development"

    # ── Auth ─────────────────────────────────────────
    secret_key: str = Field(min_length=32)
    access_token_ttl_hours: int = 24

    # ── Database pool ────────────────────────────────
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # ── Redis (optional) ─────────────────────────────
    redis_url: str | None = None

    # ── S3-compatible object storage (optional) ──────
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str = "documind"
    s3_region: str = "auto"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
