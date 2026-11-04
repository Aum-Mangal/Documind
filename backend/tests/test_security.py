from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
import pytest

from app.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from tests.conftest import TEST_SECRET_KEY


def _token(payload: dict, key: str = TEST_SECRET_KEY, algorithm: str = JWT_ALGORITHM) -> str:
    return jwt.encode(payload, key, algorithm=algorithm)


def _in(hours: float) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


# ── Passwords ────────────────────────────────────────

def test_password_round_trip():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$2b$")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("Correct horse battery staple", hashed)


def test_each_hash_is_salted():
    assert hash_password("same password") != hash_password("same password")


def test_hashes_from_before_the_passlib_removal_still_verify():
    # The old code truncated to 72 bytes on a character boundary, then let bcrypt hash it
    password = "pässwörd-" + "é" * 40  # > 72 bytes, with multi-byte characters at the cut
    old_style = password.encode("utf-8")[:72].decode("utf-8", errors="ignore").encode("utf-8")
    legacy_hash = bcrypt.hashpw(old_style, bcrypt.gensalt()).decode()
    assert verify_password(password, legacy_hash)


def test_bcrypt_only_uses_the_first_72_bytes():
    prefix = "a" * 72
    assert verify_password(prefix + "anything", hash_password(prefix + "something else"))


def test_malformed_hash_does_not_raise():
    assert verify_password("password", "not-a-bcrypt-hash") is False


# ── Tokens ───────────────────────────────────────────

def test_token_round_trip():
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token_is_rejected():
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(_token({"sub": "1", "exp": _in(-1)}))


def test_token_signed_with_another_key_is_rejected():
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(_token({"sub": "1", "exp": _in(1)}, key="x" * 40))


def test_token_without_subject_is_rejected():
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(_token({"exp": _in(1)}))


def test_token_without_expiry_is_rejected():
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(_token({"sub": "1"}))


def test_unsigned_alg_none_token_is_rejected():
    unsigned = jwt.encode({"sub": "1", "exp": _in(1)}, None, algorithm="none")
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(unsigned)


def test_non_numeric_subject_is_rejected():
    with pytest.raises(ValueError):
        decode_access_token(_token({"sub": "admin", "exp": _in(1)}))
