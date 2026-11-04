import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"


def _password_bytes(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes. Truncate on a character boundary, exactly as the
    # earlier passlib-based code did, so hashes created before the switch still verify.
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore").encode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


# Compared against when the email doesn't exist, so login takes the same time either way
DUMMY_HASH = hash_password("dummy-password-for-timing")


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    # Unique per token, so one token can be revoked (logout) without touching others.
    # None for tokens issued before token IDs existed; those simply expire.
    token_id: str | None
    expires_at: datetime


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(hours=settings.access_token_ttl_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenClaims:
    """Raises jwt.InvalidTokenError / ValueError for anything that isn't a valid, unexpired token."""
    payload = jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
    return TokenClaims(
        user_id=int(payload["sub"]),
        token_id=payload.get("jti"),
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
    )


def decode_access_token(token: str) -> int:
    """Returns the user id, or raises jwt.InvalidTokenError / ValueError."""
    return decode_token(token).user_id


def revoked_token_key(token_id: str) -> str:
    return f"revoked:{token_id}"
