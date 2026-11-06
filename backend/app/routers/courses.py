"""Course offerings (code + academic year + semester + section) and enrolment.

Visibility: admin sees every offering; a HoD their department's; faculty the offerings they
teach; students the offerings they are enrolled in. Student lists are shown only to admin and
the department's HoD."""

from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.auth.deps import AdminUser, CurrentUser, Db, User
from app.schemas.org import CourseDetail, CourseIn, CourseOut, CourseUpdate, EnrolIn, EnrolResult
from app.services.audit import record
from app.utils import conflict, now, oid

router = APIRouter(prefix="/courses", tags=["courses"])

TEACHING_ROLES = ["faculty", "hod"]


def _visibility(user: User) -> dict[str, Any]:
    role = user["role"]
    if role == "admin":
        return {}
    if role == "hod":
        return {"department_id": user.get("department_id")}
    if role == "faculty":
        return {"faculty_ids": user["_id"]}
    return {"student_ids": user["_id"]}


def _can_see_students(user: User, course: dict[str, Any]) -> bool:
    return user["role"] == "admin" or (
        user["role"] == "hod" and user.get("department_id") == course.get("department_id")
    )


async def _people(db: Db, ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
    if not ids:
        return {}
    cursor = db.users.find({"_id": {"$in": ids}}, {"name": 1, "roll_no": 1})
    return {u["_id"]: u async for u in cursor}


def _ref(person: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(person["_id"]), "name": person["name"], "roll_no": person.get("roll_no")}


def _base(course: dict[str, Any], people: dict[ObjectId, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(course["_id"]),
        "code": course["code"],
        "name": course["name"],
        "department_id": str(course["department_id"]),
        "academic_year": course["academic_year"],
        "semester": course["semester"],
        "section": course["section"],
        "faculty": [_ref(people[f]) for f in course.get("faculty_ids", []) if f in people],
        "student_count": len(course.get("student_ids", [])),
    }


async def _detail(db: Db, user: User, course: dict[str, Any]) -> CourseDetail:
    show_students = _can_see_students(user, course)
    ids = list(course.get("faculty_ids", []))
    if show_students:
        ids += course.get("student_ids", [])
    people = await _people(db, ids)
    data = _base(course, people)
    if show_students:
        students = [people[s] for s in course.get("student_ids", []) if s in people]
        data["students"] = [_ref(s) for s in sorted(students, key=lambda s: s.get("roll_no", ""))]
    return CourseDetail.model_validate(data)


async def _get_visible(db: Db, user: User, course_id: str) -> dict[str, Any]:
    course = await db.courses.find_one({"_id": oid(course_id, "Course"), **_visibility(user)})
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


@router.get("", response_model=list[CourseOut])
async def list_courses(
    db: Db,
    user: CurrentUser,
    department_id: str | None = None,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    semester: Annotated[int | None, Query(ge=1, le=8)] = None,
) -> list[CourseOut]:
    query = _visibility(user)
    if department_id and user["role"] == "admin":
        query["department_id"] = oid(department_id, "Department")
    if academic_year:
        query["academic_year"] = academic_year
    if semester:
        query["semester"] = semester
    courses = (
        await db.courses.find(query)
        .sort([("academic_year", -1), ("semester", 1), ("code", 1), ("section", 1)])
        .to_list()
    )
    people = await _people(db, list({f for c in courses for f in c.get("faculty_ids", [])}))
    return [CourseOut.model_validate(_base(c, people)) for c in courses]


@router.post("", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
async def create_course(body: CourseIn, db: Db, admin: AdminUser) -> CourseDetail:
    department_id = oid(body.department_id, "Department")
    if not await db.departments.count_documents({"_id": department_id}):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Department not found.")
    doc = {
        **body.model_dump(),
        "department_id": department_id,
        "faculty_ids": [],
        "student_ids": [],
        "created_at": now(),
    }
    try:
        result = await db.courses.insert_one(doc)
    except DuplicateKeyError:
        raise conflict(
            f"{body.code} section {body.section} already exists for semester "
            f"{body.semester}, {body.academic_year}."
        ) from None
    doc["_id"] = result.inserted_id
    await record(db, admin, "course.create", str(doc["_id"]), {"code": body.code})
    return await _detail(db, admin, doc)


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(course_id: str, db: Db, user: CurrentUser) -> CourseDetail:
    return await _detail(db, user, await _get_visible(db, user, course_id))


@router.patch("/{course_id}", response_model=CourseDetail)
async def update_course(
    course_id: str, body: CourseUpdate, db: Db, admin: AdminUser
) -> CourseDetail:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    _id = oid(course_id, "Course")
    course = (
        await db.courses.find_one_and_update(
            {"_id": _id}, {"$set": changes}, return_document=ReturnDocument.AFTER
        )
        if changes
        else await db.courses.find_one({"_id": _id})
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    if changes:
        await record(db, admin, "course.update", course_id, {"fields": sorted(changes)})
    return await _detail(db, admin, course)


@router.post("/{course_id}/enrol", response_model=EnrolResult)
async def enrol(course_id: str, body: EnrolIn, db: Db, admin: AdminUser) -> EnrolResult:
    course = await db.courses.find_one({"_id": oid(course_id, "Course")})
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")

    wanted = sorted(set(body.add_roll_numbers) | set(body.remove_roll_numbers))
    students = {
        s["roll_no"]: s["_id"]
        async for s in db.users.find(
            {"roll_no": {"$in": wanted}, "role": "student", "is_active": {"$ne": False}},
            {"roll_no": 1},
        )
    }
    unknown = [r for r in wanted if r not in students]
    update: dict[str, Any] = {}
    add = [students[r] for r in body.add_roll_numbers if r in students]
    remove = [students[r] for r in body.remove_roll_numbers if r in students]
    if add:
        update["$addToSet"] = {"student_ids": {"$each": add}}

    if body.faculty_ids is not None:
        faculty_ids = [oid(f, "Faculty member") for f in dict.fromkeys(body.faculty_ids)]
        found = await db.users.count_documents(
            {
                "_id": {"$in": faculty_ids},
                "role": {"$in": TEACHING_ROLES},
                "is_active": {"$ne": False},
            }
        )
        if found != len(faculty_ids):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Every assigned teacher must be an active faculty member or HoD.",
            )
        update["$set"] = {"faculty_ids": faculty_ids}

    # $addToSet and $pull on the same field can't share one update, so pull separately.
    if update:
        await db.courses.update_one({"_id": course["_id"]}, update)
    if remove:
        await db.courses.update_one(
            {"_id": course["_id"]}, {"$pull": {"student_ids": {"$in": remove}}}
        )
    if update or remove:
        await record(
            db,
            admin,
            "course.enrol",
            course_id,
            {
                "added": len(add),
                "removed": len(remove),
                "faculty_set": body.faculty_ids is not None,
            },
        )
    course = await db.courses.find_one({"_id": course["_id"]})
    return EnrolResult(course=await _detail(db, admin, course), unknown_roll_numbers=unknown)
