"""User management (admin) and a department-scoped read for HoDs.

Temporary passwords are generated here, returned once in the response and never stored in
plain text. Users are deactivated rather than deleted so past records stay consistent."""

import csv
import io
import re
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from pymongo.errors import BulkWriteError, DuplicateKeyError

from app.auth.deps import AdminUser, Db, User, require_roles
from app.auth.security import generate_temp_password, hash_password_async
from app.schemas.users import (
    MAY_HAVE_GENDER,
    BulkJson,
    BulkRow,
    Credential,
    UserAdminOut,
    UserCreate,
    UserCreated,
    UserOut,
    UserPage,
    UserUpdate,
    role_rule_problems,
)
from app.services.audit import record
from app.utils import conflict, now, oid, to_jsonable

router = APIRouter(prefix="/users", tags=["users"])

MAX_CSV_BYTES = 1_000_000
CSV_COLUMNS = ["name", "email", "role", "department_code", "roll_no", "gender"]


def admin_out(user: dict[str, Any]) -> UserAdminOut:
    return UserAdminOut.model_validate(to_jsonable(user))


def public_out(user: dict[str, Any]) -> UserOut:
    return UserOut.model_validate(to_jsonable(user))


def _duplicate_message(exc: DuplicateKeyError) -> str:
    key = str(exc.details.get("keyPattern", {}) if exc.details else "")
    if "roll_no" in key:
        return "A user with this roll number already exists."
    return "A user with this email already exists."


async def _department_exists(db: Db, department_id: ObjectId | None) -> bool:
    return department_id is None or await db.departments.count_documents({"_id": department_id}) > 0


def _new_user_doc(data: dict[str, Any], password_hash: str) -> dict[str, Any]:
    doc = {
        "name": data["name"],
        "role": data["role"],
        "email": data.get("email"),
        "roll_no": data.get("roll_no"),
        "department_id": data.get("department_id"),
        "password_hash": password_hash,
        "must_change_pw": True,
        "is_active": True,
        "created_at": now(),
    }
    if data.get("gender") and data["role"] in MAY_HAVE_GENDER:
        doc["gender"] = data["gender"]
    # Omit empty optional keys so the sparse/partial unique indexes ignore them.
    return {k: v for k, v in doc.items() if v is not None}


