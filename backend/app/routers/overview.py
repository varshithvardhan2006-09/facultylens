"""The unified faculty page in one call, and the evidence behind its strengths and improvements.

Everyone on staff sees the approved profile. The feedback half (numbers, summary, evidence) is
for the faculty member, their own department's HoD and IQAC admins only, and only for forms
with at least MIN_RESPONSES_FOR_DISPLAY responses. Evidence is always moderated, redacted text.
"""

from typing import Annotated, Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.deps import Db, User, require_roles
from app.config import get_settings
from app.feedback_spec import ASPECT_KEYS, ASPECT_LABELS
from app.nlp import registry
from app.pipeline.aggregate import effective_field
from app.routers.profile_versions import public_profile
from app.services.forms_data import course_brief, cycle_brief, lookups, response_counts
from app.utils import oid, to_jsonable

router = APIRouter(prefix="/faculty", tags=["overview"])
Staff = Annotated[User, Depends(require_roles("admin", "hod", "faculty"))]
MAX_EVIDENCE_IDS = 40


async def _target(db: Db, faculty_id: str) -> dict[str, Any]:
    target = await db.users.find_one({"_id": oid(faculty_id, "Faculty member")})
    if not target or target["role"] not in ("faculty", "hod"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Faculty member not found")
    return target


def _sees_feedback(user: User, target: dict[str, Any]) -> bool:
    return (
        user["role"] == "admin"
        or user["_id"] == target["_id"]
        or (
            user["role"] == "hod"
            and bool(target.get("department_id"))
            and target.get("department_id") == user.get("department_id")
        )
    )


def agreement_label(rho: float | None, n: int) -> str:
    """Plain words for the Likert–text agreement badge."""
    if rho is None or n < 5:
        return "too_few"
    if rho >= 0.3:
        return "agrees"
    if rho <= -0.1:
        return "disagrees"
    return "mixed"


def _insights(stats: dict[str, Any]) -> dict[str, Any]:
    """The aggregate without raw evidence text (the drawer and the wall fetch that by id)."""
    aspects = {}
    for key in ASPECT_KEYS:
        a = (stats.get("aspects") or {}).get(key)
        if not a:
            continue
        agreement = a.get("agreement") or {}
        aspects[key] = {
            "label": ASPECT_LABELS[key],
            "mentions": a["mentions"],
            "polarity": a["polarity"],
            "likert_mean": a.get("likert_mean"),
            "agreement": {
                "rho": agreement.get("rho"),
                "n": agreement.get("n", 0),
                "label": agreement_label(agreement.get("rho"), agreement.get("n", 0)),
            },
            # Ids only, best first per polarity; the page reads the text from /evidence.
            "note_ids": {
                polarity: [e["id"] for e in items]
                for polarity, items in (a.get("evidence") or {}).items()
            },
        }
    return {
        "analysed": stats.get("analysed", 0),
        "answers": stats.get("answers", 0),
        "sentiment": stats.get("sentiment"),
        "net_score": stats.get("net_score"),
        "likert_means": stats.get("likert_means"),
        "aspects": aspects,
        "emotion_mix": stats.get("emotion_mix"),
        "sarcasm_rate": stats.get("sarcasm_rate"),
        "hidden_comments": stats.get("hidden_comments", 0),
        "in_review": stats.get("in_review", 0),
    }


async def _sarcastic_ids(db: Db, form_id: ObjectId) -> list[str]:
    ids = [r["_id"] async for r in db.responses.find({"form_id": form_id}, {"_id": 1})]
    out = []
    async for a in db.analyses.find(
        {
            "response_id": {"$in": ids},
            "model_version": registry.model_version(),
            "fields.sentiment_uncertain": True,
        },
        {"fields": 1},
    ):
        for f in a["fields"]:
            if f.get("sentiment_uncertain") and effective_field(f)[0]:
                out.append(f"{a['_id']}:{f['field']}")
    return out


@router.get("/{faculty_id}/overview")
async def overview(
    faculty_id: str,
    db: Db,
    user: Staff,
    cycle: Annotated[str | None, Query()] = None,
    course: Annotated[str | None, Query()] = None,
) -> dict:
    target = await _target(db, faculty_id)
    out: dict[str, Any] = {
        "profile": await public_profile(db, target),
        "feedback_access": _sees_feedback(user, target),
        "is_owner": user["_id"] == target["_id"],
    }
    if not out["feedback_access"]:
        return to_jsonable(out)

    forms = await db.forms.find({"faculty_id": target["_id"], "type": "teaching"}).to_list()
    cycles, courses, _ = await lookups(db, forms)
    counts = await response_counts(db, [f["_id"] for f in forms])
    by_cycle: dict[ObjectId, list[dict]] = {}
    for f in forms:
        by_cycle.setdefault(f["cycle_id"], []).append(f)
    ordered = sorted(cycles.values(), key=lambda c: c["opens_at"], reverse=True)
    out["cycles"] = [
        {
            **cycle_brief(c),
            "offerings": [
                {"form_id": str(f["_id"]), **course_brief(courses[f["course_id"]])}
                for f in sorted(
                    by_cycle[c["_id"]],
                    key=lambda f: (
                        courses[f["course_id"]]["code"],
                        courses[f["course_id"]]["section"],
                    ),
                )
            ],
        }
        for c in ordered
    ]
    if not forms:
        out["selected"] = None
        return to_jsonable(out)

    cycle_id = oid(cycle, "Cycle") if cycle else ordered[0]["_id"]
    in_cycle = by_cycle.get(cycle_id)
    if not in_cycle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No teaching forms in that cycle")
    if course:
        course_id = oid(course, "Course")
        form = next((f for f in in_cycle if f["course_id"] == course_id), None)
        if not form:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not taught in that cycle")
    else:
        form = max(in_cycle, key=lambda f: counts.get(f["_id"], 0))

    minimum = get_settings().min_responses_for_display
    n = counts.get(form["_id"], 0)
    course_doc = courses[form["course_id"]]
    selected: dict[str, Any] = {
        "form_id": str(form["_id"]),
        "cycle": cycle_brief(cycles[form["cycle_id"]]),
        "course": course_brief(course_doc),
        "responses": n,
        "eligible": len(course_doc.get("student_ids", [])),
        "min_required": minimum,
        "status": "below_minimum",
        "insights": None,
        "summary": None,
        "sarcastic_ids": [],
    }
    if n >= minimum:
        aggregate = await db.aggregates.find_one(
            {"form_id": form["_id"], "model_version": registry.model_version()}
        )
        stats = (aggregate or {}).get("stats") or {}
        if not stats.get("analysed"):
            selected["status"] = "awaiting_analysis"
        else:
            selected["status"] = "available"
            selected["insights"] = _insights(stats)
            summary = await db.summaries.find_one({"form_id": form["_id"]})
            if summary:
                selected["summary"] = {
                    k: summary.get(k)
                    for k in (
                        "strengths",
                        "improvements",
                        "overall_summary",
                        "digest",
                        "engine",
                        "generated_at",
                    )
                }
            selected["sarcastic_ids"] = await _sarcastic_ids(db, form["_id"])
    out["selected"] = selected
    return to_jsonable(out)


def _parse(raw: str) -> tuple[ObjectId, str, int | None] | None:
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        analysis_id = ObjectId(parts[0])
        index = int(parts[2]) if len(parts) == 3 else None
    except (InvalidId, ValueError):
        return None
    return analysis_id, parts[1], index


@router.get("/{faculty_id}/evidence")
async def evidence(
    faculty_id: str, db: Db, user: Staff, ids: Annotated[str, Query(max_length=2000)]
) -> list[dict]:
    """Redacted answers for evidence ids, with the supporting sentence's offsets to highlight.

    Ids that are malformed, belong to another teacher, sit below the minimum responses or point
    at hidden text are left out rather than reported, so they reveal nothing.
    """
    target = await _target(db, faculty_id)
    if not _sees_feedback(user, target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't see this feedback.")
    wanted = [p for p in (_parse(i) for i in ids.split(",")[:MAX_EVIDENCE_IDS]) if p]
    if not wanted:
        return []
    analyses = {
        a["_id"]: a
        async for a in db.analyses.find(
            {
                "_id": {"$in": list({w[0] for w in wanted})},
                "model_version": registry.model_version(),
            }
        )
    }
    form_ids = list({a["form_id"] for a in analyses.values()})
    own = {
        f["_id"]
        async for f in db.forms.find(
            {"_id": {"$in": form_ids}, "faculty_id": target["_id"], "type": "teaching"},
            {"_id": 1},
        )
    }
    counts = await response_counts(db, list(own))
    minimum = get_settings().min_responses_for_display
    out = []
    for analysis_id, field_name, index in wanted:
        analysis = analyses.get(analysis_id)
        if not analysis or analysis["form_id"] not in own:
            continue
        if counts.get(analysis["form_id"], 0) < minimum:
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
                "sentiment": sentence["sentiment"] if sentence else field["sentiment"]["label"],
                "aspects": [
                    {"key": a["key"], "polarity": a.get("polarity")}
                    for a in (sentence or {}).get("aspects", [])
                ],
                "possibly_sarcastic": bool(field.get("sentiment_uncertain")),
                "edited_by_admin": edited,
            }
        )
    return out
