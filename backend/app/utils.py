"""Small shared helpers: ObjectId parsing, document serialisation, UTC time."""

import re
import secrets
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

# Control characters have no place in text, and Word files can't hold them.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def now() -> datetime:
    return datetime.now(UTC)


def today() -> datetime:
    """Midnight UTC: for records that must not reveal when a student submitted."""
    return now().replace(hour=0, minute=0, second=0, microsecond=0)


def anon_id() -> ObjectId:
    """A random id. A normal ObjectId embeds its creation time, which would undo anonymity."""
    return ObjectId(secrets.token_bytes(12))


def oid(value: str, what: str = "Item") -> ObjectId:
    """Parse a path/body id; an invalid id is reported as not found."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found") from None


def to_jsonable(value: Any) -> Any:
    """ObjectId -> str, `_id` -> `id`, recursively."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out["id" if k == "_id" else k] = to_jsonable(v)
        return out
    return value


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)
