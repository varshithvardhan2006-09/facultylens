"""Faculty and department analytics, and the bias & sarcasm panel (SPEC §10 analytics).

Access: a department's analytics are for its HoD and IQAC admins; a teacher's are for the
teacher, their HoD and admins. Everything reads stored aggregates, summaries and moderated,
redacted answers, and respects MIN_RESPONSES_FOR_DISPLAY per form.
"""

import asyncio
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.deps import Db, User, require_roles
from app.config import get_settings
from app.nlp import registry
from app.pipeline import analytics
from app.pipeline.aggregate import effective_field
from app.routers.overview import _hod_forms, _sees_feedback, _target
from app.services.forms_data import cycle_brief, form_rows
from app.utils import oid, to_jsonable

router = APIRouter(prefix="/analytics", tags=["analytics"])
Staff = Annotated[User, Depends(require_roles("admin", "hod", "faculty"))]
Leads = Annotated[User, Depends(require_roles("admin", "hod"))]


# --------------------------------------------------------------------------- loading


async def _department(db: Db, user: User, department_id: str) -> dict[str, Any]:
    dept = await db.departments.find_one({"_id": oid(department_id, "Department")})
    if not dept:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    if user["role"] != "admin" and user.get("department_id") != dept["_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only this department's HoD can see this.")
    return dept


async def _cycles_for(db: Db, form_query: dict[str, Any]) -> list[dict[str, Any]]:
    """Cycles that have teaching forms matching the query, newest first."""
    ids = await db.forms.distinct("cycle_id", {**form_query, "type": "teaching"})
    return await db.feedback_cycles.find({"_id": {"$in": ids}}).sort("opens_at", -1).to_list()


def _pick_cycle(cycles: list[dict[str, Any]], cycle: str | None) -> dict[str, Any] | None:
    if cycle:
        chosen = next((c for c in cycles if c["_id"] == oid(cycle, "Cycle")), None)
        if not chosen:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No teaching forms in that cycle")
        return chosen
    return cycles[0] if cycles else None


async def _department_forms(db: Db, dept_id, cycle_id) -> list[dict[str, Any]]:
    course_ids = await db.courses.distinct("_id", {"department_id": dept_id})
    return await db.forms.find(
        {"cycle_id": cycle_id, "type": "teaching", "course_id": {"$in": course_ids}}
    ).to_list()


