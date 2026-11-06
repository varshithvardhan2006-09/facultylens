"""Feedback cycles. Publishing creates the forms: one teaching form per offering x assigned teacher
and one curriculum form per offering, for offerings in the cycle's academic year whose semester
matches the term (odd term = semesters 1, 3, 5, 7)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.auth.deps import AdminUser, Db, User, require_roles
from app.feedback_spec import questions
from app.schemas.feedback import CycleIn, CycleOut, FormOut, PreviewOut
from app.services.audit import record
from app.services.forms_data import course_brief, cycle_brief, lookups, response_counts
from app.utils import now, oid

router = APIRouter(prefix="/cycles", tags=["cycles"])
Staff = Annotated[User, Depends(require_roles("admin", "hod", "faculty"))]
AdminOrHod = Annotated[User, Depends(require_roles("admin", "hod"))]


def _semesters(term: str) -> list[int]:
    return [1, 3, 5, 7] if term == "odd" else [2, 4, 6, 8]


async def _get(db: Db, cycle_id: str) -> dict[str, Any]:
    cycle = await db.feedback_cycles.find_one({"_id": oid(cycle_id, "Cycle")})
    if not cycle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cycle not found")
    return cycle


async def _counts(db: Db, cycle: dict[str, Any]) -> dict[str, Any]:
    forms = await db.forms.find({"cycle_id": cycle["_id"]}, {"type": 1, "course_id": 1}).to_list()
    counts = await response_counts(db, [f["_id"] for f in forms])
    courses = {
        c["_id"]: len(c.get("student_ids", []))
        async for c in db.courses.find(
            {"_id": {"$in": list({f["course_id"] for f in forms})}}, {"student_ids": 1}
        )
    }
    eligible = sum(courses.get(f["course_id"], 0) for f in forms)
    responses = sum(counts.values())
    return {
        "teaching_forms": sum(f["type"] == "teaching" for f in forms),
        "curriculum_forms": sum(f["type"] == "curriculum" for f in forms),
        "responses": responses,
        "eligible": eligible,
        "response_rate": round(responses / eligible, 4) if eligible else None,
    }


async def _out(db: Db, cycle: dict[str, Any], with_counts: bool) -> CycleOut:
    data = {**cycle, "id": str(cycle["_id"])}
    if with_counts:
        data["counts"] = await _counts(db, cycle)
    return CycleOut.model_validate(data)


async def _plan(db: Db, cycle: dict[str, Any]) -> tuple[list[dict], list[str], int]:
    """Forms that publishing should create, offerings without a teacher, forms already there."""
    offerings = (
        await db.courses.find(
            {
                "academic_year": cycle["academic_year"],
                "semester": {"$in": _semesters(cycle["term"])},
            }
        )
        .sort([("code", 1), ("section", 1)])
        .to_list()
    )
    existing = {
        (f["course_id"], f.get("faculty_id"), f["type"])
        async for f in db.forms.find({"cycle_id": cycle["_id"]})
    }
    planned, skipped = [], []
    for course in offerings:
        teachers = course.get("faculty_ids", [])
        if not teachers:
            skipped.append(f"{course['code']} section {course['section']}")
            continue
        wanted = [(course["_id"], t, "teaching") for t in teachers]
        wanted.append((course["_id"], None, "curriculum"))
        for course_id, faculty_id, form_type in wanted:
            if (course_id, faculty_id, form_type) not in existing:
                planned.append(
                    {
                        "cycle_id": cycle["_id"],
                        "course_id": course_id,
                        "faculty_id": faculty_id,
                        "type": form_type,
                        "questions": questions(form_type),
                        "created_at": now(),
                    }
                )
    return planned, skipped, len(existing)


@router.get("", response_model=list[CycleOut])
async def list_cycles(db: Db, user: Staff) -> list[CycleOut]:
    cycles = await db.feedback_cycles.find({}).sort("opens_at", -1).to_list()
    return [await _out(db, c, with_counts=user["role"] == "admin") for c in cycles]


@router.post("", response_model=CycleOut, status_code=status.HTTP_201_CREATED)
async def create_cycle(body: CycleIn, db: Db, admin: AdminUser) -> CycleOut:
    doc = {**body.model_dump(), "status": "draft", "created_at": now()}
    result = await db.feedback_cycles.insert_one(doc)
    doc["_id"] = result.inserted_id
    await record(db, admin, "cycle.create", str(doc["_id"]), {"name": body.name})
    return await _out(db, doc, with_counts=True)


@router.get("/{cycle_id}", response_model=CycleOut)
async def get_cycle(cycle_id: str, db: Db, user: Staff) -> CycleOut:
    return await _out(db, await _get(db, cycle_id), with_counts=user["role"] == "admin")


@router.get("/{cycle_id}/preview", response_model=PreviewOut)
async def preview_cycle(cycle_id: str, db: Db, _admin: AdminUser) -> PreviewOut:
    cycle = await _get(db, cycle_id)
    planned, skipped, existing = await _plan(db, cycle)
    return PreviewOut(
        offerings=len({p["course_id"] for p in planned}) + len(skipped),
        teaching_forms=sum(p["type"] == "teaching" for p in planned),
        curriculum_forms=sum(p["type"] == "curriculum" for p in planned),
        already_created=existing,
        without_teacher=skipped,
    )


@router.post("/{cycle_id}/publish", response_model=CycleOut)
async def publish_cycle(cycle_id: str, db: Db, admin: AdminUser) -> CycleOut:
    cycle = await _get(db, cycle_id)
    if cycle["status"] == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This cycle is closed. Create a new one.")
    planned, skipped, existing = await _plan(db, cycle)
    if not planned and not existing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No course offering in this academic year and term has a teacher assigned yet.",
        )
    created = 0
    for form in planned:
        try:
            await db.forms.insert_one(form)
            created += 1
        except DuplicateKeyError:
            pass  # created by a concurrent publish; publishing is idempotent
    changes = {"status": "open"}
    if not cycle.get("published_at"):
        changes["published_at"] = now()
    await db.feedback_cycles.update_one({"_id": cycle["_id"]}, {"$set": changes})
    await record(
        db, admin, "cycle.publish", cycle_id, {"forms_created": created, "skipped": len(skipped)}
    )
    return await _out(db, await _get(db, cycle_id), with_counts=True)


@router.post("/{cycle_id}/close", response_model=CycleOut)
async def close_cycle(cycle_id: str, db: Db, admin: AdminUser) -> CycleOut:
    cycle = await _get(db, cycle_id)
    if cycle["status"] != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an open cycle can be closed.")
    await db.feedback_cycles.update_one(
        {"_id": cycle["_id"]}, {"$set": {"status": "closed", "closed_at": now()}}
    )
    await record(db, admin, "cycle.close", cycle_id)
    return await _out(db, await _get(db, cycle_id), with_counts=True)


@router.get("/{cycle_id}/forms", response_model=list[FormOut])
async def cycle_forms(cycle_id: str, db: Db, user: AdminOrHod) -> list[FormOut]:
    """Forms with response counts (never response content). A HoD sees their department only."""
    cycle = await _get(db, cycle_id)
    forms = await db.forms.find({"cycle_id": cycle["_id"]}).to_list()
    _, courses, people = await lookups(db, forms)
    if user["role"] == "hod":
        forms = [
            f
            for f in forms
            if courses.get(f["course_id"], {}).get("department_id") == user.get("department_id")
        ]
    counts = await response_counts(db, [f["_id"] for f in forms])
    out = []
    for f in sorted(
        forms,
        key=lambda f: (
            courses[f["course_id"]]["code"],
            courses[f["course_id"]]["section"],
            f["type"] != "teaching",
        ),
    ):
        course = courses[f["course_id"]]
        teacher = people.get(f.get("faculty_id"))
        out.append(
            FormOut(
                id=str(f["_id"]),
                type=f["type"],
                cycle=cycle_brief(cycle),
                course=course_brief(course),
                faculty={"id": str(teacher["_id"]), "name": teacher["name"]} if teacher else None,
                questions=f["questions"],
                responses=counts.get(f["_id"], 0),
                eligible=len(course.get("student_ids", [])),
            )
        )
    return out
