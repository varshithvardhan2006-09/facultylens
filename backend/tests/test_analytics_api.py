"""Analytics endpoints with the fake analyser: contents, thresholds and who may see what."""

import pytest
from bson import ObjectId

from app import db as app_db
from app.config import get_settings
from app.nlp import analyze, summarize
from app.pipeline import jobs
from tests.test_analysis_jobs import fake_analyze_batch, submit_teaching
from tests.test_feedback_collection import open_cycle

TEXTS = {"liked": "Clear and helpful. Call 98480 12345.", "other": "This teacher is useless."}


@pytest.fixture
def analysed_world(world, monkeypatch):
    monkeypatch.setattr(analyze, "analyze_batch", fake_analyze_batch)
    monkeypatch.setattr(summarize, "digest", lambda pool: None)
    monkeypatch.setattr(jobs, "enqueue", lambda job_id: None)
    monkeypatch.setenv("MIN_RESPONSES_FOR_DISPLAY", "1")
    get_settings.cache_clear()
    yield world
    app_db.close_sync_client()


async def _run(client, world):
    h = world["headers"]
    cycle = await open_cycle(client, world)
    form_id = await submit_teaching(client, world, h["student"], TEXTS)
    job = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    jobs.run_job(ObjectId(job["id"]))
    return cycle, form_id


async def test_faculty_analytics_rows(client, analysed_world):
    world = analysed_world
    h = world["headers"]
    cycle, form_id = await _run(client, world)
    url = f"/api/analytics/faculty/{world['faculty']['_id']}"
    out = (await client.get(url, headers=h["faculty"])).json()
    assert out["cycle"]["id"] == cycle["id"] and out["min_required"] == 1
    [row] = out["offerings"]
    assert row["form_id"] == form_id and row["status"] == "available" and row["responses"] == 1
    assert out["combined"]["offerings"] == 1 and out["combined"]["net_score"] is not None
    assert (await client.get(url, headers=h["hod"])).status_code == 200
    assert (await client.get(url, headers=h["hod_ece"])).status_code == 403
    assert (await client.get(url, headers=h["student"])).status_code == 403


async def test_department_analytics_table_and_access(client, analysed_world):
    world = analysed_world
    h = world["headers"]
    await _run(client, world)
    url = f"/api/analytics/department/{world['cse']}"
    out = (await client.get(url, headers=h["hod"])).json()
    assert out["department"]["code"] == "CSE" and len(out["cycles"]) == 1
    [teacher] = out["teachers"]
    assert teacher["name"] == world["faculty"]["name"] and teacher["status"] == "available"
    assert "gender" not in str(out)
    assert out["totals"]["responses"] == 1 and out["totals"]["hidden_comments"] == 1
    assert out["aspects"]["clarity"]["polarity"]["positive"] == 1
    assert (await client.get(url, headers=h["admin"])).status_code == 200
    for role in ("hod_ece", "faculty", "student"):
        assert (await client.get(url, headers=h[role])).status_code == 403


async def test_bias_panel_too_small_then_available(client, analysed_world, monkeypatch):
    world = analysed_world
    h = world["headers"]
    await _run(client, world)
    url = f"/api/analytics/bias?department={world['cse']}"
    small = (await client.get(url, headers=h["hod"])).json()
    assert small["status"] == "too_small" and small["caveat"]
    assert small["groups"]["male"]["teachers"] == 1 and small["groups"]["female"]["teachers"] == 0
    assert "language" not in small

    # Only a "female" group of 0 exists here, so with thresholds of 1 it is still too small:
    # the panel never compares a group with nobody in it.
    monkeypatch.setenv("BIAS_MIN_GROUP_FACULTY", "2")
    monkeypatch.setenv("BIAS_MIN_GROUP_ANSWERS", "1")
    get_settings.cache_clear()
    assert (await client.get(url, headers=h["admin"])).json()["status"] == "too_small"
    assert (await client.get(url, headers=h["hod_ece"])).status_code == 403
    assert (await client.get(url, headers=h["faculty"])).status_code == 403


async def test_sarcasm_scopes(client, analysed_world):
    world = analysed_world
    h = world["headers"]
    await _run(client, world)
    by_dept = await client.get(
        "/api/analytics/sarcasm", params={"department": str(world["cse"])}, headers=h["hod"]
    )
    assert by_dept.status_code == 200 and by_dept.json()["teachers"][0]["answers"] == 1
    mine = await client.get(
        "/api/analytics/sarcasm",
        params={"faculty": str(world["faculty"]["_id"])},
        headers=h["faculty"],
    )
    assert mine.json() == {"faculty": str(world["faculty"]["_id"]), "answer_ids": [], "count": 0}
    assert (
        await client.get(
            "/api/analytics/sarcasm", params={"department": str(world["cse"])}, headers=h["faculty"]
        )
    ).status_code == 403
    assert (await client.get("/api/analytics/sarcasm", headers=h["hod"])).status_code == 422
