"""Action Taken Report drafting: department x aspect rows, curriculum rows, actions, re-drafting."""

from app.nlp import atr

CSE = {"_id": "d1", "code": "CSE", "name": "Computer Science and Engineering"}


def aspect(pos, neg, mean, tag):
    return {
        "mentions": pos + neg,
        "polarity": {"positive": pos, "neutral": 0, "negative": neg},
        "likert_mean": mean,
        "agreement": {"rho": None, "n": 0},
        "evidence": {
            "positive": [],
            "neutral": [],
            "negative": [
                {"id": f"{tag}:improve:{i}", "text": f"Too fast {tag} {i}.", "conf": 0.9}
                for i in range(min(neg, 3))
            ],
        },
    }


def teaching(tag, responses=10, pace=(1, 6), clarity=(8, 1)):
    return {
        "form_id": tag,
        "faculty_id": tag,
        "type": "teaching",
        "department_id": "d1",
        "responses": responses,
        "stats": {
            "responses": responses,
            "analysed": responses,
            "aspects": {
                "pace": aspect(*pace, 2.5, tag),
                "clarity": aspect(*clarity, 4.2, tag),
            },
        },
    }


def curriculum(tag, lab=2.4, pos=2.0, neg=6.0, responses=10):
    return {
        "form_id": tag,
        "type": "curriculum",
        "department_id": "d1",
        "responses": responses,
        "stats": {
            "responses": responses,
            "analysed": responses,
            "likert_means": {"lab_adequacy": lab, "syllabus_relevance": 3.8},
            "sentiment": {"positive": pos, "neutral": 1.0, "negative": neg},
            "top_comments": {"negative": [{"id": f"{tag}:comment", "text": "Labs are too few."}]},
        },
    }


def test_teaching_issues_count_courses_not_teachers():
    forms = [teaching("a"), teaching("b"), teaching("c", pace=(5, 1)), teaching("x", responses=2)]
    rows = atr.teaching_issues(CSE, forms, minimum=5)
    assert [r["key"] for r in rows] == ["pace"]
    pace = rows[0]
    assert pace["issue"].startswith("Pace & syllabus coverage was raised as an area to improve")
    assert "in 2 of 3 CSE courses (12 critical comments)" in pace["issue"]  # x is below minimum
    assert pace["evidence_count"] == 12 and len(pace["evidence_ids"]) == 6
    assert "teacher" not in pace["issue"].lower()


def test_curriculum_issues_low_items_and_critical_comments():
    rows = atr.curriculum_issues(CSE, [curriculum("k"), curriculum("l", lab=2.8)], minimum=5)
    assert [r["key"] for r in rows] == ["lab_adequacy", "comments"]
    assert "rated 2.6 out of 5" in rows[0]["issue"]
    assert rows[1]["evidence_ids"] == ["k:comment", "l:comment"]
    assert atr.curriculum_issues(CSE, [curriculum("k", lab=3.5, pos=8, neg=1)], 5) == []


def test_draft_uses_templates_without_an_llm():
    rows = atr.draft([CSE], [teaching("a"), teaching("b"), curriculum("k")], minimum=5)
    assert {(r["kind"], r["key"]) for r in rows} == {
        ("teaching", "pace"),
        ("curriculum", "lab_adequacy"),
        ("curriculum", "comments"),
    }
    pace = next(r for r in rows if r["key"] == "pace")
    assert pace["source"] == "template" and pace["action"].startswith("Check understanding")
    assert pace["responsible"] == "HoD, Computer Science and Engineering"
    lab = next(r for r in rows if r["key"] == "lab_adequacy")
    assert lab["responsible"].startswith("Board of Studies")


def test_llm_actions_are_matched_by_row_id(monkeypatch):
    def fake(system, user, schema):
        assert "Too fast" in user and "CSE" not in system
        return schema.model_validate(
            {
                "rows": [
                    {
                        "row_id": "0",
                        "action": "Share a weekly plan and pause for questions.",
                        "timeline": "Next semester",
                    },
                    {"row_id": "99", "action": "This row does not exist at all.", "timeline": "x"},
                ]
            }
        ), {"engine": "groq:m"}

    monkeypatch.setattr(atr.llm, "complete_json", fake)
    rows = atr.draft([CSE], [teaching("a"), teaching("b"), curriculum("k")], minimum=5)
    assert rows[0]["action"] == "Share a weekly plan and pause for questions."
    assert rows[0]["source"] == "groq:m" and rows[0]["timeline"] == "Next semester"
    assert all(r["source"] == "template" for r in rows[1:])  # no LLM answer: template kept


def test_merge_keeps_edited_and_approved_rows():
    fresh = [
        {"department_id": "d1", "kind": "teaching", "key": k, "issue": f"new {k}"}
        for k in ("pace", "clarity", "assessment", "practical")
    ]
    existing = [
        {"_id": 1, "department_id": "d1", "kind": "teaching", "key": "pace", "status": "draft"},
        {
            "_id": 2,
            "department_id": "d1",
            "kind": "teaching",
            "key": "clarity",
            "status": "draft",
            "edited": True,
        },
        {
            "_id": 3,
            "department_id": "d1",
            "kind": "teaching",
            "key": "assessment",
            "status": "approved",
        },
        {
            "_id": 4,
            "department_id": "d1",
            "kind": "teaching",
            "key": "behaviour",
            "status": "draft",
        },
        {
            "_id": 5,
            "department_id": "d1",
            "kind": "other",
            "key": "manual:x",
            "status": "draft",
            "source": "manual",
        },
        {
            "_id": 6,
            "department_id": "d1",
            "kind": "teaching",
            "key": "knowledge",
            "status": "approved",
        },
    ]
    inserts, replaces, removes, kept = atr.merge(existing, fresh)
    assert [r["key"] for r in inserts] == ["practical"]
    assert [(i, r["key"]) for i, r in replaces] == [(1, "pace")]
    assert removes == [4]  # an untouched draft the data no longer supports
    assert kept == 4  # edited, approved, manual, and the approved row no longer in the data


def test_an_issue_from_one_course_is_not_a_department_row():
    forms = [teaching("a"), teaching("b", pace=(5, 1)), teaching("c", pace=(5, 1))]
    assert atr.teaching_issues(CSE, forms, minimum=5) == []  # 1 of 3 would single out a teacher
    assert atr.teaching_issues(CSE, [teaching("a")], minimum=5) == []  # one course, one teacher
