"""Shared test setup.

These tests need no database, Redis or object storage. Settings are pinned through
environment variables (which take priority over backend/.env), so a developer's local
.env can't change test results or point tests at a real database.
"""
import os
import tempfile

TEST_SECRET_KEY = "test-secret-key-0123456789-0123456789-abcdef"

os.environ.update({
    "ENVIRONMENT": "test",
    "SECRET_KEY": TEST_SECRET_KEY,
    # Nothing listens here: tests must never need a real database connection
    "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/test",
    "REDIS_URL": "",
    "S3_ENDPOINT_URL": "",
    "GROQ_API_KEY": "",
    "CORS_ORIGINS": "",
    "ENABLE_API_DOCS": "false",
    "MAX_UPLOAD_MB": "1",
    "MAX_PDF_PAGES": "5",
    "WORKER_ENABLED": "false",
    # Tests sign up and log in far more often than a person would; specific tests lower these
    "SIGNUP_PER_HOUR": "100000",
    "LOGIN_PER_MINUTE": "100000",
    "LOGIN_PER_EMAIL_PER_15MIN": "100000",
    "CHAT_PER_MINUTE": "100000",
    "UPLOAD_PER_HOUR": "100000",
    "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="documind-test-uploads-"),
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_cache():
    """Each test starts with an empty in-memory cache (rate-limit counters, cached answers)."""
    from app.services import cache

    cache._cache = None
    yield
    cache._cache = None
