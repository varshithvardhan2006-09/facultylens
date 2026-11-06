"""Analysis jobs, caching, the moderation queue and faculty comments, with a fake analyser."""

import pytest

from app import db as app_db
from app.config import get_settings
from app.feedback_spec import ASPECT_KEYS
from app.nlp import analyze, registry, summarize
from app.pipeline import jobs, summaries
from app.utils import now
from tests.conftest import ROLL_NUMBERS, login, make_user
from tests.test_feedback_collection import open_cycle, student_forms


def fake_analyze_batch(items):
    docs = []
    for item in items:
        fields = []
        for name, text in (item["texts"] or {}).items():
            if not text:
                continue
            toxic = "useless" in text
            fields.append(
                {
                    "field": name,
                    "redacted": text.replace("98480 12345", "[PHONE]"),
                    "language": "en",
                    "pii_found": {"PHONE": 1} if "98480" in text else {},
                    "toxicity": {"max": 0.95 if toxic else 0.01, "label": "insult"},
                    "moderation_status": "hidden" if toxic else "visible",
                    "sentiment": {
                        "label": "negative" if toxic else "positive",
                        "probs": {"positive": 0.8, "negative": 0.1, "neutral": 0.1},
                    },
                    "emotion": {"joy": 0.9},
                    "irony": 0.1,
                    "sentiment_uncertain": False,
                    "sentences": [
                        {
                            "text": text,
                            "start": 0,
                            "end": len(text),
                            "sentiment": "positive",
                            "toxicity": 0.95 if toxic else 0.01,
                            "aspects": [
                                {
                                    "key": "clarity",
                                    "polarity": "positive",
                                    "conf": 0.9,
                                    "sim": 0.6,
                                    "via": "embedding",
                                }
                            ],
                        }
                    ],
                }
            )
        docs.append(
            {
                "response_id": item["response_id"],
                "form_id": item["form_id"],
                "type": item["type"],
                "model_version": registry.model_version(),
                "fields": fields,
                "overall_sentiment": {"label": "positive", "probs": {"positive": 0.8}}
                if fields
                else None,
                "moderation_status": "hidden"
                if any(f["moderation_status"] == "hidden" for f in fields)
                else "visible",
                "is_synthetic": False,
                "analysed_at": now(),
            }
        )
    return docs


@pytest.fixture
def analysed_world(world, monkeypatch):
    monkeypatch.setattr(analyze, "analyze_batch", fake_analyze_batch)
    monkeypatch.setattr(summarize, "digest", lambda pool: None)  # no distilbart in unit tests
    queued = []
    monkeypatch.setattr(jobs, "enqueue", queued.append)
    world["queued"] = queued
    yield world
    app_db.close_sync_client()


async def submit_teaching(client, world, headers, texts):
    forms = await student_forms(client, {"headers": {"student": headers}})
    teaching = next(f for f in forms if f["type"] == "teaching")
    body = {"likert": {k: 4 for k in ASPECT_KEYS}, "texts": texts}
    r = await client.post(f"/api/forms/{teaching['id']}/responses", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return teaching["id"]


async def test_run_cycle_job_caches_queues_and_aggregates(client, analysed_world):
    world = analysed_world
    h = world["headers"]
    cycle = await open_cycle(client, world)
    await submit_teaching(
        client,
        world,
        h["student"],
        {"liked": "Clear. Call 98480 12345.", "other": "This teacher is useless."},
    )

    summary = (
        await client.get(f"/api/analysis/summary?cycle={cycle['id']}", headers=h["admin"])
    ).json()
    assert summary["pending"] == 1 and summary["analysed"] == 0

    job = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    assert job["status"] == "queued" and world["queued"]
    again = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    assert (
        again["_id" if "_id" in again else "id"] == job["_id" if "_id" in job else "id"]
    )  # one active run per cycle

    from bson import ObjectId

    result = jobs.run_job(ObjectId(job["id"]))
    assert result["status"] == "done" and result["total"] == 1
    status = (await client.get(f"/api/analysis/status/{job['id']}", headers=h["admin"])).json()
    assert status["done"] == 1 and status["counts"]["hidden"] == 1 and status["counts"]["pii"] == 1

    # cached: a second run analyses nothing
    second = jobs.create_job_sync({"kind": "cycle", "cycle_id": ObjectId(cycle["id"])})
    assert jobs.run_job(second)["total"] == 0

    agg = await world["db"].aggregates.find_one({"type": "teaching"})
    assert agg["stats"]["analysed"] == 1 and agg["stats"]["hidden_comments"] == 1

    queue = (await client.get("/api/moderation/queue", headers=h["admin"])).json()
    assert queue["pending"] == 1
    item = queue["items"][0]
    assert item["kind"] == "hidden" and item["text"] == "This teacher is useless."
    assert item["flagged"] == [{"start": 0, "end": 24, "score": 0.95, "sentiment": "positive"}]
    jobs_list = (await client.get("/api/analysis/jobs", headers=h["admin"])).json()
    assert len(jobs_list) == 2 and "response_ids" not in jobs_list[0]


async def test_feedback_comments_moderated_and_redacted(client, analysed_world, monkeypatch):
    world = analysed_world
    monkeypatch.setenv("MIN_RESPONSES_FOR_DISPLAY", "1")
    get_settings.cache_clear()
    h = world["headers"]
    cycle = await open_cycle(client, world)
    await submit_teaching(
        client,
        world,
        h["student"],
        {"liked": "Clear. Call 98480 12345.", "other": "This teacher is useless."},
    )
    url = f"/api/feedback/faculty/{world['faculty']['_id']}"

    before = (await client.get(url, headers=h["faculty"])).json()[0]
    assert before["comments_status"] == "awaiting_analysis" and before["comments"] == []

    job = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    from bson import ObjectId

    jobs.run_job(ObjectId(job["id"]))
    after = (await client.get(url, headers=h["faculty"])).json()[0]
    assert after["comments_status"] == "available"
    texts = [c["text"] for c in after["comments"]]
    assert texts == ["Clear. Call [PHONE]."]  # redacted, and the hidden one isn't there
    assert after["comments"][0]["aspects"] == [["clarity", "positive"]]

    entry = (await client.get("/api/moderation/queue", headers=h["admin"])).json()["items"][0]
    bad = await client.post(
        f"/api/moderation/{entry['id']}/decision", headers=h["admin"], json={"action": "redact"}
    )
    assert bad.status_code == 422
    r = await client.post(
        f"/api/moderation/{entry['id']}/decision",
        headers=h["admin"],
        json={"action": "redact", "text": "The teacher could   be more engaging."},
    )
    assert r.status_code == 200
    final = (await client.get(url, headers=h["faculty"])).json()[0]
    assert "The teacher could be more engaging." in [c["text"] for c in final["comments"]]
    decided = (await client.get("/api/moderation/queue?status=decided", headers=h["admin"])).json()
    assert decided["items"][0]["decision"] == "redact" and decided["pending"] == 0
    assert await world["db"].audit_log.count_documents({"action": "moderation.decision"}) == 1


async def test_interrupted_jobs_and_auto_queue(analysed_world, monkeypatch):
    sync_db = app_db.get_sync_db()
    sync_db.analysis_jobs.insert_many(
        [
            {"kind": "cycle", "status": "running", "created_at": now()},
            {"kind": "auto", "status": "done", "created_at": now()},
        ]
    )
    assert jobs.mark_interrupted(sync_db) == 1
    assert sync_db.analysis_jobs.count_documents({"status": "interrupted"}) == 1

    monkeypatch.setattr(jobs, "_ensure_worker", lambda: None)
    jobs.submit_auto("r1")  # off in tests
    assert "r1" not in jobs._auto
    monkeypatch.setenv("ANALYSIS_ON_SUBMIT", "true")
    get_settings.cache_clear()
    jobs.submit_auto("r2")
    assert "r2" in jobs._auto
    jobs._auto.clear()


async def test_second_student_auto_job_scores_only_new_response(client, analysed_world):
    world = analysed_world
    await open_cycle(client, world)
    form_id = await submit_teaching(client, world, world["headers"]["student"], {"liked": "Clear."})
    other = await make_user(
        world["db"], "student", department_id=world["cse"], roll_no=ROLL_NUMBERS[3]
    )
    await world["db"].courses.update_one(
        {"_id": world["course_id"]}, {"$push": {"student_ids": other["_id"]}}
    )
    await submit_teaching(
        client, world, await login(client, other["roll_no"]), {"liked": "Very clear."}
    )
    ids = [r["_id"] async for r in world["db"].responses.find({})]
    job = jobs.create_job_sync({"kind": "auto", "response_ids": ids[:1]})
    assert jobs.run_job(job)["total"] == 1
    job2 = jobs.create_job_sync({"kind": "auto", "response_ids": ids})
    assert jobs.run_job(job2)["total"] == 1  # the first is cached
    assert await world["db"].analyses.count_documents({}) == 2
    assert form_id


async def test_summaries_follow_the_aggregate(client, analysed_world, monkeypatch):
    from bson import ObjectId

    world = analysed_world
    h = world["headers"]
    cycle = await open_cycle(client, world)
    form_id = await submit_teaching(
        client,
        world,
        h["student"],
        {"liked": "Clear. Call 98480 12345.", "other": "This teacher is useless."},
    )
    sync_db = app_db.get_sync_db()

    # Below the minimum (default 5): no summary is kept.
    job = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    jobs.run_job(ObjectId(job["id"]))
    assert sync_db.summaries.count_documents({}) == 0

    monkeypatch.setenv("MIN_RESPONSES_FOR_DISPLAY", "1")
    get_settings.cache_clear()
    form = sync_db.forms.find_one({"_id": ObjectId(form_id)})
    version = registry.model_version()
    assert summaries.refresh_form(sync_db, form, version) == "built"
    first = sync_db.summaries.find_one({"form_id": form["_id"]})
    assert first["engine"] == "fallback" and first["overall_summary"].startswith("1 student")
    assert "useless" not in str(first)  # hidden text never reaches a summary
    assert summaries.refresh_form(sync_db, form, version) == "kept"

    # A moderation decision changes the aggregate, so the summary is rebuilt.
    entry = (await client.get("/api/moderation/queue", headers=h["admin"])).json()["items"][0]
    r = await client.post(
        f"/api/moderation/{entry['id']}/decision", headers=h["admin"], json={"action": "approve"}
    )
    assert r.status_code == 200
    second = sync_db.summaries.find_one({"form_id": form["_id"]})
    assert second["fingerprint"] != first["fingerprint"]

    # Forced regeneration through the API reuses the job machinery.
    regen = await client.post(f"/api/analysis/summaries?cycle={cycle['id']}", headers=h["admin"])
    assert regen.status_code == 202 and regen.json()["kind"] == "summaries"
    done = jobs.run_job(ObjectId(regen.json()["id"]))
    assert done["status"] == "done" and done["counts"]["summaries_built"] == 1
