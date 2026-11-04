import pytest
from pydantic import ValidationError

from app.core.config import Settings, to_asyncpg_url
from tests.conftest import TEST_SECRET_KEY


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgresql+psycopg2://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        # Neon / Supabase style: libpq's sslmode becomes asyncpg's ssl; channel_binding is dropped
        (
            "postgresql://u:p@host/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@host/db?ssl=require",
        ),
    ],
)
def test_database_urls_are_normalised_for_asyncpg(url, expected):
    assert to_asyncpg_url(url) == expected


@pytest.mark.parametrize("url", ["sqlite:///./documind.db", "mysql://u:p@host/db", "not a url"])
def test_non_postgres_urls_are_rejected(url):
    with pytest.raises(ValueError, match="PostgreSQL"):
        to_asyncpg_url(url)


def _settings(**overrides) -> Settings:
    values = {"secret_key": TEST_SECRET_KEY, "database_url": "postgresql://u:p@h/db", **overrides}
    return Settings(_env_file=None, **values)


def test_short_secret_key_is_rejected():
    with pytest.raises(ValidationError, match="secret_key"):
        _settings(secret_key="too-short")


def test_cors_origins_accept_comma_separated_string():
    settings = _settings(cors_origins="https://a.example, https://b.example ,")
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_empty_cors_origins_means_none_allowed():
    assert _settings(cors_origins="").cors_origins == []


def test_derived_values():
    settings = _settings(max_upload_mb=3, s3_endpoint_url="")
    assert settings.max_upload_bytes == 3 * 1024 * 1024
    assert settings.storage_enabled is False
    assert _settings(s3_endpoint_url="http://s3:8333").storage_enabled is True


def test_migrations_use_the_direct_url_when_given():
    settings = _settings(database_url="postgresql://u:p@pooler-host/db", migration_database_url="postgresql://u:p@direct-host/db")
    assert settings.database_url == "postgresql+asyncpg://u:p@pooler-host/db"
    assert settings.migrations_url == "postgresql+asyncpg://u:p@direct-host/db"
    assert _settings().migrations_url == _settings().database_url


def test_json_log_lines_carry_the_request_id(capsys):
    import json
    import logging

    from app.core.logging import configure_logging, request_id

    configure_logging("json", "INFO")
    token = request_id.set("req-42")
    try:
        logging.getLogger("documind.test").info("hello")
    finally:
        request_id.reset(token)
        configure_logging("text", "INFO")
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert (line["message"], line["request_id"], line["level"]) == ("hello", "req-42", "INFO")
