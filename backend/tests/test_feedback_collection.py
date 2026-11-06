from datetime import timedelta

from app.config import get_settings
from app.feedback_spec import ASPECT_KEYS, CURRICULUM_KEYS
from app.services.anonymity import student_form_hash
from app.utils import now
from tests.conftest import ROLL_NUMBERS, login, make_user


def cycle_body(term="odd", opens=-1, closes=10, name="2026-27 Odd Sem"):
    return {
        "name": name,
        "academic_year": "2026-27",
        "term": term,
        "opens_at": (now() + timedelta(days=opens)).isoformat(),
        "closes_at": (now() + timedelta(days=closes)).isoformat(),
    }


TEACHING = {
    "likert": {k: 4 for k in ASPECT_KEYS},
    "texts": {"liked": "Clear  explanations.", "improve": ""},
}
CURRICULUM = {"likert": {k: 3 for k in CURRICULUM_KEYS}, "texts": {"comment": "More lab hours."}}


async def open_cycle(client, world, **kw):
    h = world["headers"]["admin"]
    cycle = (await client.post("/api/cycles", headers=h, json=cycle_body(**kw))).json()
    r = await client.post(f"/api/cycles/{cycle['id']}/publish", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def student_forms(client, world):
    return (await client.get("/api/forms/my", headers=world["headers"]["student"])).json()


async def test_create_preview_publish_close(client, world):
    h = world["headers"]["admin"]
    db = world["db"]
    # an even-semester offering and a teacher-less odd one, to check parity and skipping
    await db.courses.insert_many(
        [
            {
                "code": "CS402",
                "name": "OS",
                "department_id": world["cse"],
                "academic_year": "2026-27",
                "semester": 4,
                "section": "A",
                "faculty_ids": [world["faculty"]["_id"]],
                "student_ids": [],
            },
            {
                "code": "CS503",
                "name": "AI",
                "department_id": world["cse"],
                "academic_year": "2026-27",
                "semester": 5,
                "section": "B",
                "faculty_ids": [],
                "student_ids": [],
            },
        ]
    )
    bad = await client.post("/api/cycles", headers=h, json=cycle_body(opens=5, closes=1))
    assert bad.status_code == 422
    cycle = (await client.post("/api/cycles", headers=h, json=cycle_body())).json()
    assert cycle["status"] == "draft" and cycle["counts"]["teaching_forms"] == 0

    preview = (await client.get(f"/api/cycles/{cycle['id']}/preview", headers=h)).json()
    assert preview == {
        "offerings": 2,
        "teaching_forms": 1,
        "curriculum_forms": 1,
        "already_created": 0,
        "without_teacher": ["CS503 section B"],
    }
    published = (await client.post(f"/api/cycles/{cycle['id']}/publish", headers=h)).json()
    assert published["status"] == "open"
    assert (
        published["counts"]["teaching_forms"] == 1 and published["counts"]["curriculum_forms"] == 1
    )
    assert published["counts"]["eligible"] == 2  # one student x two forms

    again = (await client.post(f"/api/cycles/{cycle['id']}/publish", headers=h)).json()
    assert again["counts"]["teaching_forms"] == 1  # idempotent
    forms = (await client.get(f"/api/cycles/{cycle['id']}/forms", headers=h)).json()
    assert {f["type"] for f in forms} == {"teaching", "curriculum"}
    assert all(f["responses"] == 0 and f["eligible"] == 1 for f in forms)

    closed = (await client.post(f"/api/cycles/{cycle['id']}/close", headers=h)).json()
    assert closed["status"] == "closed"
    assert (await client.post(f"/api/cycles/{cycle['id']}/close", headers=h)).status_code == 409
    assert (await client.post(f"/api/cycles/{cycle['id']}/publish", headers=h)).status_code == 409


async def test_publish_with_nothing_to_create_is_refused(client, world):
    h = world["headers"]["admin"]
    cycle = (await client.post("/api/cycles", headers=h, json=cycle_body(term="even"))).json()
    r = await client.post(f"/api/cycles/{cycle['id']}/publish", headers=h)
    assert r.status_code == 422 and "teacher assigned" in r.json()["detail"]


async def test_student_submits_once_second_is_rejected(client, world):
    await open_cycle(client, world)
    forms = await student_forms(client, world)
    assert [f["type"] for f in forms] == ["teaching", "curriculum"]
    assert all(not f["submitted"] for f in forms)
    teaching = next(f for f in forms if f["type"] == "teaching")
    assert teaching["faculty"]["name"] == "Test Faculty"

    h = world["headers"]["student"]
    url = f"/api/forms/{teaching['id']}/responses"
    first = await client.post(url, headers=h, json=TEACHING)
    assert first.status_code == 201, first.text
    second = await client.post(url, headers=h, json=TEACHING)
    assert (
        second.status_code == 409
        and second.json()["detail"] == "You've already submitted this form."
    )

    after = await student_forms(client, world)
    assert next(f for f in after if f["type"] == "teaching")["submitted"] is True
    form = (await client.get(f"/api/forms/{teaching['id']}", headers=h)).json()
    assert form["submitted"] is True and len(form["questions"]) == 11

    # What was stored: no student id, a per-form code, the date only.
    doc = await world["db"].responses.find_one({})
    assert set(doc) == {
        "_id",
        "form_id",
        "student_hash",
        "type",
        "likert",
        "texts",
        "submitted_on",
        "is_synthetic",
    }
    assert str(world["student"]["_id"]) not in str(doc)
    assert doc["texts"] == {"liked": "Clear explanations.", "improve": None, "other": None}
    assert (doc["submitted_on"].hour, doc["submitted_on"].minute) == (0, 0)
    assert doc["is_synthetic"] is False


async def test_hash_differs_per_form():
    a = student_form_hash("student1", "formA")
    assert a != student_form_hash("student1", "formB") and a != student_form_hash(
        "student2", "formA"
    )
    assert len(a) == 64


async def test_submission_validation(client, world):
    await open_cycle(client, world)
    forms = await student_forms(client, world)
    teaching = next(f for f in forms if f["type"] == "teaching")
    curriculum = next(f for f in forms if f["type"] == "curriculum")
    h = world["headers"]["student"]
    missing = {"likert": {k: 4 for k in ASPECT_KEYS[:-1]}, "texts": {}}
    r = await client.post(f"/api/forms/{teaching['id']}/responses", headers=h, json=missing)
    assert r.status_code == 422 and "1 missing" in r.json()["detail"]
    out_of_range = {"likert": {k: 6 for k in ASPECT_KEYS}}
    assert (
        await client.post(f"/api/forms/{teaching['id']}/responses", headers=h, json=out_of_range)
    ).status_code == 422
    too_long = {"likert": TEACHING["likert"], "texts": {"liked": "x" * 2001}}
    assert (
        await client.post(f"/api/forms/{teaching['id']}/responses", headers=h, json=too_long)
    ).status_code == 422
    wrong_form = await client.post(
        f"/api/forms/{curriculum['id']}/responses", headers=h, json=TEACHING
    )
    assert wrong_form.status_code == 422
    ok = await client.post(f"/api/forms/{curriculum['id']}/responses", headers=h, json=CURRICULUM)
    assert ok.status_code == 201


async def test_not_enrolled_closed_and_not_open(client, world):
    await open_cycle(client, world)
    form_id = (await student_forms(client, world))[0]["id"]
    outsider = await make_user(
        world["db"], "student", department_id=world["cse"], roll_no=ROLL_NUMBERS[2]
    )
    h_out = await login(client, outsider["roll_no"])
    assert (await client.get(f"/api/forms/{form_id}", headers=h_out)).status_code == 403
    assert (
        await client.post(f"/api/forms/{form_id}/responses", headers=h_out, json=TEACHING)
    ).status_code == 403
    assert await student_forms(client, {"headers": {"student": h_out}}) == []

    # past closes_at counts as closed even while the status still says open
    await world["db"].feedback_cycles.update_many(
        {}, {"$set": {"closes_at": now() - timedelta(hours=1)}}
    )
    r = await client.post(
        f"/api/forms/{form_id}/responses", headers=world["headers"]["student"], json=TEACHING
    )
    assert r.status_code == 409 and "closed" in r.json()["detail"]


async def test_feedback_hidden_below_minimum_then_averages(client, world, monkeypatch):
    monkeypatch.setenv("MIN_RESPONSES_FOR_DISPLAY", "2")
    get_settings.cache_clear()
    await open_cycle(client, world)
    db = world["db"]
    teaching = next(f for f in await student_forms(client, world) if f["type"] == "teaching")
    await client.post(
        f"/api/forms/{teaching['id']}/responses", headers=world["headers"]["student"], json=TEACHING
    )
    url = f"/api/feedback/faculty/{world['faculty']['_id']}"
    stats = (await client.get(url, headers=world["headers"]["faculty"])).json()[0]
    assert stats["responses"] == 1 and stats["min_required"] == 2
    assert stats["visible"] is False and stats["likert_means"] is None
    assert stats["comments"] == [] and stats["comments_status"] == "hidden_below_minimum"

    # a second enrolled student answers with 2s: the mean of 4 and 2 is 3
    other = await make_user(db, "student", department_id=world["cse"], roll_no=ROLL_NUMBERS[3])
    await db.courses.update_one(
        {"_id": world["course_id"]}, {"$push": {"student_ids": other["_id"]}}
    )
    h2 = await login(client, other["roll_no"])
    low = {"likert": {k: 2 for k in ASPECT_KEYS}, "texts": {}}
    assert (
        await client.post(f"/api/forms/{teaching['id']}/responses", headers=h2, json=low)
    ).status_code == 201
    stats = (await client.get(url, headers=world["headers"]["hod"])).json()[0]
    assert stats["visible"] is True and stats["eligible"] == 2
    assert stats["likert_means"] == {k: 3.0 for k in ASPECT_KEYS}
    assert stats["comments"] == [] and stats["comments_status"] == "awaiting_analysis"


async def test_feedback_access(client, world):
    url = f"/api/feedback/faculty/{world['faculty']['_id']}"
    h = world["headers"]
    assert (await client.get(url, headers=h["hod_ece"])).status_code == 403
    assert (await client.get(url, headers=h["student"])).status_code == 403
    assert (
        await client.get(f"/api/feedback/faculty/{world['hod']['_id']}", headers=h["faculty"])
    ).status_code == 403
    assert (await client.get(url, headers=h["admin"])).status_code == 200


async def test_hod_sees_only_department_forms(client, world):
    cycle = await open_cycle(client, world)
    url = f"/api/cycles/{cycle['id']}/forms"
    assert len((await client.get(url, headers=world["headers"]["hod"])).json()) == 2
    assert (await client.get(url, headers=world["headers"]["hod_ece"])).json() == []
    assert (await client.get(url, headers=world["headers"]["faculty"])).status_code == 403
