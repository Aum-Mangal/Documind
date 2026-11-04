"""Integration tests against a real PostgreSQL + pgvector database.

Run them by pointing TEST_DATABASE_URL at a server you can create databases on, e.g. the
docker compose one:

    TEST_DATABASE_URL=postgresql://documind:documind@localhost:5432/documind_test pytest tests/integration

The database named in the URL is dropped and recreated, then migrated with Alembic. The LLM
is replaced with a stand-in, so nothing calls Groq; the embedding and reranker models are real.
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import to_asyncpg_url
from app.core.security import create_access_token

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
BACKEND_DIR = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to run integration tests")


def _recreate_database(url: str) -> None:
    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    admin_url = urlunsplit((parts.scheme.split("+")[0], parts.netloc, "/postgres", "", ""))

    async def run():
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            await conn.execute(f'CREATE DATABASE "{name}"')
        finally:
            await conn.close()

    asyncio.run(run())


@pytest.fixture(scope="session")
def session_factory():
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run integration tests")
    _recreate_database(TEST_DATABASE_URL)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR, env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL}, check=True,
        capture_output=True,
    )
    # NullPool: tests touch the database from more than one event loop (the test client's
    # and asyncio.run's), and pooled asyncpg connections belong to a single loop
    engine = create_async_engine(to_asyncpg_url(TEST_DATABASE_URL), poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_tables(session_factory):
    async def truncate():
        async with session_factory() as session:
            await session.execute(text("TRUNCATE users, documents, chunks, conversations, messages, usage_events RESTART IDENTITY CASCADE"))
            await session.commit()

    asyncio.run(truncate())


class FakeLLM:
    """Stands in for Groq. Records every call so tests can see what the model was asked."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.answer = "Maria Okafor was appointed chief operating officer [Source 1]."

    def __call__(self, system: str, user: str) -> str:
        from app.services.llm import record_usage

        self.calls.append((system, user))
        record_usage(100, 20)
        if "Rewrite the user's latest question" in system:
            return "Why was the Atlas launch delayed?"
        if "Summarize" in system:
            return "A short summary."
        return self.answer


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    import app.retrieval.answer as answer_module
    import app.services.summarizer as summarizer_module

    monkeypatch.setattr(answer_module, "complete", fake)
    monkeypatch.setattr(summarizer_module, "complete", fake)
    return fake


@pytest.fixture
def api(session_factory, monkeypatch, llm):
    import app.api.routes.documents as documents_routes
    from app.db.session import get_session
    from app.main import app

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(documents_routes, "SessionLocal", session_factory)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def worker(session_factory):
    from app.ingestion.worker import IngestionWorker

    return IngestionWorker(session_factory)


def run(coro):
    return asyncio.run(coro)


def make_user(api, email: str = "reader@documind.dev") -> dict:
    """Creates a user through the API and returns auth headers."""
    api.post("/api/auth/signup", json={"email": email, "password": "integration-pass"})
    token = api.post("/api/auth/login", json={"email": email, "password": "integration-pass"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def forged_headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}
