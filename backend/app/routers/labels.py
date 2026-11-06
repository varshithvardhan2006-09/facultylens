"""Labelling for the evaluation (SPEC §8.2): blind two-annotator labels, adjudication, human
reference summaries and grounding checks.

Who: staff accounts the admin has marked as `annotator` or `adjudicator` (never students).
Annotators label blind: they never see anyone else's label. Faculty and HoD annotators see only
the public dataset; the app's own comments (already redacted and moderated) go to admin
annotators only.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.deps import CurrentUser, Db, User
from app.feedback_spec import ASPECT_KEYS
from app.services import agreement
from app.utils import now, oid, upsert_one

router = APIRouter(prefix="/labels", tags=["evaluation"])

Sentiment = Literal["negative", "neutral", "positive"]


def _require(*modes: str):
    async def dependency(user: CurrentUser) -> User:
        if user.get("annotator") not in modes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only annotators can do this.")
        return user

    return dependency


Annotator = Annotated[User, Depends(_require("annotator"))]
Adjudicator = Annotated[User, Depends(_require("adjudicator"))]
AnyAnnotator = Annotated[User, Depends(_require("annotator", "adjudicator"))]


async def _viewer(user: CurrentUser) -> User:
    if user["role"] != "admin" and not user.get("annotator"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this.")
    return user


Viewer = Annotated[User, Depends(_viewer)]


def _scope(user: User) -> dict[str, Any]:
    """The labelling set this user may see."""
    query: dict[str, Any] = {"set": "label"}
    if user["role"] != "admin":
        query["source"] = "rmp"
    return query


def _item_out(item: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(item["_id"]), "text": item["text"], "source": item["source"]}


class AspectLabel(BaseModel):
    key: str
    polarity: Sentiment

    @field_validator("key")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ASPECT_KEYS:
            raise ValueError(f"Unknown aspect {v}.")
        return v


class _Judgement(BaseModel):
    sentiment: Sentiment | None = None
    aspects: list[AspectLabel] = Field(default_factory=list, max_length=len(ASPECT_KEYS))

    @field_validator("aspects")
    @classmethod
    def _unique(cls, v: list[AspectLabel]) -> list[AspectLabel]:
        if len({a.key for a in v}) != len(v):
            raise ValueError("Each aspect can be marked once.")
        return v


class LabelIn(_Judgement):
    item_id: str
    sarcastic: bool = False
    skip_reason: Literal["not_english", "not_about_teaching", "unclear"] | None = None

    @model_validator(mode="after")
    def _complete(self):
        if not self.skip_reason and not self.sentiment:
            raise ValueError("Choose the overall sentiment, or skip the comment with a reason.")
        return self


class ResolveIn(_Judgement):
    item_id: str
    sentiment: Sentiment


async def _labels(db: Db) -> list[dict[str, Any]]:
    return await db.labels.find({}).to_list(None)


async def _adjudications(db: Db) -> list[dict[str, Any]]:
    return await db.adjudications.find({}).to_list(None)


@router.get("/next")
async def next_item(db: Db, user: Annotator) -> dict[str, Any]:
    """The next comment I haven't labelled. Items that already have two labels are skipped."""
    scope = _scope(user)
    total = await db.eval_items.count_documents(scope)
    mine = {lab["item_id"] async for lab in db.labels.find({"annotator_id": user["_id"]})}
    cursor = await db.labels.aggregate(
        [{"$group": {"_id": "$item_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gte": 2}}}]
    )
    full = await cursor.to_list(None)
    exclude = mine | {f["_id"] for f in full}
    item = await db.eval_items.find_one(
        {**scope, "_id": {"$nin": list(exclude)}}, sort=[("order", 1)]
    )
    return {
        "item": _item_out(item) if item else None,
        "progress": {"mine": len(mine), "total": total},
    }


@router.post("")
async def save_label(body: LabelIn, db: Db, user: Annotator) -> dict[str, Any]:
    item = await db.eval_items.find_one({**_scope(user), "_id": oid(body.item_id, "Item")})
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    doc = {
        "sentiment": body.sentiment,
        "aspects": [a.model_dump() for a in body.aspects],
        "sarcastic": body.sarcastic,
        "skipped": bool(body.skip_reason),
        "skip_reason": body.skip_reason,
        "at": now(),
    }
    await upsert_one(
        db.labels, {"item_id": item["_id"], "annotator_id": user["_id"]}, {"$set": doc}
    )
    return {"saved": True}


@router.get("/progress")
async def progress(db: Db, user: Viewer) -> dict[str, Any]:
    labels = await _labels(db)
    adjudications = await _adjudications(db)
    counts: dict[Any, dict[str, int]] = {}
    for lab in labels:
        entry = counts.setdefault(lab["annotator_id"], {"labelled": 0, "skipped": 0})
        entry["skipped" if lab.get("skipped") else "labelled"] += 1
    people = await db.users.find(
        {"annotator": {"$in": ["annotator", "adjudicator"]}}, {"name": 1, "annotator": 1}
    ).to_list(None)
    groups = await db.eval_groups.find({}, {"references": 1, "system": 1, "grounding": 1}).to_list(
        None
    )
    return {
        "items": await db.eval_items.count_documents({"set": "label"}),
        "annotators": [
            {
                "id": str(p["_id"]),
                "name": p["name"],
                "mode": p["annotator"],
                **counts.get(p["_id"], {"labelled": 0, "skipped": 0}),
            }
            for p in people
        ],
        "agreement": agreement.agreement(labels),
        "gold": len(agreement.gold(labels, adjudications)),
        "disagreements": len(agreement.disagreements(labels, adjudications)),
        "groups": {
            "total": len(groups),
            "with_reference": sum(bool(g.get("references")) for g in groups),
            "with_system": sum(bool(g.get("system")) for g in groups),
            "grounding_checked": sum(bool(g.get("grounding")) for g in groups),
        },
    }


