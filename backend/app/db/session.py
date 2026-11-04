from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy import NullPool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()


def _engine_options() -> tuple[str, dict]:
    url = make_url(_settings.database_url)
    options: dict = {"pool_pre_ping": True}  # drop connections a managed host closed while idle
    if _settings.db_pgbouncer:
        # PgBouncer in transaction mode hands each transaction any server connection, so
        # neither asyncpg nor SQLAlchemy may cache prepared statements, and names must be unique
        url = url.update_query_dict({"prepared_statement_cache_size": "0"})
        options["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
        }
    if _settings.db_null_pool:
        options["poolclass"] = NullPool
    else:
        options.update(pool_size=_settings.db_pool_size, max_overflow=_settings.db_max_overflow, pool_recycle=300)
    return url.render_as_string(hide_password=False), options


_url, _options = _engine_options()
engine = create_async_engine(_url, **_options)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
