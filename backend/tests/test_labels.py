import json

from app.routers import evaluation
from app.services import agreement
from app.utils import now


async def _items(mongo):
    docs = [
        {"source": "rmp", "ref": f"r{i}", "set": "label", "order": i, "text": f"Comment {i}."}
        for i in range(3)
    ]
    docs.append({"source": "app", "ref": "a0", "set": "label", "order": 3, "text": "App comment."})
    result = await mongo.eval_items.insert_many(docs)
    return [str(i) for i in result.inserted_ids]


async def _team(mongo, client, world):
    """Admin and the CSE faculty label; the CSE HoD adjudicates."""
    h = world["headers"]["admin"]
    for user, mode in ((world["faculty"], "annotator"), (world["hod"], "adjudicator")):
        r = await client.patch(f"/api/users/{user['_id']}", headers=h, json={"annotator": mode})
        assert r.status_code == 200 and r.json()["annotator"] == mode
    admin = await mongo.users.find_one({"role": "admin"})
    await mongo.users.update_one({"_id": admin["_id"]}, {"$set": {"annotator": "annotator"}})
    return world["headers"]["admin"], world["headers"]["faculty"], world["headers"]["hod"]


async def test_students_cannot_be_annotators(client, world):
    r = await client.patch(
        f"/api/users/{world['student']['_id']}",
        headers=world["headers"]["admin"],
        json={"annotator": "annotator"},
    )
    assert r.status_code == 422 and "annotators" in r.text


async def test_blind_queue_scope_and_upsert(client, mongo, world):
    ids = await _items(mongo)
    admin, faculty, hod = await _team(mongo, client, world)

    r = await client.get("/api/labels/next", headers=faculty)
    body = r.json()
    assert body["item"]["id"] == ids[0] and body["progress"] == {"mine": 0, "total": 3}
    assert set(body["item"]) == {"id", "text", "source"}  # nobody else's label

    # Faculty annotators never get the app's own comments.
    r = await client.post(
        "/api/labels", headers=faculty, json={"item_id": ids[3], "sentiment": "positive"}
    )
    assert r.status_code == 404

    bad = [
        {"item_id": ids[0]},
        {
            "item_id": ids[0],
            "sentiment": "positive",
            "aspects": [{"key": "x", "polarity": "neutral"}],
        },
        {
            "item_id": ids[0],
            "sentiment": "positive",
            "aspects": [{"key": "clarity", "polarity": "positive"}] * 2,
        },
    ]
    for payload in bad:
        assert (await client.post("/api/labels", headers=faculty, json=payload)).status_code == 422

    for sentiment in ("negative", "positive"):  # labelling again replaces the label
        r = await client.post(
            "/api/labels", headers=faculty, json={"item_id": ids[0], "sentiment": sentiment}
        )
        assert r.status_code == 200
    assert await mongo.labels.count_documents({}) == 1
    assert (await client.get("/api/labels/next", headers=faculty)).json()["item"]["id"] == ids[1]

    # The admin annotator still gets item 0 (one label so far) and sees app comments.
    assert (await client.get("/api/labels/next", headers=admin)).json()["progress"]["total"] == 4
    # The adjudicator doesn't label.
    assert (await client.get("/api/labels/next", headers=hod)).status_code == 403


async def test_disagreement_resolution_and_gold(client, mongo, world):
    ids = await _items(mongo)
    admin, faculty, hod = await _team(mongo, client, world)
    clarity = [{"key": "clarity", "polarity": "negative"}]
    for headers, sentiment in ((admin, "negative"), (faculty, "negative")):
        await client.post(
            "/api/labels",
            headers=headers,
            json={"item_id": ids[0], "sentiment": sentiment, "aspects": clarity},
        )
    for headers, sentiment in ((admin, "positive"), (faculty, "neutral")):
        await client.post(
            "/api/labels", headers=headers, json={"item_id": ids[1], "sentiment": sentiment}
        )
    await client.post(
        "/api/labels", headers=faculty, json={"item_id": ids[2], "skip_reason": "not_english"}
    )

    progress = (await client.get("/api/labels/progress", headers=admin)).json()
    assert progress["gold"] == 1 and progress["disagreements"] == 1
    assert progress["agreement"]["status"] == "pending"
    people = {p["mode"]: p for p in progress["annotators"]}
    assert people["adjudicator"]["labelled"] == 0

    r = await client.get("/api/labels/disagreements", headers=hod)
    item = r.json()["items"][0]
    assert item["id"] == ids[1] and {item["a"]["sentiment"], item["b"]["sentiment"]} == {
        "positive",
        "neutral",
    }
    assert (await client.get("/api/labels/disagreements", headers=faculty)).status_code == 403
    r = await client.post(
        "/api/labels/resolve", headers=hod, json={"item_id": ids[1], "sentiment": "positive"}
    )
    assert r.status_code == 200
    progress = (await client.get("/api/labels/progress", headers=admin)).json()
    assert progress["gold"] == 2 and progress["disagreements"] == 0


