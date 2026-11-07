"""Faculty profile data: manual editing plus ORCID / Semantic Scholar import with review.

Access: the faculty member (or HoD) who owns the profile and admins can read and write;
a HoD can read the profiles of their own department; everyone else gets 403.
Imported items wait in `pending_imports` until the owner accepts or rejects each one.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from app.auth.deps import Db, User, require_roles
from app.limiter import limiter
from app.schemas.profiles import (
    ITEM_MODELS,
    AcceptIn,
    BulkDecisionIn,
    ImportResult,
    OrcidImportIn,
    ProfileDataIn,
    ProfileDataOut,
    S2ImportIn,
)
from app.services import orcid as orcid_service
from app.services import semantic_scholar as s2_service
from app.services.access import faculty_or_404
from app.services.audit import record
from app.services.http import ExternalServiceError
from app.services.profile_items import (
    SECTION_FOR_KIND,
    existing_keys,
    item_key,
    new_id,
)
from app.utils import now, upsert_one

router = APIRouter(prefix="/faculty", tags=["profiles"])
Staff = Annotated[User, Depends(require_roles("admin", "hod", "faculty"))]
IMPORT_LIMIT = "10/minute"
SECTIONS = ("qualifications", "experience", "publications", "achievements")


# --------------------------------------------------------------------------- access


async def _faculty(db: Db, user: User, faculty_id: str, write: bool) -> dict[str, Any]:
    target = await faculty_or_404(db, faculty_id)
    if user["role"] == "admin" or user["_id"] == target["_id"]:
        return target
    same_dept = target.get("department_id") and target.get("department_id") == user.get(
        "department_id"
    )
    if not write and user["role"] == "hod" and same_dept:
        return target
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't open this profile.")


def _can_edit(user: User, target: dict[str, Any]) -> bool:
    return user["role"] == "admin" or user["_id"] == target["_id"]


async def _profile(db: Db, user_id) -> dict[str, Any]:
    return await db.faculty_profiles.find_one({"user_id": user_id}) or {"user_id": user_id}


async def _out(db: Db, viewer: User, target: dict[str, Any], profile: dict[str, Any]):
    dept = None
    if target.get("department_id"):
        dept = await db.departments.find_one({"_id": target["department_id"]})
    courses = (
        await db.courses.find({"faculty_ids": target["_id"]})
        .sort([("academic_year", -1), ("semester", 1), ("code", 1)])
        .to_list()
    )
    data = {
        "designation": profile.get("designation"),
        "photo_url": profile.get("photo_url"),
        "interests": profile.get("interests", []),
        **{s: profile.get(s, []) for s in SECTIONS},
        "orcid": profile.get("orcid"),
        "s2_author_id": profile.get("s2_author_id"),
        "pending_imports": profile.get("pending_imports", []),
        "import_log": profile.get("import_log", {}),
        "updated_at": profile.get("updated_at"),
        "can_edit": _can_edit(viewer, target),
        "user": {
            "id": str(target["_id"]),
            "name": target["name"],
            "role": target["role"],
            "email": target.get("email"),
            "department_id": str(target["department_id"]) if target.get("department_id") else None,
            "department_code": dept["code"] if dept else None,
            "department_name": dept["name"] if dept else None,
        },
        "courses_taught": [
            {
                "id": str(c["_id"]),
                "code": c["code"],
                "name": c["name"],
                "academic_year": c["academic_year"],
                "semester": c["semester"],
                "section": c["section"],
            }
            for c in courses
        ],
    }
    return ProfileDataOut.model_validate(data)


async def _save(db: Db, user_id, changes: dict[str, Any]) -> dict[str, Any]:
    await upsert_one(
        db.faculty_profiles,
        {"user_id": user_id},
        {"$set": {**changes, "updated_at": now()}, "$setOnInsert": {"created_at": now()}},
    )
    return await _profile(db, user_id)


def _http_error(exc: ExternalServiceError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


# --------------------------------------------------------------------------- read / edit


@router.get("/{faculty_id}/profile-data", response_model=ProfileDataOut)
async def get_profile_data(faculty_id: str, db: Db, user: Staff) -> ProfileDataOut:
    target = await _faculty(db, user, faculty_id, write=False)
    return await _out(db, user, target, await _profile(db, target["_id"]))


@router.put("/{faculty_id}/profile-data", response_model=ProfileDataOut)
async def put_profile_data(
    faculty_id: str, body: ProfileDataIn, db: Db, user: Staff
) -> ProfileDataOut:
    target = await _faculty(db, user, faculty_id, write=True)
    data = body.model_dump()
    for section in SECTIONS:
        for item in data[section]:
            item["id"] = item.get("id") or new_id()
    profile = await _save(db, target["_id"], data)
    await record(db, user, "profile.update", faculty_id)
    return await _out(db, user, target, profile)


# --------------------------------------------------------------------------- imports


async def _queue(
    db: Db, target: dict[str, Any], source: str, items_by_kind: dict[str, list], ref: dict
) -> tuple[dict[str, int], int, int, dict[str, Any]]:
    """Add new items to pending; skip duplicates; let S2 fill gaps in pending ORCID papers."""
    profile = await _profile(db, target["_id"])
    keys = existing_keys(profile)
    pending = list(profile.get("pending_imports", []))
    pending_by_key = {p["key"]: p for p in pending}
    added: dict[str, int] = {}
    skipped = enriched = 0
    for kind, items in items_by_kind.items():
        for data in items:
            key = item_key(kind, data)
            if key in keys:
                skipped += 1
                twin = pending_by_key.get(key)
                if twin and kind == "publication" and source == "s2":
                    filled = False
                    for field in ("citations", "tldr", "s2_paper_id"):
                        if twin["data"].get(field) is None and data.get(field) is not None:
                            twin["data"][field] = data[field]
                            filled = True
                    enriched += filled
                continue
            keys.add(key)
            entry = {
                "id": new_id(),
                "kind": kind,
                "source": source,
                "data": data,
                "key": key,
                "fetched_at": now(),
            }
            pending.append(entry)
            pending_by_key[key] = entry
            added[kind] = added.get(kind, 0) + 1
    log = {
        "at": now(),
        "added": sum(added.values()),
        "skipped": skipped,
        "enriched": enriched,
        "ref": next(iter(ref.values())),
    }
    profile = await _save(
        db, target["_id"], {"pending_imports": pending, f"import_log.{source}": log, **ref}
    )
    return added, skipped, enriched, profile


@router.post("/{faculty_id}/import/orcid", response_model=ImportResult)
@limiter.limit(IMPORT_LIMIT)
async def import_orcid(
    request: Request, faculty_id: str, body: OrcidImportIn, db: Db, user: Staff
) -> ImportResult:
    target = await _faculty(db, user, faculty_id, write=True)
    try:
        orcid = orcid_service.parse_orcid(body.orcid)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    try:
        items = await orcid_service.fetch_orcid(orcid)
    except ExternalServiceError as exc:
        if exc.status == 404:
            raise HTTPException(404, f"No public ORCID record for {orcid}.") from None
        raise _http_error(exc) from None
    added, skipped, enriched, profile = await _queue(db, target, "orcid", items, {"orcid": orcid})
    await record(db, user, "profile.import_orcid", faculty_id, {"orcid": orcid, **added})
    return ImportResult(
        added=added,
        skipped=skipped,
        enriched=enriched,
        profile=await _out(db, user, target, profile),
    )


@router.get("/{faculty_id}/semantic-scholar/search")
@limiter.limit(IMPORT_LIMIT)
async def search_semantic_scholar(
    request: Request,
    faculty_id: str,
    db: Db,
    user: Staff,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[dict]:
    await _faculty(db, user, faculty_id, write=True)
    try:
        return await s2_service.search_authors(q.strip())
    except ExternalServiceError as exc:
        raise _http_error(exc) from None


@router.post("/{faculty_id}/import/semantic-scholar", response_model=ImportResult)
@limiter.limit(IMPORT_LIMIT)
async def import_semantic_scholar(
    request: Request, faculty_id: str, body: S2ImportIn, db: Db, user: Staff
) -> ImportResult:
    target = await _faculty(db, user, faculty_id, write=True)
    try:
        author_id = s2_service.parse_author_id(body.author)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    try:
        papers = await s2_service.fetch_papers(author_id)
    except ExternalServiceError as exc:
        if exc.status == 404:
            raise HTTPException(404, f"No Semantic Scholar author {author_id}.") from None
        raise _http_error(exc) from None
    added, skipped, enriched, profile = await _queue(
        db, target, "s2", {"publication": papers}, {"s2_author_id": author_id}
    )
    await record(db, user, "profile.import_s2", faculty_id, {"author": author_id, **added})
    return ImportResult(
        added=added,
        skipped=skipped,
        enriched=enriched,
        profile=await _out(db, user, target, profile),
    )


# --------------------------------------------------------------------------- review


def _accept_into(profile: dict[str, Any], entry: dict[str, Any], override: dict | None) -> None:
    """Validate the (optionally edited) item and move it into its section. Raises 422."""
    kind = entry["kind"]
    section = SECTION_FOR_KIND[kind]
    if kind == "interest":
        tag = " ".join(str((override or entry["data"]).get("tag", "")).split())[:60]
        if not tag:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The interest is empty.")
        interests = profile.setdefault("interests", [])
        if tag.lower() not in {t.lower() for t in interests}:
            interests.append(tag)
        return
    data = {**entry["data"], **(override or {}), "id": entry["id"], "source": entry["source"]}
    try:
        item = ITEM_MODELS[kind].model_validate(data).model_dump()
    except ValidationError as exc:
        message = "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message) from None
    profile.setdefault(section, []).append(item)


# ProfileDataIn's limits: the profile must stay valid, or the editor can't load it any more.
SECTION_LIMITS = {
    name: next(
        m.max_length for m in ProfileDataIn.model_fields[name].metadata if hasattr(m, "max_length")
    )
    for name in ("interests", "qualifications", "experience", "publications", "achievements")
}


async def _decide(
    db: Db,
    user: User,
    faculty_id: str,
    accept: list[str],
    reject: list[str],
    overrides=None,
    skip_invalid: bool = False,
):
    target = await _faculty(db, user, faculty_id, write=True)
    profile = await _profile(db, target["_id"])
    pending = {p["id"]: p for p in profile.get("pending_imports", [])}
    accept = list(dict.fromkeys(accept))
    reject = [i for i in dict.fromkeys(reject) if i not in accept]
    unknown = [i for i in [*accept, *reject] if i not in pending]
    if unknown:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "That imported item is no longer waiting for review."
        )
    rejected_keys = list(profile.get("rejected_keys", []))
    skipped: list[str] = []
    for item_id in accept:
        entry = pending[item_id]
        try:
            _accept_into(profile, entry, (overrides or {}).get(item_id))
        except HTTPException as exc:
            if not skip_invalid:
                raise
            data = entry.get("data") or {}
            skipped.append(f"{data.get('title') or data.get('tag') or item_id}: {exc.detail}")
            continue
        del pending[item_id]
    for section, limit in SECTION_LIMITS.items():
        if len(profile.get(section, [])) > limit:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"That would put more than {limit} {section} on the profile. Accept fewer.",
            )
    for item_id in reject:
        rejected_keys.append(pending.pop(item_id)["key"])
    changes = {
        "pending_imports": list(pending.values()),
        "rejected_keys": rejected_keys,
        "interests": profile.get("interests", []),
        **{s: profile.get(s, []) for s in SECTIONS},
    }
    saved = await _save(db, target["_id"], changes)
    await record(
        db,
        user,
        "profile.review_imports",
        faculty_id,
        {"accepted": len(accept) - len(skipped), "rejected": len(reject)},
    )
    out = await _out(db, user, target, saved)
    return out.model_copy(update={"skipped_imports": skipped})


@router.post("/{faculty_id}/imports/{item_id}/accept", response_model=ProfileDataOut)
async def accept_import(
    faculty_id: str, item_id: str, db: Db, user: Staff, body: AcceptIn | None = None
) -> ProfileDataOut:
    overrides = {item_id: body.data} if body and body.data else None
    return await _decide(db, user, faculty_id, [item_id], [], overrides)


@router.post("/{faculty_id}/imports/{item_id}/reject", response_model=ProfileDataOut)
async def reject_import(faculty_id: str, item_id: str, db: Db, user: Staff) -> ProfileDataOut:
    return await _decide(db, user, faculty_id, [], [item_id])


@router.post("/{faculty_id}/imports/bulk", response_model=ProfileDataOut)
async def bulk_decide(faculty_id: str, body: BulkDecisionIn, db: Db, user: Staff) -> ProfileDataOut:
    if set(body.accept) & set(body.reject):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "An item can't be both accepted and rejected."
        )
    return await _decide(
        db, user, faculty_id, list(body.accept), list(body.reject), skip_invalid=True
    )