@router.get("", response_model=UserPage)
async def list_users(
    db: Db,
    user: Annotated[User, Depends(require_roles("admin", "hod"))],
    role: str | None = None,
    department_id: str | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    include_inactive: bool = False,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> UserPage:
    query: dict[str, Any] = {}
    if role:
        query["role"] = role
    if user["role"] == "hod":
        # A HoD sees their own department only, whatever filter was asked for.
        query["department_id"] = user.get("department_id")
    elif department_id:
        query["department_id"] = oid(department_id, "Department")
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    if q:
        pattern = re.escape(q.strip())
        query["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"email": {"$regex": pattern, "$options": "i"}},
            {"roll_no": {"$regex": pattern, "$options": "i"}},
        ]
    total = await db.users.count_documents(query)
    cursor = (
        db.users.find(query, {"password_hash": 0})
        .sort([("role", 1), ("name", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    docs = await cursor.to_list()
    convert = admin_out if user["role"] == "admin" else public_out
    return UserPage(items=[convert(d) for d in docs], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: Db, admin: AdminUser) -> UserCreated:
    data = body.model_dump()
    data["department_id"] = oid(body.department_id, "Department") if body.department_id else None
    if not await _department_exists(db, data["department_id"]):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Department not found.")
    temp = generate_temp_password()
    doc = _new_user_doc(data, await hash_password_async(temp))
    try:
        result = await db.users.insert_one(doc)
    except DuplicateKeyError as exc:
        raise conflict(_duplicate_message(exc)) from None
    doc["_id"] = result.inserted_id
    await record(db, admin, "user.create", str(doc["_id"]), {"role": doc["role"]})
    return UserCreated(user=admin_out(doc), temp_password=temp)


def _parse_csv(raw: bytes) -> list[dict[str, Any]]:
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "CSV is larger than 1 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Save the CSV as UTF-8 and try again."
        ) from None
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = {"name", "role"} - set(headers)
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"CSV header must include: {', '.join(CSV_COLUMNS)} "
            f"(missing {', '.join(sorted(missing))}).",
        )
    rows = []
    try:
        for raw_row in reader:
            # Extra columns arrive under the key None, as a list: they aren't ours.
            row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
            rows.append({k: v for k, v in row.items() if k in CSV_COLUMNS and v != ""})
    except csv.Error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "That CSV file can't be read."
        ) from None
    return rows


def _field_message(error: dict[str, Any]) -> str:
    """'name: String should have at least 2 characters' or the plain rule message."""
    message = error["msg"].removeprefix("Value error, ")
    field = ".".join(str(part) for part in error.get("loc", ()))
    return f"{field}: {message}" if field else message


async def _read_bulk_rows(request: Request) -> tuple[list[dict[str, Any]], int]:
    """Return the rows and the number of the first data row (CSV line 1 is the header)."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Attach a CSV as 'file'.")
        rows, first = _parse_csv(await upload.read()), 2
    else:
        try:
            rows, first = BulkJson.model_validate(await request.json()).users, 1
        except (ValidationError, ValueError):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                'Send {"users": [...]} (1-1000 rows) or a CSV file.',
            ) from None
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The upload has no rows.")
    if len(rows) > 1000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Upload at most 1000 rows.")
    return rows, first


@router.post("/bulk")
async def bulk_create(request: Request, db: Db, admin: AdminUser, dry_run: bool = False) -> dict:
    """Validate every row first; insert nothing unless all rows are valid (all-or-nothing)."""
    rows, first_row = await _read_bulk_rows(request)
    departments = {d["code"]: d["_id"] async for d in db.departments.find({}, {"code": 1})}

    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_emails: dict[str, int] = {}
    seen_rolls: dict[str, int] = {}
    for index, raw in enumerate(rows, start=first_row):
        problems: list[str] = []
        try:
            row = BulkRow.model_validate(raw)
        except ValidationError as exc:
            problems = [_field_message(e) for e in exc.errors()]
            # Still report an unknown department, so one pass shows everything to fix.
            code = str(raw.get("department_code") or "").strip().upper()
            if code and code not in departments:
                problems.append(f"No department with code {code}.")
            errors.append({"row": index, "errors": problems, "input": raw})
            continue
        dept_id = None
        if row.department_code:
            dept_id = departments.get(row.department_code)
            if dept_id is None:
                problems.append(f"No department with code {row.department_code}.")
        if row.email:
            if row.email in seen_emails:
                problems.append(f"Same email as row {seen_emails[row.email]}.")
            seen_emails.setdefault(row.email, index)
        if row.roll_no:
            if row.roll_no in seen_rolls:
                problems.append(f"Same roll number as row {seen_rolls[row.roll_no]}.")
            seen_rolls.setdefault(row.roll_no, index)
        if problems:
            errors.append({"row": index, "errors": problems, "input": raw})
        else:
            data = row.model_dump(exclude={"department_code"})
            data["department_id"] = dept_id
            valid.append({"row": index, "data": data, "input": raw})

    # Clashes with users already in the database.
    existing_emails = {
        u["email"] async for u in db.users.find({"email": {"$in": list(seen_emails)}}, {"email": 1})
    }
    existing_rolls = {
        u["roll_no"]
        async for u in db.users.find({"roll_no": {"$in": list(seen_rolls)}}, {"roll_no": 1})
    }
    still_valid = []
    for item in valid:
        problems = []
        if item["data"].get("email") in existing_emails:
            problems.append("A user with this email already exists.")
        if item["data"].get("roll_no") in existing_rolls:
            problems.append("A user with this roll number already exists.")
        if problems:
            errors.append({"row": item["row"], "errors": problems, "input": item["input"]})
        else:
            still_valid.append(item)
    errors.sort(key=lambda e: e["row"])

    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "bulk_invalid",
                "message": f"{len(errors)} of {len(rows)} rows need fixing. Nothing was added.",
                "errors": to_jsonable(errors),
            },
        )
    if dry_run:
        return {"dry_run": True, "valid_rows": len(still_valid)}

    credentials: list[Credential] = []
    docs = []
    for item in still_valid:
        temp = generate_temp_password()
        docs.append(_new_user_doc(item["data"], await hash_password_async(temp)))
        credentials.append(
            Credential(
                name=item["data"]["name"],
                role=item["data"]["role"],
                email=item["data"].get("email"),
                roll_no=item["data"].get("roll_no"),
                temp_password=temp,
            )
        )
    try:
        await db.users.insert_many(docs, ordered=True)
    except BulkWriteError:  # a race with another admin: undo, so no password is lost half-way
        await db.users.delete_many({"_id": {"$in": [d["_id"] for d in docs if "_id" in d]}})
        raise conflict("Someone added one of these users just now. Nothing was added.") from None
    await record(db, admin, "user.bulk_create", None, {"count": len(docs)})
    return {"created": len(docs), "credentials": [c.model_dump() for c in credentials]}


async def _get_user_or_404(db: Db, user_id: str) -> dict[str, Any]:
    user = await db.users.find_one({"_id": oid(user_id, "User")})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserAdminOut)
async def update_user(user_id: str, body: UserUpdate, db: Db, admin: AdminUser) -> UserAdminOut:
    user = await _get_user_or_404(db, user_id)
    changes = body.model_dump(exclude_unset=True)
    if "department_id" in changes:
        changes["department_id"] = (
            oid(changes["department_id"], "Department") if changes["department_id"] else None
        )
        if not await _department_exists(db, changes["department_id"]):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Department not found.")
    if user["_id"] == admin["_id"] and (
        changes.get("is_active") is False or changes.get("role", "admin") != "admin"
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You can't deactivate or demote your own account."
        )
    merged = {**user, **changes}
    problems = role_rule_problems(
        merged["role"],
        merged.get("email"),
        merged.get("roll_no"),
        merged.get("department_id"),
        merged.get("gender") if merged["role"] in MAY_HAVE_GENDER else None,
    )
    if merged.get("annotator") and merged["role"] == "student":
        problems.append("Students can't be annotators.")
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(problems))

    to_set = {k: v for k, v in changes.items() if v is not None}
    to_unset = {k: "" for k, v in changes.items() if v is None}
    if merged["role"] not in MAY_HAVE_GENDER:
        to_set.pop("gender", None)
        to_unset["gender"] = ""
    update: dict[str, Any] = {}
    if to_set:
        update["$set"] = to_set
    if to_unset:
        update["$unset"] = to_unset
    if update:
        try:
            await db.users.update_one({"_id": user["_id"]}, update)
        except DuplicateKeyError as exc:
            raise conflict(_duplicate_message(exc)) from None
        if changes.get("is_active") is False:
            await db.refresh_tokens.update_many(
                {"user_id": user["_id"]}, {"$set": {"revoked": True}, "$unset": {"rotated_at": ""}}
            )
        await record(db, admin, "user.update", user_id, {"fields": sorted(changes)})
    return admin_out(await db.users.find_one({"_id": user["_id"]}))


@router.delete("/{user_id}", response_model=UserAdminOut)
async def deactivate_user(user_id: str, db: Db, admin: AdminUser) -> UserAdminOut:
    """Soft delete: the account can no longer sign in; its records stay intact."""
    user = await _get_user_or_404(db, user_id)
    if user["_id"] == admin["_id"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't deactivate your own account.")
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": False}})
    await db.refresh_tokens.update_many(
        {"user_id": user["_id"]}, {"$set": {"revoked": True}, "$unset": {"rotated_at": ""}}
    )
    await record(db, admin, "user.deactivate", user_id)
    return admin_out(await db.users.find_one({"_id": user["_id"]}))


@router.post("/{user_id}/reset-password")
async def reset_password(user_id: str, db: Db, admin: AdminUser) -> dict:
    user = await _get_user_or_404(db, user_id)
    temp = generate_temp_password()
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": await hash_password_async(temp), "must_change_pw": True}},
    )
    await db.refresh_tokens.update_many(
        {"user_id": user["_id"]}, {"$set": {"revoked": True}, "$unset": {"rotated_at": ""}}
    )
    await record(db, admin, "user.reset_password", user_id)
    return {"temp_password": temp}
