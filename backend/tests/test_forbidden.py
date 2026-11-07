"""The SPEC "done when" check for Phase 1: every endpoint against every role.

Anonymous -> 401. A role outside the allowed set -> 403. An allowed role is never 401/403."""

from datetime import timedelta

import pytest

from app.feedback_spec import questions
from app.pipeline import jobs
from app.services import orcid as orcid_service
from app.services import semantic_scholar as s2_service
from app.utils import now

ROLES = ["anon", "admin", "hod", "faculty", "student"]
ANY = {"admin", "hod", "faculty", "student"}
OWNER = {"admin", "faculty"}
STAFF = {"admin", "hod", "faculty"}
CYCLE = {
    "name": "2026-27 Even Sem",
    "academic_year": "2026-27",
    "term": "even",
    "opens_at": "2027-01-01T00:00:00Z",
    "closes_at": "2027-02-01T00:00:00Z",
}  # the profile owner (world faculty) and Admin

PROFILE_FIELDS = {"headline": "H", "bio_short": "S", "bio_long": "L"}
NO_ID = "000000000000000000000000"

# (method, path, allowed roles, json body). {course} / {user} are filled from the fixture.
ENDPOINTS = [
    ("GET", "/api/auth/me", ANY, None),
    ("GET", "/api/users", {"admin", "hod"}, None),
    ("POST", "/api/users", {"admin"}, {"name": "New Faculty", "role": "faculty"}),
    (
        "POST",
        "/api/users/bulk?dry_run=true",
        {"admin"},
        {"users": [{"name": "X", "role": "admin"}]},
    ),
    ("PATCH", "/api/users/{user}", {"admin"}, {"name": "Renamed Person"}),
    ("DELETE", "/api/users/{user}", {"admin"}, None),
    ("POST", "/api/users/{user}/reset-password", {"admin"}, None),
    ("GET", "/api/departments", ANY, None),
    ("POST", "/api/departments", {"admin"}, {"name": "Mechanical", "code": "MECH"}),
    ("PATCH", "/api/departments/{dept}", {"admin"}, {"name": "Computer Science and Engg"}),
    ("GET", "/api/courses", ANY, None),
    (
        "POST",
        "/api/courses",
        {"admin"},
        {
            "code": "CS502",
            "name": "Networks",
            "department_id": "{dept}",
            "academic_year": "2026-27",
            "semester": 5,
            "section": "B",
        },
    ),
    ("PATCH", "/api/courses/{course}", {"admin"}, {"name": "Compiler Design Lab"}),
    ("POST", "/api/courses/{course}/enrol", {"admin"}, {"add_roll_numbers": []}),
    ("GET", "/api/health/models", {"admin"}, None),
    # Profiles: {user} is the CSE faculty member; the world's HoD is in the same department.
    ("GET", "/api/faculty/{user}/profile-data", {"admin", "hod", "faculty"}, None),
    ("PUT", "/api/faculty/{user}/profile-data", OWNER, {"designation": "Professor"}),
    ("POST", "/api/faculty/{user}/import/orcid", OWNER, {"orcid": "0000-0002-1825-0097"}),
    ("GET", "/api/faculty/{user}/semantic-scholar/search?q=Rao", OWNER, None),
    ("POST", "/api/faculty/{user}/import/semantic-scholar", OWNER, {"author": "42"}),
    ("POST", "/api/faculty/{user}/imports/nope/accept", OWNER, None),
    ("POST", "/api/faculty/{user}/imports/nope/reject", OWNER, None),
    ("POST", "/api/faculty/{user}/imports/bulk", OWNER, {"accept": [], "reject": []}),
    # Generated profiles: the owner or admin drafts; only the owner approves; staff read it.
    ("POST", "/api/faculty/{user}/profile/generate", OWNER, None),
    ("GET", "/api/faculty/{user}/profile/versions", {"admin", "hod", "faculty"}, None),
    ("PUT", "/api/faculty/{user}/profile/versions/1", OWNER, PROFILE_FIELDS),
    ("POST", "/api/faculty/{user}/profile/versions/1/approve", {"faculty"}, None),
    ("GET", "/api/faculty/{user}/profile", {"admin", "hod", "faculty"}, None),
    # Unified page: any staff member gets the profile; feedback evidence is owner, HoD, admin.
    ("GET", "/api/faculty/{user}/overview", {"admin", "hod", "faculty"}, None),
    ("GET", "/api/faculty/{user}/evidence?ids=x", {"admin", "hod", "faculty"}, None),
    # Analytics: department views for its HoD and admin; a teacher's for them, HoD, admin.
    ("GET", "/api/analytics/faculty/{user}", {"admin", "hod", "faculty"}, None),
    ("GET", "/api/analytics/department/{dept}", {"admin", "hod"}, None),
    ("GET", "/api/analytics/bias?department={dept}", {"admin", "hod"}, None),
    ("GET", "/api/analytics/sarcasm?department={dept}", {"admin", "hod"}, None),
    ("GET", "/api/analytics/sarcasm?faculty={user}", {"admin", "hod", "faculty"}, None),
    # Feedback report: admin drafts and exports; the department's HoD reads, edits, approves.
    ("POST", "/api/reports/feedback/{cycle}/draft", {"admin"}, None),
    ("GET", "/api/reports/feedback/{cycle}/actions", {"admin", "hod"}, None),
    ("GET", "/api/reports/feedback/{cycle}/status", {"admin", "hod"}, None),
    (
        "POST",
        "/api/reports/feedback/{cycle}/actions",
        {"admin", "hod"},
        {
            "department_id": "{dept}",
            "label": "Library",
            "issue": "Library closes early.",
            "action": "Extend the hours.",
            "responsible": "Librarian",
        },
    ),
    (
        "PUT",
        f"/api/reports/feedback/{{cycle}}/actions/{NO_ID}",
        {"admin", "hod"},
        {"status": "approved"},
    ),
    ("DELETE", f"/api/reports/feedback/{{cycle}}/actions/{NO_ID}", {"admin"}, None),
    ("GET", f"/api/reports/feedback/{{cycle}}/actions/{NO_ID}/evidence", {"admin", "hod"}, None),
    ("GET", "/api/reports/feedback/{cycle}.pdf?draft=true", {"admin"}, None),
    ("GET", "/api/reports/feedback/{cycle}.docx?draft=true", {"admin"}, None),
    # Feedback collection: {cycle} is open with a teaching form {form} for the CSE offering.
    ("GET", "/api/cycles", STAFF, None),
    ("POST", "/api/cycles", {"admin"}, CYCLE),
    ("GET", "/api/cycles/{cycle}", STAFF, None),
    ("GET", "/api/cycles/{cycle}/preview", {"admin"}, None),
    ("POST", "/api/cycles/{cycle}/publish", {"admin"}, None),
    ("POST", "/api/cycles/{cycle}/close", {"admin"}, None),
    ("GET", "/api/cycles/{cycle}/forms", {"admin", "hod"}, None),
    ("GET", "/api/forms/my", {"student"}, None),
    ("GET", "/api/forms/{form}", ANY, None),
    ("POST", "/api/forms/{form}/responses", {"student"}, {"likert": {}, "texts": {}}),
    ("GET", "/api/feedback/faculty/{user}", STAFF, None),
    # Analysis and moderation: admin only.
    ("GET", "/api/analysis/summary?cycle={cycle}", {"admin"}, None),
    ("POST", "/api/analysis/run?cycle={cycle}", {"admin"}, None),
    ("POST", "/api/analysis/summaries?cycle={cycle}", {"admin"}, None),
    ("GET", "/api/analysis/status/000000000000000000000000", {"admin"}, None),
    ("GET", "/api/analysis/jobs", {"admin"}, None),
    ("GET", "/api/moderation/queue", {"admin"}, None),
    (
        "POST",
        "/api/moderation/000000000000000000000000/decision",
        {"admin"},
        {"action": "approve"},
    ),
    # Evaluation. Labelling needs the annotator flag, which no role has by default.
    ("GET", "/api/labels/next", set(), None),
    ("POST", "/api/labels", set(), {"item_id": NO_ID, "sentiment": "positive"}),
    ("GET", "/api/labels/progress", {"admin"}, None),
    ("GET", "/api/labels/disagreements", set(), None),
    ("POST", "/api/labels/resolve", set(), {"item_id": NO_ID, "sentiment": "neutral"}),
    ("GET", "/api/labels/groups/next", set(), None),
    (
        "POST",
        f"/api/labels/groups/{NO_ID}/reference",
        set(),
        {"strengths": ["a"], "improvements": ["b"]},
    ),
    ("GET", "/api/labels/grounding/next", set(), None),
    (
        "POST",
        "/api/labels/grounding",
        set(),
        {"group_id": NO_ID, "checks": [{"index": 0, "supported": True}]},
    ),
    ("GET", "/api/evaluation/results", {"admin"}, None),
    ("GET", "/api/survey/mine", {"hod", "faculty"}, None),
    (
        "POST",
        "/api/survey",
        {"hod", "faculty"},
        {"answers": {"usefulness": 4, "accuracy": 4, "fairness": 3, "actionability": 5}},
    ),
]

