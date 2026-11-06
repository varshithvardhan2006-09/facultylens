"""NAAC Criterion 1.4: the Action Taken Report rows and the PDF / DOCX export (SPEC §12).

The IQAC admin drafts, edits and exports; a HoD reads, edits and approves their own
department's rows. The final export needs every row approved; a draft preview, marked on
every page, is always available to the admin.
"""

import asyncio
import re
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.auth.deps import AdminUser, Db, User, require_roles
from app.config import get_settings
from app.nlp import atr, registry
from app.pipeline.aggregate import effective_field
from app.routers.overview import _parse
from app.services import naac_charts, naac_render
from app.services.audit import record
from app.services.forms_data import form_rows, response_counts
from app.services.naac_data import report_data
from app.utils import CONTROL_CHARS, now, oid, to_jsonable

router = APIRouter(prefix="/reports/naac", tags=["reports"])
Leads = Annotated[User, Depends(require_roles("admin", "hod"))]
TEXT_FIELDS = ("issue", "action", "responsible", "timeline")


async def _cycle(db: Db, cycle: str) -> dict[str, Any]:
    doc = await db.feedback_cycles.find_one({"_id": oid(cycle, "Cycle")})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cycle not found")
    return doc


def _without_control_chars(value: Any) -> Any:
    """Older comments may still hold characters that a Word file can't store."""
    if isinstance(value, str):
        return CONTROL_CHARS.sub("", value)
    if isinstance(value, dict):
        return {k: _without_control_chars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_without_control_chars(v) for v in value]
    return value


def _scope(user: User) -> dict[str, Any]:
    """HoDs only ever see their own department's rows."""
    return {} if user["role"] == "admin" else {"department_id": user.get("department_id")}


