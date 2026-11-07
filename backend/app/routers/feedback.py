"""What faculty, their HoD and the admin may see about a faculty member's feedback.

Phase 3: response counts, and rating averages once a form has MIN_RESPONSES_FOR_DISPLAY
responses. Comment text stays hidden until Phase 4 has moderated and redacted it.
"""

import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.deps import Db, User, require_roles
from app.config import get_settings
from app.nlp import registry
from app.pipeline.aggregate import effective_field
from app.schemas.feedback import FormStats
from app.services.access import faculty_or_404, hod_forms, sees_feedback
from app.services.forms_data import course_brief, cycle_brief, lookups, response_counts
from app.utils import oid

router = APIRouter(prefix="/feedback", tags=["feedback"])
Staff = Annotated[User, Depends(require_roles("admin", "hod", "faculty"))]


async def _visible_comments(db, form_id) -> list[dict] | None:
    """Moderated, redacted answers for one form; None when nothing is analysed yet.

    Only text that passed moderation (or that an admin approved or edited) is returned, and it
    is the redacted text: names, phone numbers, roll numbers and links are already replaced.
    """
    response_ids = [r["_id"] async for r in db.responses.find({"form_id": form_id}, {"_id": 1})]
    analyses = await db.analyses.find(
        {"response_id": {"$in": response_ids}, "model_version": registry.model_version()},
        {"fields": 1},
    ).to_list()
    if not analyses:
        return None
    comments = []
    for analysis in analyses:
        for field in analysis["fields"]:
            shown, text = effective_field(field)
            if not shown:
                continue
            comments.append(
                {
                    "field": field["field"],
                    "text": text,
                    "sentiment": field["sentiment"]["label"],
                    "possibly_sarcastic": bool(field.get("sentiment_uncertain")),
                    "aspects": sorted(
                        {
                            (a["key"], a.get("polarity", "neutral"))
                            for s in field["sentences"]
                            for a in s.get("aspects", [])
                        }
                    ),
                }
            )
    # Opaque ids in random order: an analysis id would tie one student's answers together.
    random.shuffle(comments)
    return [{"id": f"c{i}", **c} for i, c in enumerate(comments)]


@router.get("/faculty/{faculty_id}", response_model=list[FormStats])
async def faculty_feedback(
    faculty_id: str,
    db: Db,
    user: Staff,
    cycle: Annotated[str | None, Query()] = None,
    course: Annotated[str | None, Query()] = None,
) -> list[FormStats]:
    target = await faculty_or_404(db, faculty_id)
    if not await sees_feedback(db, user, target):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't see this feedback.")

    query = {"faculty_id": target["_id"], "type": "teaching"}
    if cycle:
        query["cycle_id"] = oid(cycle, "Cycle")
    if course:
        query["course_id"] = oid(course, "Course")
    forms = await db.forms.find(query).to_list()
    scope = await hod_forms(db, user, target)
    if scope:
        forms = [f for f in forms if f["course_id"] in scope["course_id"]["$in"]]
    cycles, courses, _ = await lookups(db, forms)
    counts = await response_counts(db, [f["_id"] for f in forms])
    minimum = get_settings().min_responses_for_display

    out = []
    for form in forms:
        n = counts.get(form["_id"], 0)
        visible = n >= minimum
        means = None
        if visible:
            pipeline = [
                {"$match": {"form_id": form["_id"]}},
                {
                    "$group": {
                        "_id": None,
                        **{
                            k["key"]: {"$avg": f"$likert.{k['key']}"}
                            for k in form["questions"]
                            if k["kind"] == "likert"
                        },
                    }
                },
            ]
            rows = [r async for r in await db.responses.aggregate(pipeline)]
            if rows:
                means = {k: round(v, 2) for k, v in rows[0].items() if k != "_id" and v is not None}
        comments: list[dict] = []
        comments_status = "hidden_below_minimum"
        if visible:
            comments = await _visible_comments(db, form["_id"])
            comments_status = "available" if comments is not None else "awaiting_analysis"
        course_doc = courses[form["course_id"]]
        out.append(
            FormStats(
                form_id=str(form["_id"]),
                cycle=cycle_brief(cycles[form["cycle_id"]]),
                course=course_brief(course_doc),
                responses=n,
                eligible=len(course_doc.get("student_ids", [])),
                min_required=minimum,
                visible=visible,
                likert_means=means,
                comments=comments or [],
                comments_status=comments_status,
            )
        )
    out.sort(key=lambda s: (s.cycle.closes_at, s.course.code, s.course.section), reverse=True)
    return out