CASES = [
    pytest.param(method, path, allowed, body, role, id=f"{role}-{method}-{path}")
    for method, path, allowed, body in ENDPOINTS
    for role in ROLES
]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    async def nothing(*_args):
        return {"publication": [], "experience": [], "qualification": [], "interest": []}

    async def no_papers(*_args):
        return []

    monkeypatch.setattr(orcid_service, "fetch_orcid", nothing)
    monkeypatch.setattr(s2_service, "fetch_papers", no_papers)
    monkeypatch.setattr(s2_service, "search_authors", no_papers)
    monkeypatch.setattr(jobs, "enqueue", lambda job_id: None)  # no real analysis worker


def _fill(value, ids):
    if isinstance(value, str):
        for key, v in ids.items():
            value = value.replace("{" + key + "}", v)
        return value
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


@pytest.mark.parametrize(("method", "path", "allowed", "body", "role"), CASES)
async def test_role_matrix(client, world, method, path, allowed, body, role):
    db = world["db"]
    cycle = await db.feedback_cycles.insert_one(
        {
            "name": "2026-27 Odd Sem",
            "academic_year": "2026-27",
            "term": "odd",
            "opens_at": now() - timedelta(days=1),
            "closes_at": now() + timedelta(days=9),
            "status": "open",
        }
    )
    form = await db.forms.insert_one(
        {
            "cycle_id": cycle.inserted_id,
            "course_id": world["course_id"],
            "faculty_id": world["faculty"]["_id"],
            "type": "teaching",
            "questions": questions("teaching"),
        }
    )
    ids = {
        "course": str(world["course_id"]),
        "user": str(world["faculty"]["_id"]),
        "dept": str(world["cse"]),
        "cycle": str(cycle.inserted_id),
        "form": str(form.inserted_id),
    }
    r = await client.request(
        method, _fill(path, ids), json=_fill(body, ids), headers=world["headers"][role]
    )
    if role in allowed:
        assert r.status_code not in (401, 403), r.text
    elif role == "anon":
        assert r.status_code == 401, r.text
    else:
        assert r.status_code == 403, r.text
