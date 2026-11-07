"""Generated profiles: draft → edit → approve (SPEC §7), and the approved public profile.

The owner or an Admin can generate and edit drafts; only the owner can approve one, which
supersedes the previously approved version. The approved profile is readable by all staff in
the institution, without evidence ids (feedback detail stays on the feedback page).
"""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.auth.deps import Db, User, require_roles
from app.limiter import limiter
from app.nlp import profile_gen
from app.routers.profiles import _faculty, _profile
from app.services.audit import record
from app.utils import conflict, now, oid, to_jsonable

router = APIRouter(prefix="/faculty", tags=["profiles"])
Staff = Annotated[User, Depends(require_roles("admin", "hod", "faculty"))]
GENERATE_LIMIT = "10/minute"
RECENT_PUBLICATIONS = 5


class HighlightIn(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)


class ProfileFieldsIn(BaseModel):
    headline: str = Field(min_length=1, max_length=200)
    bio_short: str = Field(min_length=1, max_length=900)
    bio_long: str = Field(min_length=1, max_length=2200)
    research_areas: list[str] = Field(default_factory=list, max_length=12)
    key_achievements: list[str] = Field(default_factory=list, max_length=10)
    teaching_highlights: list[HighlightIn] = Field(default_factory=list, max_length=6)


def _version_out(doc: dict[str, Any]) -> dict[str, Any]:
    out = to_jsonable(doc)
    out.pop("user_id", None)
    return out


async def _highlights(db: Db, faculty_id) -> list[dict[str, Any]]:
    """Strengths from this person's most recent cycle that has summaries, one per aspect."""
    latest = await db.summaries.find_one({"faculty_id": faculty_id}, sort=[("generated_at", -1)])
    if not latest:
        return []
    out, seen = [], set()
    async for summary in db.summaries.find(
        {"faculty_id": faculty_id, "cycle_id": latest["cycle_id"]}
    ):
        for item in summary.get("strengths", []):
            if item["aspect"] not in seen:
                seen.add(item["aspect"])
                out.append(item)
    return out[:3]


@router.post("/{faculty_id}/profile/generate", status_code=status.HTTP_201_CREATED)
@limiter.limit(GENERATE_LIMIT)
async def generate_profile(request: Request, faculty_id: str, db: Db, user: Staff) -> dict:
    target = await _faculty(db, user, faculty_id, write=True)
    profile = await _profile(db, target["_id"])
    dept = (
        await db.departments.find_one({"_id": target["department_id"]})
        if target.get("department_id")
        else None
    )
    facts = profile_gen.build_facts(target, dept, profile, await _highlights(db, target["_id"]))
    fields, meta = await asyncio.to_thread(profile_gen.generate, facts)
    last = await db.profile_versions.find_one({"user_id": target["_id"]}, sort=[("version", -1)])
    doc = {
        "user_id": target["_id"],
        "version": (last["version"] + 1) if last else 1,
        "status": "draft",
        "fields": {k: v for k, v in fields.items() if k != "sources"},
        "generated": {k: v for k, v in fields.items() if k != "sources"},
        "sources": fields.get("sources", {}),
        "engine": meta["engine"],
        "keywords": meta.get("keywords", []),
        "rejected_claims": meta.get("rejected", []),
        "edited": False,
        "created_by": user["_id"],
        "created_at": now(),
    }
    try:
        doc["_id"] = (await db.profile_versions.insert_one(doc)).inserted_id
    except DuplicateKeyError:
        raise conflict("A newer draft was just created. Reload to see it.") from None
    await record(db, user, "profile.generate", faculty_id, {"version": doc["version"]})
    return _version_out(doc)


@router.get("/{faculty_id}/profile/versions")
async def list_versions(faculty_id: str, db: Db, user: Staff) -> list[dict]:
    target = await _faculty(db, user, faculty_id, write=False)
    rows = await db.profile_versions.find({"user_id": target["_id"]}).sort("version", -1).to_list()
    return [_version_out(r) for r in rows]