async def _row(db: Db, user: User, cycle_id, action_id: str) -> dict[str, Any]:
    row = await db.action_taken.find_one({"_id": oid(action_id, "Action"), "cycle_id": cycle_id})
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    if user["role"] != "admin" and row["department_id"] != user.get("department_id"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This action belongs to another department.")
    return row


def _out(row: dict[str, Any]) -> dict[str, Any]:
    out = to_jsonable(row)
    out.pop("examples", None)
    return out


@router.post("/{cycle}/draft")
async def draft_actions(cycle: str, db: Db, admin: AdminUser) -> dict:
    """Draft (or re-draft) the Action Taken rows from the cycle's stored aggregates."""
    doc = await _cycle(db, cycle)
    forms = await form_rows(db, await db.forms.find({"cycle_id": doc["_id"]}).to_list())
    departments = await db.departments.find(
        {"_id": {"$in": list({f["department_id"] for f in forms})}}
    ).to_list()
    minimum = get_settings().min_responses_for_display
    fresh = await asyncio.to_thread(atr.draft, departments, forms, minimum)
    existing = await db.action_taken.find({"cycle_id": doc["_id"]}).to_list()
    inserts, replaces, removes, kept = atr.merge(existing, fresh)
    stamp = now()

    def stored(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "cycle_id": doc["_id"],
            **{k: v for k, v in row.items() if k != "examples"},
            "status": "draft",
            "edited": False,
            "updated_at": stamp,
        }

    if inserts:
        await db.action_taken.insert_many([{**stored(r), "created_at": stamp} for r in inserts])
    for row_id, row in replaces:
        await db.action_taken.update_one({"_id": row_id}, {"$set": stored(row)})
    if removes:
        await db.action_taken.delete_many({"_id": {"$in": removes}})
    counts = {"added": len(inserts), "replaced": len(replaces), "removed": len(removes)}
    await record(db, admin, "naac.draft", cycle, counts)
    return {**counts, "kept": kept, "issues": len(fresh)}


@router.get("/{cycle}/actions")
async def list_actions(cycle: str, db: Db, user: Leads) -> list[dict]:
    doc = await _cycle(db, cycle)
    rows = (
        await db.action_taken.find({"cycle_id": doc["_id"], **_scope(user)})
        .sort([("department_id", 1), ("kind", -1), ("evidence_count", -1)])
        .to_list()
    )
    return [_out(r) for r in rows]


class ActionIn(BaseModel):
    department_id: str
    kind: Literal["teaching", "curriculum", "other"] = "other"
    label: str = Field(min_length=2, max_length=120)
    issue: str = Field(min_length=5, max_length=600)
    action: str = Field(min_length=5, max_length=600)
    responsible: str = Field(min_length=2, max_length=160)
    timeline: str = Field(default=atr.DEFAULT_TIMELINE, min_length=2, max_length=120)


class ActionEdit(BaseModel):
    issue: str | None = Field(default=None, min_length=5, max_length=600)
    action: str | None = Field(default=None, min_length=5, max_length=600)
    responsible: str | None = Field(default=None, min_length=2, max_length=160)
    timeline: str | None = Field(default=None, min_length=2, max_length=120)
    status: Literal["draft", "approved"] | None = None


@router.post("/{cycle}/actions", status_code=status.HTTP_201_CREATED)
async def add_action(cycle: str, body: ActionIn, db: Db, user: Leads) -> dict:
    doc = await _cycle(db, cycle)
    dept_id = oid(body.department_id, "Department")
    if user["role"] != "admin" and dept_id != user.get("department_id"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can add actions for your department only."
        )
    if not await db.departments.find_one({"_id": dept_id}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    row = {
        "cycle_id": doc["_id"],
        "department_id": dept_id,
        "kind": body.kind,
        "key": f"manual:{uuid.uuid4().hex[:12]}",
        "label": body.label.strip(),
        "issue": body.issue.strip(),
        "evidence_count": 0,
        "evidence_ids": [],
        "action": body.action.strip(),
        "responsible": body.responsible.strip(),
        "timeline": body.timeline.strip(),
        "status": "draft",
        "source": "manual",
        "edited": True,
        "created_at": now(),
        "updated_at": now(),
        "created_by": user["_id"],
    }
    try:
        row["_id"] = (await db.action_taken.insert_one(row)).inserted_id
    except DuplicateKeyError as exc:  # pragma: no cover - uuid collision
        raise HTTPException(status.HTTP_409_CONFLICT, "Try again.") from exc
    await record(db, user, "naac.action.add", str(row["_id"]))
    return _out(row)


@router.put("/{cycle}/actions/{action_id}")
async def edit_action(cycle: str, action_id: str, body: ActionEdit, db: Db, user: Leads) -> dict:
    doc = await _cycle(db, cycle)
    row = await _row(db, user, doc["_id"], action_id)
    changes = {
        k: " ".join(v.split())
        for k in TEXT_FIELDS
        if (v := getattr(body, k)) is not None and " ".join(v.split()) != row.get(k)
    }
    update: dict[str, Any] = {**changes, "updated_at": now(), "updated_by": user["_id"]}
    if changes:
        update["edited"] = True
    new_status = body.status or ("draft" if changes and row["status"] == "approved" else None)
    if new_status:
        update["status"] = new_status
        if new_status == "approved":
            update.update(approved_by=user["_id"], approved_at=now())
    await db.action_taken.update_one({"_id": row["_id"]}, {"$set": update})
    await record(
        db, user, "naac.action.edit", action_id, {"fields": sorted(changes), "status": new_status}
    )
    return _out(await db.action_taken.find_one({"_id": row["_id"]}))


@router.delete("/{cycle}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(cycle: str, action_id: str, db: Db, admin: AdminUser) -> Response:
    doc = await _cycle(db, cycle)
    row = await _row(db, admin, doc["_id"], action_id)
    await db.action_taken.delete_one({"_id": row["_id"]})
    await record(db, admin, "naac.action.delete", action_id, {"issue": row["issue"]})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{cycle}/actions/{action_id}/evidence")
async def action_evidence(cycle: str, action_id: str, db: Db, user: Leads) -> list[dict]:
    """The redacted, visible student sentences behind a row; no teacher is named."""
    doc = await _cycle(db, cycle)
    row = await _row(db, user, doc["_id"], action_id)
    wanted = [p for p in (_parse(i) for i in row.get("evidence_ids", [])) if p]
    if not wanted:
        return []
    analyses = {
        a["_id"]: a
        async for a in db.analyses.find(
            {"_id": {"$in": [w[0] for w in wanted]}, "model_version": registry.model_version()}
        )
    }
    forms = {
        f["_id"]: f
        async for f in db.forms.find(
            {
                "_id": {"$in": list({a["form_id"] for a in analyses.values()})},
                "cycle_id": doc["_id"],
            }
        )
    }
    courses = {
        c["_id"]: c
        async for c in db.courses.find(
            {"_id": {"$in": list({f["course_id"] for f in forms.values()})}}, {"department_id": 1}
        )
    }
    counts = await response_counts(db, list(forms))
    minimum = get_settings().min_responses_for_display
    out = []
    for analysis_id, field_name, index in wanted:
        analysis = analyses.get(analysis_id)
        form = forms.get(analysis["form_id"]) if analysis else None
        if not form or counts.get(form["_id"], 0) < minimum:
            continue
        if courses[form["course_id"]]["department_id"] != row["department_id"]:
            continue
        field = next((f for f in analysis["fields"] if f["field"] == field_name), None)
        if not field:
            continue
        shown, text = effective_field(field)
        if not shown:
            continue
        edited = (field.get("moderation") or {}).get("decision") == "redact"
        sentence = (
            field["sentences"][index]
            if index is not None and 0 <= index < len(field["sentences"])
            else None
        )
        out.append(
            {
                "id": f"{analysis_id}:{field_name}" + (f":{index}" if index is not None else ""),
                "field": field_name,
                "text": text,
                "highlight": {"start": sentence["start"], "end": sentence["end"]}
                if sentence and not edited
                else None,
                "possibly_sarcastic": bool(field.get("sentiment_uncertain")),
                "edited_by_admin": edited,
            }
        )
    return out


@router.get("/{cycle}/status")
async def report_status(cycle: str, db: Db, user: Leads) -> dict:
    """What still stands between this cycle and a final export."""
    doc = await _cycle(db, cycle)
    form_query: dict[str, Any] = {"cycle_id": doc["_id"]}
    if user["role"] != "admin":  # a HoD's checklist covers their own department
        form_query["course_id"] = {
            "$in": await db.courses.distinct("_id", {"department_id": user.get("department_id")})
        }
    form_ids = await db.forms.distinct("_id", form_query)
    responses = await db.responses.count_documents({"form_id": {"$in": form_ids}})
    response_ids = await db.responses.distinct("_id", {"form_id": {"$in": form_ids}})
    analysed = await db.analyses.count_documents(
        {"response_id": {"$in": response_ids}, "model_version": registry.model_version()}
    )
    scope = {"cycle_id": doc["_id"], **_scope(user)}
    total = await db.action_taken.count_documents(scope)
    approved = await db.action_taken.count_documents({**scope, "status": "approved"})
    return {
        "cycle": {"id": str(doc["_id"]), "name": doc["name"], "status": doc["status"]},
        "responses": responses,
        "analysed": analysed,
        "actions": total,
        "approved": approved,
        "ready": total > 0 and approved == total and analysed == responses,
    }


async def _export(cycle: str, fmt: str, draft: bool, db: Db, admin: User) -> Response:
    doc = await _cycle(db, cycle)
    if not draft:
        pending = await db.action_taken.count_documents(
            {"cycle_id": doc["_id"], "status": {"$ne": "approved"}}
        )
        total = await db.action_taken.count_documents({"cycle_id": doc["_id"]})
        if pending or not total:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{pending} action(s) still need approval."
                if total
                else "Draft the Action Taken Report first.",
            )
    data = _without_control_chars(await report_data(db, doc))

    def build() -> bytes:
        with naac_charts.LOCK:
            charts = naac_charts.all_charts(data)
        render = naac_render.render_pdf if fmt == "pdf" else naac_render.render_docx
        return render(data, charts, draft)

    content = await asyncio.to_thread(build)
    # Headers hold Latin-1 only, and a cycle may be called "2026–27 Odd Sem".
    cycle_name = re.sub(r"[^A-Za-z0-9._-]+", "-", doc["name"]).strip("-")
    name = f"NAAC-1.4-{cycle_name}{'-DRAFT' if draft else ''}.{fmt}"
    media = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    await record(db, admin, f"naac.export.{fmt}", cycle, {"draft": draft})
    return Response(
        content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.get("/{cycle}.pdf")
async def export_pdf(
    cycle: str, db: Db, admin: AdminUser, draft: Annotated[bool, Query()] = False
) -> Response:
    return await _export(cycle, "pdf", draft, db, admin)


@router.get("/{cycle}.docx")
async def export_docx(
    cycle: str, db: Db, admin: AdminUser, draft: Annotated[bool, Query()] = False
) -> Response:
    return await _export(cycle, "docx", draft, db, admin)
