"""Small shared helpers: ObjectId parsing, document serialisation, UTC time."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status


def now() -> datetime:
    return datetime.now(UTC)


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
