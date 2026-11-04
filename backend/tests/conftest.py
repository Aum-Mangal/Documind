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
    "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="documind-test-uploads-"),
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
