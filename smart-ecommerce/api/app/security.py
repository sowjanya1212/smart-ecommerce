"""
Password hashing is byte-compatible with Django's PBKDF2-SHA256 hasher, so a user
created in the Django admin can log in through the API and vice-versa.
Format:  pbkdf2_sha256$<iterations>$<salt>$<base64(hash)>
"""
import base64
import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

_ALPHABET = string.ascii_letters + string.digits


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return base64.b64encode(digest).decode("ascii").strip()


def hash_password(password: str) -> str:
    salt = "".join(secrets.choice(_ALPHABET) for _ in range(22))
    iterations = settings.PASSWORD_ITERATIONS
    return f"pbkdf2_sha256${iterations}${salt}${_pbkdf2(password, salt, iterations)}"


def unusable_password() -> str:
    """Django treats values starting with '!' as 'cannot log in with a password'."""
    return "!" + secrets.token_urlsafe(32)


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, hashed = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        return hmac.compare_digest(_pbkdf2(password, salt, int(iterations)), hashed)
    except (ValueError, AttributeError):
        return False


def _create_token(user_id: int, token_type: str, expires: timedelta, role: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "type": token_type, "iat": now, "exp": now + expires}
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES), role)


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_DAYS))


def decode_token(token: str, expected_type: str = "access") -> dict:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload
