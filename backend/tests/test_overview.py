"""GET /faculty/{id}/overview and /evidence: access, minimum responses, redaction, highlighting."""

import pytest
from bson import ObjectId

from app import db as app_db
from app.config import get_settings
from app.nlp import analyze, summarize
from app.pipeline import jobs
from app.routers.overview import agreement_label
from tests.test_analysis_jobs import fake_analyze_batch, submit_teaching
from tests.test_feedback_collection import open_cycle


@pytest.fixture
def analysed_world(world, monkeypatch):
    monkeypatch.setattr(analyze, "analyze_batch", fake_analyze_batch)
    monkeypatch.setattr(summarize, "digest", lambda pool: None)
    monkeypatch.setattr(jobs, "enqueue", lambda job_id: None)
    yield world
    app_db.close_sync_client()


TEXTS = {"liked": "Clear. Call 98480 12345.", "other": "This teacher is useless."}


async def _analysed(client, world, monkeypatch, minimum="1"):
    monkeypatch.setenv("MIN_RESPONSES_FOR_DISPLAY", minimum)
    get_settings.cache_clear()
    h = world["headers"]
    cycle = await open_cycle(client, world)
    form_id = await submit_teaching(client, world, h["student"], TEXTS)
    job = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    jobs.run_job(ObjectId(job["id"]))
    return cycle, form_id


def test_agreement_labels():
    assert agreement_label(None, 10) == "too_few"
    assert agreement_label(0.9, 4) == "too_few"
    assert agreement_label(0.45, 20) == "agrees"
    assert agreement_label(0.1, 20) == "mixed"
    assert agreement_label(-0.3, 20) == "disagrees"


async def test_overview_for_owner_hod_and_others(client, analysed_world, monkeypatch):
    world = analysed_world
    h = world["headers"]
    cycle, form_id = await _analysed(client, world, monkeypatch)
    url = f"/api/faculty/{world['faculty']['_id']}/overview"

    mine = (await client.get(url, headers=h["faculty"])).json()
    assert mine["feedback_access"] and mine["is_owner"] and mine["profile"]["status"] == "none"
    assert mine["cycles"][0]["id"] == cycle["id"]
    assert mine["cycles"][0]["offerings"][0]["form_id"] == form_id
    sel = mine["selected"]
    assert sel["status"] == "available" and sel["responses"] == 1
    assert sel["insights"]["aspects"]["clarity"]["polarity"]["positive"] == 1
    assert sel["insights"]["hidden_comments"] == 1
    assert "evidence" not in str(sel["insights"])  # evidence text comes only from /evidence
    note_ids = sel["insights"]["aspects"]["clarity"]["note_ids"]
    assert note_ids["positive"] and note_ids["positive"][0].endswith(":liked:0")
    assert "Clear" not in str(sel["insights"])
    assert sel["summary"]["engine"] == "fallback"

    hod = (await client.get(url, headers=h["hod"])).json()
    assert hod["feedback_access"] and hod["selected"]["status"] == "available"
    other = (await client.get(url, headers=h["hod_ece"])).json()
    assert other["feedback_access"] is False and "selected" not in other
    assert other["profile"]["name"] == world["faculty"]["name"]
    assert (await client.get(url, headers=h["student"])).status_code == 403

    picked = await client.get(
        url, headers=h["admin"], params={"cycle": cycle["id"], "course": str(world["course_id"])}
    )
    assert picked.json()["selected"]["form_id"] == form_id
    missing = await client.get(url, headers=h["admin"], params={"course": str(ObjectId())})
    assert missing.status_code == 404


async def test_overview_below_minimum_shows_no_insights(client, analysed_world, monkeypatch):
    world = analysed_world
    await _analysed(client, world, monkeypatch, minimum="5")
    sel = (
        await client.get(
            f"/api/faculty/{world['faculty']['_id']}/overview", headers=world["headers"]["faculty"]
        )
    ).json()["selected"]
    assert sel["status"] == "below_minimum" and sel["insights"] is None and sel["summary"] is None


async def test_evidence_is_redacted_highlighted_and_scoped(client, analysed_world, monkeypatch):
    world = analysed_world
    h = world["headers"]
    _, form_id = await _analysed(client, world, monkeypatch)
    sync_db = app_db.get_sync_db()
    analysis = sync_db.analyses.find_one({"form_id": ObjectId(form_id)})
    aid = str(analysis["_id"])
    url = f"/api/faculty/{world['faculty']['_id']}/evidence"

    ids = f"{aid}:liked:0,{aid}:other:0,{aid}:liked,{ObjectId()}:liked:0,garbage,{aid}:liked:9"
    items = (await client.get(url, headers=h["faculty"], params={"ids": ids})).json()
    assert [i["id"] for i in items] == [f"{aid}:liked:0", f"{aid}:liked", f"{aid}:liked:9"]
    first = items[0]
    assert first["text"] == "Clear. Call [PHONE]." and "98480" not in str(items)
    assert first["highlight"] == {"start": 0, "end": len("Clear. Call 98480 12345.")}
    assert first["aspects"] == [{"key": "clarity", "polarity": "positive"}]
    assert items[1]["highlight"] is None and items[2]["highlight"] is None

    # Another teacher's page never returns these answers, and other HoDs are refused.
    other = await app_db.get_db().users.insert_one(
        {"name": "Other Teacher", "role": "faculty", "department_id": world["cse"]}
    )
    foreign = await client.get(
        f"/api/faculty/{other.inserted_id}/evidence", headers=h["admin"], params={"ids": ids}
    )
    assert foreign.json() == []
    refused = await client.get(url, headers=h["hod_ece"], params={"ids": ids})
    assert refused.status_code == 403
