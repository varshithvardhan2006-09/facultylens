"""Analysis jobs and the moderation queue (admin only)."""

import asyncio
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import db
from app.auth.deps import AdminUser, Db
from app.nlp import registry
from app.pipeline import jobs, summaries
from app.pipeline.aggregate import recompute_form
from app.services.audit import record
from app.utils import now, oid, to_jsonable

router = APIRouter(tags=["analysis"])


def _job_out(job: dict[str, Any]) -> dict[str, Any]:
    out = to_jsonable(job)
    out.pop("response_ids", None)
    return out


async def _cycle_form_ids(database: Db, cycle_id) -> list:
    return [f["_id"] async for f in database.forms.find({"cycle_id": cycle_id}, {"_id": 1})]


@router.get("/analysis/summary")
async def analysis_summary(database: Db, _admin: AdminUser, cycle: str) -> dict:
    """How much of a cycle is analysed for the current model version."""
    cycle_id = oid(cycle, "Cycle")
    form_ids = await _cycle_form_ids(database, cycle_id)
    ids = [
        r["_id"] async for r in database.responses.find({"form_id": {"$in": form_ids}}, {"_id": 1})
    ]
    analysed = await database.analyses.count_documents(
        {"response_id": {"$in": ids}, "model_version": registry.model_version()}
    )
    running = await database.analysis_jobs.find_one(
        {"cycle_id": cycle_id, "status": {"$in": ["queued", "running"]}}
    )
    return {
        "responses": len(ids),
        "analysed": analysed,
        "pending": len(ids) - analysed,
        "model_version": registry.model_version(),
        "active_job": _job_out(running) if running else None,
    }