async def test_reference_summaries_and_grounding(client, mongo, world):
    ids = await _items(mongo)
    _admin, faculty, _ = await _team(mongo, client, world)
    from bson import ObjectId

    group = await mongo.eval_groups.insert_one(
        {
            "order": 0,
            "item_ids": [ObjectId(i) for i in ids[:2]],
            "system": {
                "bullets": [
                    {"kind": "strength", "text": "Clear", "evidence": ["Comment 0."]},
                    {"kind": "improvement", "text": "Pace", "evidence": ["Comment 1."]},
                ]
            },
        }
    )
    gid = str(group.inserted_id)
    r = await client.get("/api/labels/groups/next", headers=faculty)
    assert r.json()["group"]["comments"] == ["Comment 0.", "Comment 1."]
    payload = {"strengths": [" Explains well ", ""], "improvements": ["Too fast"]}
    for _ in range(2):  # writing again replaces the reference
        r = await client.post(f"/api/labels/groups/{gid}/reference", headers=faculty, json=payload)
        assert r.status_code == 200
    doc = await mongo.eval_groups.find_one({"_id": group.inserted_id})
    assert len(doc["references"]) == 1 and doc["references"][0]["strengths"] == ["Explains well"]
    assert (await client.get("/api/labels/groups/next", headers=faculty)).json()["group"] is None

    r = await client.get("/api/labels/grounding/next", headers=faculty)
    assert len(r.json()["group"]["bullets"]) == 2
    r = await client.post(
        "/api/labels/grounding",
        headers=faculty,
        json={"group_id": gid, "checks": [{"index": 5, "supported": True}]},
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/labels/grounding",
        headers=faculty,
        json={
            "group_id": gid,
            "checks": [{"index": 0, "supported": True}, {"index": 1, "supported": False}],
        },
    )
    assert r.status_code == 200
    assert (await client.get("/api/labels/grounding/next", headers=faculty)).json()["group"] is None


def test_agreement_kappa_needs_thirty_pairs():
    labels, t = [], now()
    for i in range(40):
        a = "positive" if i % 2 else "negative"
        b = a if i < 36 else "neutral"
        aspects = [{"key": "clarity", "polarity": a}] if i % 3 == 0 else []
        labels.append(
            {"item_id": i, "annotator_id": "A", "sentiment": a, "aspects": aspects, "at": t}
        )
        labels.append(
            {"item_id": i, "annotator_id": "B", "sentiment": b, "aspects": aspects, "at": t}
        )
    out = agreement.agreement(labels)
    assert out["status"] == "ok" and out["pairs"] == 40
    assert 0.8 < out["sentiment"] < 1 and out["raw_agreement"] == 0.9
    assert out["aspect_presence"]["clarity"]["kappa"] == 1.0
    assert out["aspect_presence"]["pace"]["kappa"] is None  # never marked
    assert agreement.agreement(labels[:20])["status"] == "pending"


async def test_survey_and_results(client, mongo, world, tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "RESULTS_FILE", tmp_path / "evaluation.json")
    admin = world["headers"]["admin"]
    assert (await client.get("/api/evaluation/results", headers=admin)).json() == {
        "status": "not_run"
    }
    (tmp_path / "evaluation.json").write_text(json.dumps({"generated_at": "x"}), encoding="utf-8")
    assert (await client.get("/api/evaluation/results", headers=admin)).json()["status"] == "ok"

    faculty = world["headers"]["faculty"]
    assert (await client.get("/api/survey/mine", headers=faculty)).json() == {"answered": False}
    answers = {"usefulness": 5, "accuracy": 4, "fairness": 4, "actionability": 3}
    for comment in ("Useful", "  Changed my mind  "):
        r = await client.post(
            "/api/survey", headers=faculty, json={"answers": answers, "comment": comment}
        )
        assert r.status_code == 200
    assert await mongo.survey_responses.count_documents({}) == 1
    mine = (await client.get("/api/survey/mine", headers=faculty)).json()
    assert mine["answered"] and mine["comment"] == "Changed my mind"
    bad = {**answers, "fairness": 6}
    assert (
        await client.post("/api/survey", headers=faculty, json={"answers": bad})
    ).status_code == 422
