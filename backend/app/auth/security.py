"""Password hashing (pwdlib + bcrypt), JWT access tokens (PyJWT) and opaque refresh tokens."""

import hashlib
import secrets
from datetime import timedelta
from functools import lru_cache
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.utils import now

ALGORITHM = "HS256"
# No 0/O, 1/l/I: temporary passwords are read off a screen or a printed sheet.
_TEMP_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


MAX_PASSWORD_BYTES = 72  # bcrypt's limit


def password_stamp(user: dict[str, Any]) -> int:
    """Changes whenever the password does, so older access tokens stop working."""
    changed = user.get("password_changed_at")
    return int(changed.timestamp()) if changed else 0


@lru_cache
def _hasher(rounds: int) -> PasswordHash:
    return PasswordHash((BcryptHasher(rounds=rounds),))


def hash_password(password: str) -> str:
    return _hasher(get_settings().bcrypt_rounds).hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        # bcrypt refuses these outright, and no stored password can be this long.
        password_hash = None
        password = password[:8]
    if not password_hash:
        # Still spend a hash so unknown usernames take as long as wrong passwords.
        _hasher(get_settings().bcrypt_rounds).hash(password)
        return False
    return _hasher(get_settings().bcrypt_rounds).verify(password, password_hash)


async def hash_password_async(password: str) -> str:
    """bcrypt is deliberately slow (~0.25 s); keep it off the event loop."""
    return await run_in_threadpool(hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    return await run_in_threadpool(verify_password, password, password_hash)


def generate_temp_password(length: int = 12) -> str:
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))


def create_access_token(user: dict[str, Any]) -> tuple[str, int]:
    """Return (token, expires_in_seconds). Claims are hints; the user is reloaded per request."""
    settings = get_settings()
    issued = now()
    expires_in = settings.jwt_access_minutes * 60
    payload = {
        "sub": str(user["_id"]),
        "role": user["role"],
        "dept": str(user["department_id"]) if user.get("department_id") else None,
        "mcp": bool(user.get("must_change_pw")),
        "type": "access",
        "pwd": password_stamp(user),
        "iat": issued,
        "exp": issued + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """Raise jwt.InvalidTokenError (incl. expiry) on any problem."""
    payload = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


def new_refresh_token() -> tuple[str, str]:
    """Return (opaque token for the cookie, sha256 hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