@router.post("/analysis/run", status_code=status.HTTP_202_ACCEPTED)
async def run_analysis(database: Db, admin: AdminUser, cycle: str) -> dict:
    cycle_id = oid(cycle, "Cycle")
    if not await database.feedback_cycles.find_one({"_id": cycle_id}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cycle not found")
    active = await database.analysis_jobs.find_one(
        {"cycle_id": cycle_id, "status": {"$in": ["queued", "running"]}}
    )
    if active:
        return _job_out(active)  # one run per cycle at a time; the UI keeps polling it
    doc = {
        "kind": "cycle",
        "cycle_id": cycle_id,
        "status": "queued",
        "total": None,
        "done": 0,
        "requested_by": admin["_id"],
        "created_at": now(),
    }
    doc["_id"] = (await database.analysis_jobs.insert_one(doc)).inserted_id
    jobs.enqueue(doc["_id"])
    await record(database, admin, "analysis.run", cycle)
    return _job_out(doc)


@router.get("/analysis/status/{job_id}")
async def job_status(job_id: str, database: Db, _admin: AdminUser) -> dict:
    job = await database.analysis_jobs.find_one({"_id": oid(job_id, "Job")})
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _job_out(job)


@router.get("/analysis/jobs")
async def list_jobs(
    database: Db, _admin: AdminUser, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[dict]:
    rows = await database.analysis_jobs.find({}).sort("created_at", -1).limit(limit).to_list()
    return [_job_out(j) for j in rows]


# --------------------------------------------------------------------------- moderation


@router.get("/moderation/queue")
async def moderation_queue(
    database: Db,
    _admin: AdminUser,
    status_filter: Annotated[Literal["pending", "decided"], Query(alias="status")] = "pending",
    kind: Literal["hidden", "review"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    query: dict[str, Any] = {"status": status_filter}
    if kind:
        query["kind"] = kind
    total = await database.moderation_queue.count_documents(query)
    entries = (
        await database.moderation_queue.find(query)
        .sort([("score", -1), ("created_at", -1)])
        .limit(limit)
        .to_list()
    )
    analyses = {
        a["_id"]: a
        async for a in database.analyses.find(
            {"_id": {"$in": [e["analysis_id"] for e in entries]}}, {"fields": 1, "form_id": 1}
        )
    }
    forms = {
        f["_id"]: f
        async for f in database.forms.find(
            {"_id": {"$in": list({e["form_id"] for e in entries})}},
            {"course_id": 1, "faculty_id": 1, "type": 1},
        )
    }
    courses = {
        c["_id"]: c
        async for c in database.courses.find(
            {"_id": {"$in": list({f["course_id"] for f in forms.values()})}},
            {"code": 1, "name": 1, "section": 1},
        )
    }
    teachers = {
        u["_id"]: u["name"]
        async for u in database.users.find(
            {"_id": {"$in": [f["faculty_id"] for f in forms.values() if f.get("faculty_id")]}},
            {"name": 1},
        )
    }
    items = []
    for e in entries:
        analysis = analyses.get(e["analysis_id"])
        field = next(
            (f for f in (analysis or {}).get("fields", []) if f["field"] == e["field"]), None
        )
        if not field:
            continue
        form = forms.get(e["form_id"], {})
        course = courses.get(form.get("course_id"), {})
        items.append(
            {
                "id": str(e["_id"]),
                "kind": e["kind"],
                "status": e["status"],
                "score": e["score"],
                "label": e["label"],
                "field": e["field"],
                "text": field["redacted"],  # PII already removed; never the raw answer
                "flagged": [
                    {
                        "start": s["start"],
                        "end": s["end"],
                        "score": s["toxicity"],
                        "sentiment": s.get("sentiment"),
                    }
                    for s in field["sentences"]
                    if s["toxicity"] >= 0.4
                ],
                "decision": e.get("decision"),
                "edited_text": (field.get("moderation") or {}).get("text"),
                "course": " · ".join(
                    [
                        course.get("code", ""),
                        course.get("name", ""),
                        f"Section {course.get('section', '')}",
                    ]
                ),
                "form_type": form.get("type"),
                "teacher": teachers.get(form.get("faculty_id")),
                "created_at": e["created_at"],
                "decided_at": e.get("decided_at"),
            }
        )
    pending = await database.moderation_queue.count_documents({"status": "pending"})
    return {"items": items, "total": total, "pending": pending}


class DecisionIn(BaseModel):
    action: Literal["approve", "hide", "redact"]
    text: str | None = Field(default=None, max_length=2000)


@router.post("/moderation/{entry_id}/decision")
async def decide(entry_id: str, body: DecisionIn, database: Db, admin: AdminUser) -> dict:
    entry = await database.moderation_queue.find_one({"_id": oid(entry_id, "Queue item")})
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue item not found")
    if body.action == "redact" and not (body.text or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give the edited text to show.")
    decision = {
        "decision": body.action,
        "by": admin["_id"],
        "at": now(),
        **({"text": " ".join(body.text.split())} if body.action == "redact" else {}),
    }
    result = await database.analyses.update_one(
        {"_id": entry["analysis_id"], "fields.field": entry["field"]},
        {"$set": {"fields.$.moderation": decision}},
    )
    if not result.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The analysed comment is gone.")
    await database.moderation_queue.update_one(
        {"_id": entry["_id"]},
        {
            "$set": {
                "status": "decided",
                "decision": body.action,
                "decided_by": admin["_id"],
                "decided_at": now(),
            }
        },
    )
    form = await database.forms.find_one({"_id": entry["form_id"]})
    if form:
        await asyncio.to_thread(_refresh, form)
    await record(database, admin, "moderation.decision", entry_id, {"action": body.action})
    return {"status": "decided", "action": body.action}


def _refresh(form: dict[str, Any]) -> None:
    """After a decision: the aggregate changes, so its summary may too (worker-style, sync)."""
    sync_db, version = db.get_sync_db(), registry.model_version()
    recompute_form(sync_db, form, version)
    summaries.refresh_forms(sync_db, [form], version)


@router.post("/analysis/summaries", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_summaries(database: Db, admin: AdminUser, cycle: str) -> dict:
    """Rebuild every teaching summary in a cycle (e.g. after adding a Groq key)."""
    cycle_id = oid(cycle, "Cycle")
    if not await database.feedback_cycles.find_one({"_id": cycle_id}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cycle not found")
    active = await database.analysis_jobs.find_one(
        {"cycle_id": cycle_id, "status": {"$in": ["queued", "running"]}}
    )
    if active:
        return _job_out(active)
    doc = {
        "kind": "summaries",
        "cycle_id": cycle_id,
        "status": "queued",
        "total": None,
        "done": 0,
        "requested_by": admin["_id"],
        "created_at": now(),
    }
    doc["_id"] = (await database.analysis_jobs.insert_one(doc)).inserted_id
    jobs.enqueue(doc["_id"])
    await record(database, admin, "analysis.summaries", cycle)
    return _job_out(doc)