@router.get("/disagreements")
async def list_disagreements(db: Db, user: Adjudicator) -> dict[str, Any]:
    """Items the pair labelled differently and nobody has settled yet (first 20)."""
    every = agreement.disagreements(await _labels(db), await _adjudications(db))
    items = {
        i["_id"]: i
        async for i in db.eval_items.find({**_scope(user), "_id": {"$in": [p[0] for p in every]}})
    }

    def view(label: dict[str, Any]) -> dict[str, Any]:
        return {
            "sentiment": label["sentiment"],
            "aspects": label.get("aspects") or [],
            "sarcastic": label.get("sarcastic", False),
        }

    pending = [(item, a, b) for item, a, b in every if item in items]
    return {
        "total": len(pending),
        "items": [
            {**_item_out(items[item]), "a": view(a), "b": view(b)} for item, a, b in pending[:20]
        ],
    }


@router.post("/resolve")
async def resolve(body: ResolveIn, db: Db, user: Adjudicator) -> dict[str, Any]:
    item = await db.eval_items.find_one({**_scope(user), "_id": oid(body.item_id, "Item")})
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    await db.adjudications.update_one(
        {"item_id": item["_id"]},
        {
            "$set": {
                "sentiment": body.sentiment,
                "aspects": [a.model_dump() for a in body.aspects],
                "by": user["_id"],
                "at": now(),
            }
        },
        upsert=True,
    )
    return {"saved": True}


# ---- Reference summaries (SPEC §8.6) ----


class ReferenceIn(BaseModel):
    strengths: list[str] = Field(min_length=1, max_length=4)
    improvements: list[str] = Field(min_length=1, max_length=4)

    @field_validator("strengths", "improvements")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        v = [s.strip() for s in v if s.strip()]
        if not v:
            raise ValueError("Write at least one point.")
        if any(len(s) > 300 for s in v):
            raise ValueError("Keep each point under 300 characters.")
        return v


@router.get("/groups/next")
async def next_group(db: Db, user: AnyAnnotator) -> dict[str, Any]:
    """A teacher's comments (public dataset) I haven't written a reference summary for."""
    total = await db.eval_groups.count_documents({})
    query = {"references.annotator_id": {"$ne": user["_id"]}}
    done = total - await db.eval_groups.count_documents(query)
    group = await db.eval_groups.find_one(query, sort=[("order", 1)])
    if not group:
        return {"group": None, "progress": {"mine": done, "total": total}}
    texts = await db.eval_items.find({"_id": {"$in": group["item_ids"]}}, {"text": 1}).to_list(None)
    return {
        "group": {"id": str(group["_id"]), "comments": [t["text"] for t in texts]},
        "progress": {"mine": done, "total": total},
    }


@router.post("/groups/{group_id}/reference")
async def save_reference(
    group_id: str, body: ReferenceIn, db: Db, user: AnyAnnotator
) -> dict[str, Any]:
    group = await db.eval_groups.find_one({"_id": oid(group_id, "Group")})
    if not group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    await db.eval_groups.update_one(
        {"_id": group["_id"]}, {"$pull": {"references": {"annotator_id": user["_id"]}}}
    )
    await db.eval_groups.update_one(
        {"_id": group["_id"]},
        {"$push": {"references": {"annotator_id": user["_id"], **body.model_dump(), "at": now()}}},
    )
    return {"saved": True}


# ---- Grounding checks: is each generated bullet supported by its cited evidence? ----


class Check(BaseModel):
    index: int = Field(ge=0)
    supported: bool


class GroundingIn(BaseModel):
    group_id: str
    checks: list[Check] = Field(min_length=1, max_length=20)


@router.get("/grounding/next")
async def next_grounding(db: Db, user: AnyAnnotator) -> dict[str, Any]:
    query = {"system": {"$exists": True}, "grounding.annotator_id": {"$ne": user["_id"]}}
    total = await db.eval_groups.count_documents({"system": {"$exists": True}})
    left = await db.eval_groups.count_documents(query)
    group = await db.eval_groups.find_one(query, sort=[("order", 1)])
    return {
        "group": {"id": str(group["_id"]), "bullets": group["system"]["bullets"]}
        if group
        else None,
        "progress": {"mine": total - left, "total": total},
    }


@router.post("/grounding")
async def save_grounding(body: GroundingIn, db: Db, user: AnyAnnotator) -> dict[str, Any]:
    group = await db.eval_groups.find_one({"_id": oid(body.group_id, "Group")})
    if not group or not group.get("system"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    count = len(group["system"]["bullets"])
    if any(c.index >= count for c in body.checks):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown bullet.")
    await db.eval_groups.update_one(
        {"_id": group["_id"]}, {"$pull": {"grounding": {"annotator_id": user["_id"]}}}
    )
    await db.eval_groups.update_one(
        {"_id": group["_id"]},
        {
            "$push": {
                "grounding": {
                    "annotator_id": user["_id"],
                    "checks": [c.model_dump() for c in body.checks],
                    "at": now(),
                }
            }
        },
    )
    return {"saved": True}
