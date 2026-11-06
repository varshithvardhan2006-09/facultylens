"""Everything the NAAC Criterion 1.4 report says, as one plain dict (SPEC §12).

Both the PDF and the DOCX are rendered from this dict, so they cannot disagree. It is built
only from stored aggregates (which hold moderated, redacted text), course and department
records and the Action Taken rows. It never reads `responses.texts` and never includes a
teacher's name or a per-teacher score: the report is published on the college website.
"""

from typing import Any

from app.config import get_settings
from app.feedback_spec import (
    ASPECT_KEYS,
    ASPECT_LABELS,
    CURRICULUM_ITEMS,
    CURRICULUM_KEYS,
    CURRICULUM_LABELS,
    TEACHING_ASPECTS,
)
from app.nlp import atr, registry
from app.nlp.summarize import choose_aspects
from app.pipeline import analytics
from app.services.forms_data import form_rows
from app.utils import now

SAMPLES_PER_THEME = 2
CURRICULUM_SAMPLES = 3


def _usable(form: dict[str, Any], minimum: int) -> bool:
    return form["responses"] >= minimum and bool((form.get("stats") or {}).get("analysed"))


def _rate(responses: int, eligible: int) -> float | None:
    return round(responses / eligible, 3) if eligible else None


def _strengths(forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aspects praised across a department's courses, with a few redacted sample sentences."""
    found: dict[str, dict[str, Any]] = {}
    for form in forms:
        strengths, _ = choose_aspects(form["stats"], need_evidence=False)
        for s in strengths:
            row = found.setdefault(s["aspect"], {"courses": 0, "mentions": 0, "samples": []})
            row["courses"] += 1
            row["mentions"] += s["positive"]
            evidence = form["stats"]["aspects"][s["aspect"]].get("evidence", {}).get("positive", [])
            row["samples"] += [e["text"] for e in evidence if not e.get("uncertain")]
    return [
        {
            "aspect": key,
            "label": ASPECT_LABELS[key],
            "courses": r["courses"],
            "mentions": r["mentions"],
            "samples": list(dict.fromkeys(r["samples"]))[:SAMPLES_PER_THEME],
        }
        for key, r in sorted(found.items(), key=lambda kv: (-kv[1]["courses"], -kv[1]["mentions"]))
    ][:3]


def _weighted(pairs):
    pairs = [(v, w) for v, w in pairs if v is not None and w > 0]
    total = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / total, 2) if total else None


