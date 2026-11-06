"""Regression tests for the full-project audit: each one failed before its fix."""

from datetime import timedelta

import pytest
from bson import ObjectId

from app.limiter import limiter
from app.nlp import analyze
from app.nlp.atr import teaching_issues
from app.nlp.preprocess import normalise
from app.schemas.feedback import CycleIn, ResponseIn
from app.utils import anon_id, now, today
from tests.conftest import PASSWORD, login, make_user


async def test_overlong_login_password_is_a_wrong_password(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    for password in ("x" * 100, "अ" * 30):
        r = await client.post(
            "/api/auth/login", json={"username": "t@test.edu", "password": password}
        )
        assert r.status_code == 401


async def test_overlong_new_password_is_refused_politely(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    headers = await login(client, "t@test.edu")
    r = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "x" * 100},
    )
    assert r.status_code == 422


async def test_blank_username_matches_nobody(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    r = await client.post("/api/auth/login", json={"username": "   ", "password": PASSWORD})
    assert r.status_code == 401


async def test_old_access_token_stops_working_after_a_password_change(client, mongo):
    await make_user(
        mongo, "admin", email="t@test.edu", password_changed_at=now() - timedelta(days=1)
    )
    old = await login(client, "t@test.edu")
    assert (await client.get("/api/auth/me", headers=old)).status_code == 200
    r = await client.post(
        "/api/auth/change-password",
        headers=old,
        json={"current_password": PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert r.status_code == 200
    assert (await client.get("/api/auth/me", headers=old)).status_code == 401
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/api/auth/me", headers=fresh)).status_code == 200


async def test_two_tabs_refreshing_together_stay_signed_in(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    await login(client, "t@test.edu")
    first = client.cookies.get("fl_refresh")
    assert (await client.post("/api/auth/refresh")).status_code == 200
    client.cookies.clear()
    client.cookies.set("fl_refresh", first)  # the second tab still holds the old token
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    assert await mongo.refresh_tokens.count_documents({"revoked": False}) == 2


async def test_token_revoked_by_a_password_change_does_not_end_other_sessions(client, mongo):
    await make_user(mongo, "admin", email="t@test.edu")
    headers = await login(client, "t@test.edu")
    stale = client.cookies.get("fl_refresh")
    r = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert r.status_code == 200
    client.cookies.clear()
    client.cookies.set("fl_refresh", stale)
    assert (await client.post("/api/auth/refresh")).status_code == 401
    assert await mongo.refresh_tokens.count_documents({"revoked": False}) == 1


async def test_model_status_is_for_admins(client, world):
    assert (await client.get("/api/health/models")).status_code == 401
    r = await client.get("/api/health/models", headers=world["headers"]["admin"])
    assert r.status_code == 200


async def test_api_responses_carry_security_headers(client, mongo):
    r = await client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("change", [{"name": None}, {"role": None}, {"is_active": None}])
async def test_required_user_fields_cannot_be_nulled(client, world, change):
    r = await client.patch(
        f"/api/users/{world['faculty']['_id']}", headers=world["headers"]["admin"], json=change
    )
    assert r.status_code == 422
    assert (await world["db"].users.find_one({"_id": world["faculty"]["_id"]}))["role"] == "faculty"


async def test_csv_with_an_extra_column_does_not_crash(client, world):
    r = await client.post(
        "/api/users/bulk?dry_run=true",
        headers=world["headers"]["admin"],
        files={
            "file": (
                "u.csv",
                b"name,email,role,department_code,roll_no,gender\n"
                b"Test Name,x@test.edu,faculty,CSE,,,surplus\n",
                "text/csv",
            )
        },
    )
    assert r.status_code != 500


async def test_deactivated_student_can_still_be_removed_from_a_course(client, world):
    db = world["db"]
    await db.users.update_one({"_id": world["student"]["_id"]}, {"$set": {"is_active": False}})
    r = await client.post(
        f"/api/courses/{world['course_id']}/enrol",
        headers=world["headers"]["admin"],
        json={"remove_roll_numbers": [world["student"]["roll_no"]]},
    )
    assert r.status_code == 200
    assert (await db.courses.find_one({"_id": world["course_id"]}))["student_ids"] == []


async def test_hod_reads_only_their_department_courses_of_a_shared_teacher(client, world):
    db = world["db"]
    ece_course = await db.courses.insert_one(
        {
            "code": "EC501",
            "name": "Signals",
            "department_id": world["ece"],
            "academic_year": "2026-27",
            "semester": 5,
            "section": "A",
            "faculty_ids": [world["faculty"]["_id"]],
            "student_ids": [],
            "created_at": now(),
        }
    )
    cycle = await db.feedback_cycles.insert_one(
        {
            "name": "2026-27 Odd Sem",
            "academic_year": "2026-27",
            "term": "odd",
            "status": "open",
            "opens_at": now(),
            "closes_at": now() + timedelta(days=9),
        }
    )
    for course in (world["course_id"], ece_course.inserted_id):
        await db.forms.insert_one(
            {
                "cycle_id": cycle.inserted_id,
                "course_id": course,
                "faculty_id": world["faculty"]["_id"],
                "type": "teaching",
            }
        )
    url = f"/api/feedback/faculty/{world['faculty']['_id']}"
    cse = await client.get(url, headers=world["headers"]["hod"])
    ece = await client.get(url, headers=world["headers"]["hod_ece"])
    assert cse.status_code == 200 and ece.status_code == 200
    assert [f["course"]["code"] for f in cse.json()] == ["CS501"]
    assert [f["course"]["code"] for f in ece.json()] == ["EC501"]
    limiter.reset()


def test_anonymous_ids_do_not_hold_the_time():
    ids = {anon_id() for _ in range(200)}
    assert len(ids) == 200 and all(isinstance(i, ObjectId) for i in ids)
    years = {i.generation_time.year for i in ids}
    assert len(years) > 3  # a real ObjectId would give only this year


def test_today_has_no_time_of_day():
    assert (today().hour, today().minute, today().second) == (0, 0, 0)


def test_control_characters_are_removed_from_answers():
    body = ResponseIn.model_validate(
        {"likert": {}, "texts": {"liked": "good\x01 teacher\x0b"}, "consent": True}
    )
    assert "\x01" not in body.texts["liked"] and "\x0b" not in body.texts["liked"]
    assert "\x01" not in normalise("good\x01 teacher")


def test_cycle_dates_without_a_timezone_compare_safely():
    cycle = CycleIn(
        name="2026-27 Odd Sem",
        academic_year="2026-27",
        term="odd",
        opens_at="2026-12-01T00:00:00Z",
        closes_at="2026-12-20T00:00:00",
    )
    assert cycle.closes_at.tzinfo is not None


def test_long_sentences_are_scored_to_their_end():
    assert analyze._windows("short") == ["short"]
    text = "fine words " * 150 + "ABUSE"
    windows = analyze._windows(text)
    assert len(windows) > 1 and windows[-1].endswith("ABUSE")
    assert all(len(w) <= analyze.WINDOW_CHARS for w in windows)


def test_one_teacher_is_never_reported_as_a_department_issue():
    stats = {"analysed": 10, "aspects": {}}
    forms = [
        {"type": "teaching", "responses": 10, "stats": stats, "faculty_id": "same"},
        {"type": "teaching", "responses": 10, "stats": stats, "faculty_id": "same"},
    ]
    assert teaching_issues({"code": "CSE", "name": "CSE"}, forms, minimum=5) == []
