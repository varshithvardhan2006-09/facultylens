"""Students list and submit feedback forms; staff can read a form in their scope.

A response stores no student id: only an HMAC that is different on every form (see
services/anonymity.py), the answers, the submission date (no time) and `is_synthetic`.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.auth.deps import CurrentUser, Db, User, require_roles
from app.feedback_spec import likert_keys, text_keys
from app.pipeline import jobs
from app.schemas.feedback import FormOut, MyForm, ResponseIn
from app.services.anonymity import student_form_hash
from app.services.audit import record
from app.services.forms_data import course_brief, cycle_brief, lookups, response_counts
from app.utils import anon_id, now, oid

router = APIRouter(prefix="/forms", tags=["forms"])
Student = Annotated[User, Depends(require_roles("student"))]


def _form_view(form, cycle, course, teacher, **extra) -> dict[str, Any]:
    return {
        "id": str(form["_id"]),
        "type": form["type"],
        "cycle": cycle_brief(cycle),
        "course": course_brief(course),
        "faculty": {"id": str(teacher["_id"]), "name": teacher["name"]} if teacher else None,
        **extra,
    }


@router.get("/my", response_model=list[MyForm])
async def my_forms(db: Db, student: Student) -> list[MyForm]:
    """Open forms for the offerings this student is enrolled in, with what they've submitted."""
    open_cycles = [c["_id"] async for c in db.feedback_cycles.find({"status": "open"}, {"_id": 1})]
    course_ids = [
        c["_id"] async for c in db.courses.find({"student_ids": student["_id"]}, {"_id": 1})
    ]
    if not open_cycles or not course_ids:
        return []
    forms = await db.forms.find(
        {"cycle_id": {"$in": open_cycles}, "course_id": {"$in": course_ids}}
    ).to_list()
    hashes = {f["_id"]: student_form_hash(student["_id"], f["_id"]) for f in forms}
    done = {
        r["form_id"]
        async for r in db.responses.find(
            {"form_id": {"$in": list(hashes)}, "student_hash": {"$in": list(hashes.values())}},
            {"form_id": 1},
        )
    }
    cycles, courses, people = await lookups(db, forms)
    rows = [
        _form_view(
            f,
            cycles[f["cycle_id"]],
            courses[f["course_id"]],
            people.get(f.get("faculty_id")),
            submitted=f["_id"] in done,
        )
        for f in forms
    ]
    rows.sort(
        key=lambda r: (
            r["course"]["code"],
            r["type"] != "teaching",
            r["faculty"] and r["faculty"]["name"],
        )
    )
    return [MyForm.model_validate(r) for r in rows]


async def _load(db: Db, form_id: str):
    form = await db.forms.find_one({"_id": oid(form_id, "Form")})
    if not form:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
    cycles, courses, people = await lookups(db, [form])
    return (
        form,
        cycles[form["cycle_id"]],
        courses[form["course_id"]],
        people.get(form.get("faculty_id")),
    )


def _staff_can_see(user: User, form: dict, course: dict) -> bool:
    if user["role"] == "admin":
        return True
    if user["role"] == "hod" and course.get("department_id") == user.get("department_id"):
        return True
    if user["role"] not in ("faculty", "hod"):
        return False
    if form.get("type") == "teaching":  # a co-teacher's form is that teacher's own
        return form.get("faculty_id") == user["_id"]
    return user["_id"] in course.get("faculty_ids", [])


@router.get("/{form_id}", response_model=FormOut)
async def get_form(form_id: str, db: Db, user: CurrentUser) -> FormOut:
    form, cycle, course, teacher = await _load(db, form_id)
    if user["role"] == "student":
        if user["_id"] not in course.get("student_ids", []) or cycle["status"] == "draft":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This form isn't for you.")
        submitted = await db.responses.count_documents(
            {"form_id": form["_id"], "student_hash": student_form_hash(user["_id"], form["_id"])}
        )
        extra = {"submitted": bool(submitted)}
    elif _staff_can_see(user, form, course):
        counts = await response_counts(db, [form["_id"]])
        extra = {
            "responses": counts.get(form["_id"], 0),
            "eligible": len(course.get("student_ids", [])),
        }
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't open this form.")
    view = _form_view(form, cycle, course, teacher, questions=form["questions"], **extra)
    return FormOut.model_validate(view)


@router.post("/{form_id}/responses", status_code=status.HTTP_201_CREATED)
async def submit_response(form_id: str, body: ResponseIn, db: Db, student: Student) -> dict:
    form, cycle, course, _ = await _load(db, form_id)
    if student["_id"] not in course.get("student_ids", []):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You aren't enrolled in this course.")
    if cycle["status"] != "open" or now() > cycle["closes_at"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This feedback cycle is closed.")
    if now() < cycle["opens_at"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This feedback cycle hasn't opened yet.")

    wanted = likert_keys(form["type"])
    missing = [k for k in wanted if k not in body.likert]
    unknown = [k for k in body.likert if k not in wanted]
    if missing or unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Rate every question ({len(missing)} missing)." if missing else "Unknown question.",
        )
    allowed_texts = set(text_keys(form["type"]))
    texts = {k: body.texts.get(k) for k in allowed_texts}

    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    doc = {
        "form_id": form["_id"],
        "student_hash": student_form_hash(student["_id"], form["_id"]),
        "type": form["type"],
        "likert": {k: body.likert[k] for k in wanted},
        "texts": texts,
        "submitted_on": today,
        "is_synthetic": False,
    }
    try:
        inserted = await db.responses.insert_one({"_id": anon_id(), **doc})
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You've already submitted this form."
        ) from None
    # No student id in the audit trail either: only that a form received a response.
    await record(db, None, "form.response", form_id, date_only=True)
    jobs.submit_auto(inserted.inserted_id)  # analysed in the background (SPEC §3 step 4)
    return {"status": "recorded"}