async def report_data(db, cycle: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    minimum = settings.min_responses_for_display
    forms = await form_rows(db, await db.forms.find({"cycle_id": cycle["_id"]}).to_list())
    dept_ids = list({f["department_id"] for f in forms})
    departments = await db.departments.find({"_id": {"$in": dept_ids}}).sort("name", 1).to_list()
    actions = (
        await db.action_taken.find({"cycle_id": cycle["_id"]})
        .sort([("department_id", 1), ("kind", -1), ("evidence_count", -1)])
        .to_list()
    )

    dept_sections = []
    all_teaching: list[dict[str, Any]] = []
    for dept in departments:
        mine = [f for f in forms if f["department_id"] == dept["_id"]]
        teaching = [f for f in mine if f["type"] == "teaching"]
        curriculum = [f for f in mine if f["type"] == "curriculum"]
        usable_t = [f for f in teaching if _usable(f, minimum)]
        usable_c = [f for f in curriculum if _usable(f, minimum)]
        all_teaching += usable_t

        courses: dict[str, dict[str, Any]] = {}
        for f in mine:
            c = courses.setdefault(
                f["course"]["id"],
                {
                    "code": f["course"]["code"],
                    "name": f["course"]["name"],
                    "section": f["course"]["section"],
                    "teaching_responses": 0,
                    "teaching_eligible": 0,
                    "curriculum_responses": 0,
                    "curriculum_eligible": 0,
                },
            )
            c[f"{f['type']}_responses"] += f["responses"]
            c[f"{f['type']}_eligible"] += f["eligible"]
        course_rows = sorted(courses.values(), key=lambda c: (c["code"], c["section"]))
        for c in course_rows:
            c["teaching_rate"] = _rate(c["teaching_responses"], c["teaching_eligible"])

        combined = analytics.combine([f["stats"] for f in usable_t]) if usable_t else None
        gaps = atr.teaching_issues(dept, mine, minimum)
        curriculum_stats = [f["stats"] for f in usable_c]
        curriculum_sentiment = {
            k: round(sum((s.get("sentiment") or {}).get(k, 0) for s in curriculum_stats), 1)
            for k in ("positive", "neutral", "negative")
        }
        samples = []
        for label in ("negative", "positive"):
            for s in curriculum_stats:
                samples += [c["text"] for c in (s.get("top_comments") or {}).get(label, [])]
        responses = sum(f["responses"] for f in mine)
        eligible = sum(f["eligible"] for f in mine)
        dept_sections.append(
            {
                "code": dept["code"],
                "name": dept["name"],
                "offerings": len(course_rows),
                "teaching_forms": len(teaching),
                "curriculum_forms": len(curriculum),
                "forms_shown": len(usable_t),
                "teaching_responses": sum(f["responses"] for f in teaching),
                "teaching_eligible": sum(f["eligible"] for f in teaching),
                "responses": responses,
                "eligible": eligible,
                "response_rate": _rate(responses, eligible),
                "courses": course_rows,
                "net_score": combined["net_score"] if combined else None,
                "sentiment": combined["sentiment"] if combined else None,
                "aspect_means": {
                    k: (combined["aspects"].get(k) or {}).get("likert_mean") for k in ASPECT_KEYS
                }
                if combined
                else {},
                "strengths": _strengths(usable_t),
                "gaps": [
                    {
                        "aspect": g["key"],
                        "label": g["label"],
                        "issue": g["issue"],
                        "mentions": g["evidence_count"],
                        "samples": list(dict.fromkeys(g["examples"]))[:SAMPLES_PER_THEME],
                    }
                    for g in gaps[:3]
                ],
                "curriculum": {
                    "forms_shown": len(usable_c),
                    "means": {
                        k: _weighted(
                            [
                                ((s.get("likert_means") or {}).get(k), s["responses"])
                                for s in curriculum_stats
                            ]
                        )
                        for k in CURRICULUM_KEYS
                    },
                    "sentiment": curriculum_sentiment,
                    "samples": list(dict.fromkeys(samples))[:CURRICULUM_SAMPLES],
                },
            }
        )

    institution = analytics.combine([f["stats"] for f in all_teaching]) if all_teaching else None
    engines: dict[str, int] = {}
    async for s in db.summaries.find({"cycle_id": cycle["_id"]}, {"engine": 1}):
        key = (
            "an AI model (Groq)"
            if str(s.get("engine", "")).startswith("groq")
            else "built-in templates"
        )
        engines[key] = engines.get(key, 0) + 1
    dept_names = {d["_id"]: d["name"] for d in departments}
    return {
        "institution": settings.institution_name,
        "cycle": {
            "name": cycle["name"],
            "academic_year": cycle.get("academic_year"),
            "term": cycle.get("term"),
            "opens_at": cycle.get("opens_at"),
            "closes_at": cycle.get("closes_at"),
            "status": cycle.get("status"),
        },
        "generated_at": now(),
        "minimum": minimum,
        "totals": {
            "departments": len(departments),
            "offerings": sum(d["offerings"] for d in dept_sections),
            "responses": sum(d["responses"] for d in dept_sections),
            "eligible": sum(d["eligible"] for d in dept_sections),
            "net_score": institution["net_score"] if institution else None,
            "sentiment": institution["sentiment"] if institution else None,
        },
        "departments": dept_sections,
        "questionnaire": {
            "teaching": [(label, question) for _, label, question, _ in TEACHING_ASPECTS],
            "curriculum": [(label, question) for _, label, question in CURRICULUM_ITEMS],
        },
        "models": [{"task": m["description"], "model": m["model_id"]} for m in registry.status()],
        "summary_engines": engines,
        "thresholds": {
            "tox_hide": settings.tox_hide,
            "tox_review": settings.tox_review,
            "sarc_flag": settings.sarc_flag,
        },
        "actions": [
            {
                "department": dept_names.get(a["department_id"], "Institution"),
                "kind": a["kind"],
                "topic": ASPECT_LABELS.get(a["key"])
                or CURRICULUM_LABELS.get(a["key"])
                or a.get("label")
                or a["key"],
                "issue": a["issue"],
                "evidence_count": a.get("evidence_count", 0),
                "action": a["action"],
                "responsible": a["responsible"],
                "timeline": a["timeline"],
                "status": a["status"],
            }
            for a in actions
        ],
    }