async def _draft(db: Db, target: dict[str, Any], version: int) -> dict[str, Any]:
    if not 0 < version < 2**31:  # MongoDB can't even look up a number beyond 64 bits
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That version doesn't exist.")
    doc = await db.profile_versions.find_one({"user_id": target["_id"], "version": version})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    if doc["status"] != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft can be changed.")
    return doc


@router.put("/{faculty_id}/profile/versions/{version}")
async def edit_version(
    faculty_id: str, version: int, body: ProfileFieldsIn, db: Db, user: Staff
) -> dict:
    target = await _faculty(db, user, faculty_id, write=True)
    doc = await _draft(db, target, version)
    fields = body.model_dump()
    await db.profile_versions.update_one(
        {"_id": doc["_id"]},
        {"$set": {"fields": fields, "edited": True, "edited_by": user["_id"], "edited_at": now()}},
    )
    await record(db, user, "profile.edit", faculty_id, {"version": version})
    return _version_out(await db.profile_versions.find_one({"_id": doc["_id"]}))


@router.post("/{faculty_id}/profile/versions/{version}/approve")
async def approve_version(faculty_id: str, version: int, db: Db, user: Staff) -> dict:
    target = await _faculty(db, user, faculty_id, write=True)
    if user["_id"] != target["_id"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the faculty member can approve their own profile."
        )
    doc = await _draft(db, target, version)
    # In this order there is never a moment with no approved profile, and only one remains.
    await db.profile_versions.update_one(
        {"_id": doc["_id"]}, {"$set": {"status": "approved", "approved_at": now()}}
    )
    await db.profile_versions.update_many(
        {"user_id": target["_id"], "status": "approved", "_id": {"$ne": doc["_id"]}},
        {"$set": {"status": "superseded", "superseded_at": now()}},
    )
    await record(db, user, "profile.approve", faculty_id, {"version": version})
    return _version_out(await db.profile_versions.find_one({"_id": doc["_id"]}))


async def public_profile(db: Db, target: dict[str, Any]) -> dict[str, Any]:
    """The approved profile plus the facts the page lists (publications, achievements)."""
    approved = await db.profile_versions.find_one({"user_id": target["_id"], "status": "approved"})
    profile = await _profile(db, target["_id"])
    dept = (
        await db.departments.find_one({"_id": target["department_id"]})
        if target.get("department_id")
        else None
    )
    pubs = sorted(profile.get("publications", []), key=lambda p: p.get("year") or 0, reverse=True)
    fields = dict(approved["fields"]) if approved else None
    if fields:
        fields["teaching_highlights"] = [
            {"text": h["text"]} for h in fields.get("teaching_highlights", [])
        ]
    return {
        "id": str(target["_id"]),
        "name": target["name"],
        "designation": profile.get("designation"),
        "department": {"code": dept["code"], "name": dept["name"]} if dept else None,
        "photo_url": profile.get("photo_url"),
        "status": "approved" if approved else "none",
        "version": approved["version"] if approved else None,
        "approved_at": approved.get("approved_at") if approved else None,
        "fields": fields,
        "publications": [
            {k: p.get(k) for k in ("id", "title", "venue", "year", "tldr", "doi", "url")}
            for p in pubs[:RECENT_PUBLICATIONS]
        ],
        "publication_count": len(pubs),
        "achievements": [
            {k: a.get(k) for k in ("id", "kind", "title", "year")}
            for a in sorted(
                profile.get("achievements", []), key=lambda a: a.get("year") or 0, reverse=True
            )
        ],
    }


@router.get("/{faculty_id}/profile")
async def get_public_profile(faculty_id: str, db: Db, _user: Staff) -> dict:
    target = await db.users.find_one({"_id": oid(faculty_id, "Faculty member")})
    if not target or target["role"] not in ("faculty", "hod"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Faculty member not found")
    return to_jsonable(await public_profile(db, target))
