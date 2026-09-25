from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt silently truncates at 72 bytes; rejecting is better than a password
# where only the first 72 bytes ever mattered.
MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_problems(plain: str) -> list[str]:
    """Readable reasons a password is unacceptable. Empty list means it passes."""
    problems: list[str] = []
    if len(plain) < 8:
        problems.append("Use at least 8 characters.")
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        problems.append("Keep it under 72 bytes.")
    if plain.isdigit() or plain.isalpha():
        problems.append("Mix letters with digits or symbols.")
    if plain.lower() in {"password", "password1", "12345678", "qwertyui", "admin123"}:
        problems.append("That password is too common.")
    return problems


def _encode(subject: str, role: str, token_type: TokenType, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    ttl = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode(subject, role, "access", ttl), int(ttl.total_seconds())


def create_refresh_token(subject: str, role: str) -> tuple[str, int]:
    ttl = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode(subject, role, "refresh", ttl), int(ttl.total_seconds())


def decode_token(token: str, expect: TokenType = "access") -> dict:
    """Decode and check the token is the kind the caller asked for.

    Without the type check a refresh token would work as a bearer credential,
    which would quietly hand every client a 14-day access token.
    """
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    kind = payload.get("type", "access")
    if kind != expect:
        raise jwt.InvalidTokenError(f"Expected a {expect} token, got {kind}")
    return payload


# Older call sites used this name.
decode_access_token = decode_token
