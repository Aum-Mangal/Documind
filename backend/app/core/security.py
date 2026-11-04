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


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=settings.access_token_ttl_hours)}
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Returns the user id, or raises jwt.InvalidTokenError / ValueError."""
    payload = jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
    return int(payload["sub"])
