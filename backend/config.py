from dotenv import load_dotenv
import os

load_dotenv()


def _require_secret_key() -> str:
    key = os.getenv("SECRET_KEY", "")
    if len(key) < 32:
        raise RuntimeError(
            "SECRET_KEY must be a random string of at least 32 characters. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return key


# ── Auth ─────────────────────────────────────────────
SECRET_KEY = _require_secret_key()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_HOURS = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "24"))

# ── HTTP ─────────────────────────────────────────────
# Comma-separated list of origins allowed to call the API from another domain.
# Leave empty when the frontend is served by this app (same origin).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
ENABLE_API_DOCS = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"

# ── Upload limits ────────────────────────────────────
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "200"))
MAX_QUESTION_CHARS = 2000
