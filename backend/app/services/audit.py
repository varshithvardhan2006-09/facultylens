"""Append-only audit log for admin actions (SPEC §13)."""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.utils import now, today


async def record(
    db: AsyncDatabase,
    actor: dict[str, Any] | None,
    action: str,
    target: str | None = None,
    details: dict[str, Any] | None = None,
    date_only: bool = False,
) -> None:
    await db.audit_log.insert_one(
        {
            "actor": actor["_id"] if actor else None,
            "actor_role": actor["role"] if actor else "system",
            "action": action,
            "target": target,
            "details": details or {},
            "at": today() if date_only else now(),
        }
    )
