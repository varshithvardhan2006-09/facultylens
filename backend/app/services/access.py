"""Who may see a teacher's page and feedback: one set of rules for every router."""

from typing import Any

from fastapi import HTTPException, status

from app.auth.deps import Db, User
from app.utils import oid


async def faculty_or_404(db: Db, faculty_id: str) -> dict[str, Any]:
    """The faculty member or HoD with this id, or a 404."""
    target = await db.users.find_one({"_id": oid(faculty_id, "Faculty member")})
    if not target or target["role"] not in ("faculty", "hod"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Faculty member not found")
    return target


async def sees_feedback(db: Db, user: User, target: dict[str, Any]) -> bool:
    if user["role"] == "admin" or user["_id"] == target["_id"]:
        return True
    if user["role"] != "hod":
        return False
    if target.get("department_id") and target.get("department_id") == user.get("department_id"):
        return True
    # A teacher from elsewhere who teaches a course in this HoD's department.
    return bool(
        await db.courses.find_one(
            {"department_id": user.get("department_id"), "faculty_ids": target["_id"]}, {"_id": 1}
        )
    )


async def hod_forms(db: Db, user: User, target: dict[str, Any]) -> dict[str, Any]:
    """A HoD reads other teachers' feedback for their own department's courses only."""
    if user["role"] != "hod" or user["_id"] == target["_id"]:
        return {}
    return {
        "course_id": {
            "$in": await db.courses.distinct("_id", {"department_id": user.get("department_id")})
        }
    }