async def _answers(db: Db, form_ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
    """Per form: visible, redacted answers and the 1-5 ratings of its responses."""
    responses = await db.responses.find(
        {"form_id": {"$in": form_ids}}, {"form_id": 1, "likert": 1}
    ).to_list()
    by_form: dict[ObjectId, dict[str, Any]] = {f: {"answers": [], "ratings": {}} for f in form_ids}
    for r in responses:
        for key, value in (r.get("likert") or {}).items():
            by_form[r["form_id"]]["ratings"].setdefault(key, []).append(float(value))
    async for a in db.analyses.find(
        {
            "response_id": {"$in": [r["_id"] for r in responses]},
            "model_version": registry.model_version(),
        },
        {"form_id": 1, "fields": 1},
    ):
        for f in a["fields"]:
            shown, text = effective_field(f)
            if shown:
                by_form[a["form_id"]]["answers"].append(
                    {
                        "id": f"{a['_id']}:{f['field']}",
                        "text": text,
                        "emotion": f.get("emotion") or {},
                        "uncertain": bool(f.get("sentiment_uncertain")),
                    }
                )
    return by_form


async def _department_scope(db: Db, user: User, department: str, cycle: str | None):
    dept = await _department(db, user, department)
    course_ids = await db.courses.distinct("_id", {"department_id": dept["_id"]})
    cycles = await _cycles_for(db, {"course_id": {"$in": course_ids}})
    chosen = _pick_cycle(cycles, cycle)
    forms = (
        await form_rows(db, await _department_forms(db, dept["_id"], chosen["_id"]))
        if chosen
        else []
    )
    teacher_ids = list({f["faculty_id"] for f in forms if f["faculty_id"]})
    teachers = await db.users.find(
        {"_id": {"$in": teacher_ids}}, {"name": 1, "gender": 1}
    ).to_list()
    head = {
        "department": {"id": str(dept["_id"]), "code": dept["code"], "name": dept["name"]},
        "cycles": [cycle_brief(c) for c in cycles],
        "cycle": cycle_brief(chosen) if chosen else None,
        "min_required": get_settings().min_responses_for_display,
    }
    return head, forms, teachers


# --------------------------------------------------------------------------- endpoints


@router.get("/faculty/{faculty_id}")
async def faculty_analytics(
    faculty_id: str, db: Db, user: Staff, cycle: Annotated[str | None, Query()] = None
) -> dict:
    """One teacher's offerings in a cycle, side by side, plus all of them combined."""
    target = await _target(db, faculty_id)
    if not await _sees_feedback(db, user, target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't see this feedback.")
    cycles = await _cycles_for(db, {"faculty_id": target["_id"]})
    chosen = _pick_cycle(cycles, cycle)
    minimum = get_settings().min_responses_for_display
    out: dict[str, Any] = {
        "cycles": [cycle_brief(c) for c in cycles],
        "cycle": cycle_brief(chosen) if chosen else None,
        "min_required": minimum,
        "offerings": [],
        "combined": None,
    }
    if chosen:
        forms = await form_rows(
            db,
            await db.forms.find(
                {
                    "faculty_id": target["_id"],
                    "cycle_id": chosen["_id"],
                    "type": "teaching",
                    **await _hod_forms(db, user, target),
                }
            ).to_list(),
        )
        forms.sort(key=lambda f: (f["course"]["code"], f["course"]["section"]))
        out["offerings"] = [analytics.offering_row(f, minimum) for f in forms]
        out["combined"] = analytics.teacher_row(target, forms, minimum)
    return to_jsonable(out)


@router.get("/department/{department_id}")
async def department_analytics(
    department_id: str, db: Db, user: Leads, cycle: Annotated[str | None, Query()] = None
) -> dict:
    head, forms, teachers = await _department_scope(db, user, department_id, cycle)
    by_teacher: dict[Any, list] = {}
    for f in forms:
        by_teacher.setdefault(f["faculty_id"], []).append(f)
    view = analytics.department_view(teachers, by_teacher, head["min_required"])
    return to_jsonable({**head, **view})


@router.get("/bias")
async def bias(
    db: Db,
    user: Leads,
    department: Annotated[str, Query()],
    cycle: Annotated[str | None, Query()] = None,
) -> dict:
    """The bias & sarcasm panel for one department: groups only, never names."""
    head, forms, teachers = await _department_scope(db, user, department, cycle)
    minimum = head["min_required"]
    usable = [f for f in forms if analytics.form_status(f, minimum) == "available"]
    data = await _answers(db, [f["form_id"] for f in usable])
    people = []
    for t in teachers:
        mine = [data[f["form_id"]] for f in usable if f["faculty_id"] == t["_id"]]
        if not mine:
            continue
        ratings: dict[str, list[float]] = {}
        for d in mine:
            for key, values in d["ratings"].items():
                ratings.setdefault(key, []).extend(values)
        people.append(
            {
                "gender": t.get("gender"),
                "answers": [a for d in mine for a in d["answers"]],
                "ratings": ratings,
            }
        )
    settings = get_settings()
    panel = await asyncio.to_thread(  # the first call imports scipy, which takes a moment
        analytics.bias_panel,
        people,
        settings.bias_min_group_faculty,
        settings.bias_min_group_answers,
    )
    head.pop("cycles", None)
    return to_jsonable({**head, **panel})


@router.get("/sarcasm")
async def sarcasm(
    db: Db,
    user: Staff,
    department: Annotated[str | None, Query()] = None,
    faculty: Annotated[str | None, Query()] = None,
    cycle: Annotated[str | None, Query()] = None,
) -> dict:
    """Possibly-sarcastic answers: rates per teacher for a department, or one teacher's ids."""
    if bool(department) == bool(faculty):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a department or a faculty id."
        )
    minimum = get_settings().min_responses_for_display
    if faculty:
        target = await _target(db, faculty)
        if not await _sees_feedback(db, user, target):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't see this feedback.")
        chosen = _pick_cycle(await _cycles_for(db, {"faculty_id": target["_id"]}), cycle)
        forms = await form_rows(
            db,
            await db.forms.find(
                {
                    "faculty_id": target["_id"],
                    "cycle_id": chosen["_id"],
                    "type": "teaching",
                    **await _hod_forms(db, user, target),
                }
            ).to_list()
            if chosen
            else [],
        )
        usable = [f["form_id"] for f in forms if analytics.form_status(f, minimum) == "available"]
        data = await _answers(db, usable)
        ids = [a["id"] for d in data.values() for a in d["answers"] if a["uncertain"]]
        return {"faculty": str(target["_id"]), "answer_ids": ids, "count": len(ids)}

    if user["role"] == "faculty":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only HoDs and IQAC see department rates.")
    head, forms, teachers = await _department_scope(db, user, department, cycle)
    usable = [f for f in forms if analytics.form_status(f, minimum) == "available"]
    data = await _answers(db, [f["form_id"] for f in usable])
    rows = []
    for t in teachers:
        answers = [
            a for f in usable if f["faculty_id"] == t["_id"] for a in data[f["form_id"]]["answers"]
        ]
        if answers:
            flagged = sum(a["uncertain"] for a in answers)
            rows.append(
                {
                    "id": str(t["_id"]),
                    "name": t["name"],
                    "answers": len(answers),
                    "flagged": flagged,
                    "rate": round(flagged / len(answers), 3),
                }
            )
    head.pop("cycles", None)
    return to_jsonable({**head, "teachers": sorted(rows, key=lambda r: -r["rate"])})
