from fastapi import APIRouter, HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.auth.deps import AdminUser, CurrentUser, Db
from app.schemas.org import DepartmentIn, DepartmentOut, DepartmentUpdate
from app.services.audit import record
from app.utils import conflict, now, oid, to_jsonable

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
async def list_departments(db: Db, _user: CurrentUser) -> list[DepartmentOut]:
    docs = await db.departments.find({}).sort("code", 1).to_list()
    return [DepartmentOut.model_validate(to_jsonable(d)) for d in docs]


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(body: DepartmentIn, db: Db, admin: AdminUser) -> DepartmentOut:
    doc = {**body.model_dump(), "created_at": now()}
    try:
        result = await db.departments.insert_one(doc)
    except DuplicateKeyError:
        raise conflict(f"Department code {body.code} is already used.") from None
    doc["_id"] = result.inserted_id
    await record(db, admin, "department.create", str(doc["_id"]), {"code": body.code})
    return DepartmentOut.model_validate(to_jsonable(doc))


@router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department(
    department_id: str, body: DepartmentUpdate, db: Db, admin: AdminUser
) -> DepartmentOut:
    _id = oid(department_id, "Department")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if changes:
        doc = await db.departments.find_one_and_update(
            {"_id": _id}, {"$set": changes}, return_document=ReturnDocument.AFTER
        )
    else:
        doc = await db.departments.find_one({"_id": _id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    if changes:
        await record(db, admin, "department.update", department_id, {"fields": sorted(changes)})
    return DepartmentOut.model_validate(to_jsonable(doc))
