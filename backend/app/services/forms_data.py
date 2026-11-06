"""Shared lookups for cycles, forms and responses (kept out of the routers to avoid repetition)."""

from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase


def cycle_brief(cycle: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(cycle["_id"]),
        "name": cycle["name"],
        "status": cycle["status"],
        "opens_at": cycle["opens_at"],
        "closes_at": cycle["closes_at"],
    }


def course_brief(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(course["_id"]),
        "code": course["code"],
        "name": course["name"],
        "academic_year": course["academic_year"],
        "semester": course["semester"],
        "section": course["section"],
        "department_id": str(course["department_id"]),
    }


async def lookups(
    db: AsyncDatabase, forms: list[dict[str, Any]]
) -> tuple[dict[ObjectId, dict], dict[ObjectId, dict], dict[ObjectId, dict]]:
    """Cycles, courses and teachers referenced by a list of forms, each keyed by _id."""
    cycle_ids = list({f["cycle_id"] for f in forms})
    course_ids = list({f["course_id"] for f in forms})
    faculty_ids = list({f["faculty_id"] for f in forms if f.get("faculty_id")})
    cycles = {c["_id"]: c async for c in db.feedback_cycles.find({"_id": {"$in": cycle_ids}})}
    courses = {c["_id"]: c async for c in db.courses.find({"_id": {"$in": course_ids}})}
    people = {u["_id"]: u async for u in db.users.find({"_id": {"$in": faculty_ids}}, {"name": 1})}
    return cycles, courses, people


async def response_counts(db: AsyncDatabase, form_ids: list[ObjectId]) -> dict[ObjectId, int]:
    pipeline = [
        {"$match": {"form_id": {"$in": form_ids}}},
        {"$group": {"_id": "$form_id", "n": {"$sum": 1}}},
    ]
    return {row["_id"]: row["n"] async for row in await db.responses.aggregate(pipeline)}


async def form_rows(db: AsyncDatabase, forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Forms with what analytics and reports need: counts, course and the stored aggregate."""
    from app.nlp import registry  # model_version only; no model is loaded

    if not forms:
        return []
    ids = [f["_id"] for f in forms]
    counts = await response_counts(db, ids)
    courses = {
        c["_id"]: c
        async for c in db.courses.find({"_id": {"$in": list({f["course_id"] for f in forms})}})
    }
    aggregates = {
        a["form_id"]: a["stats"]
        async for a in db.aggregates.find(
            {"form_id": {"$in": ids}, "model_version": registry.model_version()},
            {"form_id": 1, "stats": 1},
        )
    }
    return [
        {
            "form_id": f["_id"],
            "faculty_id": f.get("faculty_id"),
            "type": f["type"],
            "course": course_brief(courses[f["course_id"]]),
            "department_id": courses[f["course_id"]]["department_id"],
            "responses": counts.get(f["_id"], 0),
            "eligible": len(courses[f["course_id"]].get("student_ids", [])),
            "stats": aggregates.get(f["_id"]),
        }
        for f in forms
    ]
