# ruff: noqa: E501  (request bodies read better unwrapped)
"""NAAC report endpoints: drafting, who may edit and approve, the export gate, no raw text."""

import io

import pytest
from bson import ObjectId
from docx import Document
from pypdf import PdfReader

from app import db as app_db
from app.config import get_settings
from app.nlp import analyze, summarize
from app.pipeline import jobs
from tests.test_analysis_jobs import fake_analyze_batch, submit_teaching
from tests.test_feedback_collection import open_cycle

RAW = {
    "liked": "Clear. Call 98480 12345.",  # the fake analyser redacts the phone
    "other": "This teacher is useless.",  # hidden by moderation
}


@pytest.fixture
def analysed_world(world, monkeypatch):
    monkeypatch.setattr(analyze, "analyze_batch", fake_analyze_batch)
    monkeypatch.setattr(summarize, "digest", lambda pool: None)
    monkeypatch.setattr(jobs, "enqueue", lambda job_id: None)
    monkeypatch.setenv("MIN_RESPONSES_FOR_DISPLAY", "1")
    get_settings.cache_clear()
    yield world
    app_db.close_sync_client()


async def _ready(client, world):
    """An analysed cycle whose one teaching form has a clear 'pace' gap."""
    h = world["headers"]
    cycle = await open_cycle(client, world)
    form_id = await submit_teaching(client, world, h["student"], RAW)
    job = (await client.post(f"/api/analysis/run?cycle={cycle['id']}", headers=h["admin"])).json()
    jobs.run_job(ObjectId(job["id"]))
    sync = app_db.get_sync_db()
    analysis = sync.analyses.find_one({"form_id": ObjectId(form_id)})
    sync.aggregates.update_one(
        {"form_id": ObjectId(form_id)},
        {
            "$set": {
                "stats.aspects.pace": {
                    "mentions": 3,
                    "polarity": {"positive": 0, "neutral": 0, "negative": 3},
                    "likert_mean": 2.0,
                    "agreement": {"rho": None, "n": 0},
                    "evidence": {
                        "positive": [],
                        "neutral": [],
                        "negative": [
                            {
                                "id": f"{analysis['_id']}:liked:0",
                                "text": "Clear. Call [PHONE].",
                                "conf": 0.9,
                            }
                        ],
                    },
                }
            }
        },
    )
    # A second teacher: a department row may not rest on one person (SPEC Phase 7).
    form = sync.forms.find_one({"_id": ObjectId(form_id)})
    other = sync.users.insert_one(
        {"name": "Second Teacher", "role": "faculty", "department_id": world["cse"]}
    ).inserted_id
    second = sync.forms.insert_one(
        {k: v for k, v in form.items() if k != "_id"} | {"faculty_id": other}
    ).inserted_id
    aggregate = sync.aggregates.find_one({"form_id": ObjectId(form_id)})
    sync.aggregates.insert_one(
        {k: v for k, v in aggregate.items() if k != "_id"}
        | {"form_id": second, "faculty_id": other}
    )
    response = sync.responses.find_one({"form_id": ObjectId(form_id)})
    copy = sync.responses.insert_one(
        {k: v for k, v in response.items() if k != "_id"} | {"form_id": second}
    ).inserted_id
    sync.analyses.insert_one(
        {k: v for k, v in analysis.items() if k != "_id"} | {"form_id": second, "response_id": copy}
    )
    return cycle


async def test_draft_edit_approve_and_scope(client, analysed_world):
    world = analysed_world
    h = world["headers"]
    cycle = await _ready(client, world)
    base = f"/api/reports/naac/{cycle['id']}"

    drafted = (await client.post(f"{base}/draft", headers=h["admin"])).json()
    assert drafted["added"] >= 1 and drafted["replaced"] == 0
    rows = (await client.get(f"{base}/actions", headers=h["hod"])).json()
    pace = next(r for r in rows if r["key"] == "pace")
    assert pace["status"] == "draft" and "2 of 2 CSE course" in pace["issue"]
    assert pace["responsible"].startswith("HoD, ") and "examples" not in pace
    assert (await client.get(f"{base}/actions", headers=h["hod_ece"])).json() == []

    url = f"{base}/actions/{pace['id']}"
    assert (
        await client.put(url, headers=h["hod_ece"], json={"status": "approved"})
    ).status_code == 403
    assert (
        await client.put(url, headers=h["faculty"], json={"status": "approved"})
    ).status_code == 403
    approved = (await client.put(url, headers=h["hod"], json={"status": "approved"})).json()
    assert approved["status"] == "approved"
    edited = (
        await client.put(
            url, headers=h["admin"], json={"action": "Share a weekly coverage plan with students."}
        )
    ).json()
    assert edited["status"] == "draft" and edited["edited"] is True  # an edit reopens approval

    # Re-drafting keeps the edited row and adds nothing new.
    again = (await client.post(f"{base}/draft", headers=h["admin"])).json()
    assert again["kept"] >= 1 and again["added"] == 0

    evidence = (await client.get(f"{url}/evidence", headers=h["hod"])).json()
    assert {e["text"] for e in evidence} == {"Clear. Call [PHONE]."}
    assert (await client.get(f"{url}/evidence", headers=h["hod_ece"])).status_code == 403

    added = await client.post(
        f"{base}/actions",
        headers=h["hod"],
        json={
            "department_id": str(world["cse"]),
            "label": "Library",
            "issue": "Library closes too early.",
            "action": "Extend library hours in exam weeks.",
            "responsible": "Librarian",
        },
    )
    assert added.status_code == 201 and added.json()["source"] == "manual"
    other = await client.post(
        f"{base}/actions",
        headers=h["hod"],
        json={
            "department_id": str(world["ece"]),
            "label": "Other",
            "issue": "Not mine to add.",
            "action": "Nothing to do here.",
            "responsible": "Nobody",
        },
    )
    assert other.status_code == 403
    assert (
        await client.delete(f"{base}/actions/{added.json()['id']}", headers=h["hod"])
    ).status_code == 403
    assert (
        await client.delete(f"{base}/actions/{added.json()['id']}", headers=h["admin"])
    ).status_code == 204


def _pdf_text(raw: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages)


def _docx_text(raw: bytes) -> str:
    doc = Document(io.BytesIO(raw))
    parts = [p.text for p in doc.paragraphs]
    parts += [c.text for t in doc.tables for r in t.rows for c in r.cells]
    parts += [p.text for s in doc.sections for p in s.header.paragraphs]
    return "\n".join(parts)


async def test_export_gate_and_no_unredacted_text(client, analysed_world):
    world = analysed_world
    h = world["headers"]
    cycle = await _ready(client, world)
    base = f"/api/reports/naac/{cycle['id']}"
    assert (
        await client.get(f"{base}.pdf", headers=h["admin"])
    ).status_code == 409  # nothing drafted
    await client.post(f"{base}/draft", headers=h["admin"])
    blocked = await client.get(f"{base}.pdf", headers=h["admin"])
    assert blocked.status_code == 409 and "need approval" in blocked.json()["detail"]

    preview = await client.get(f"{base}.pdf", params={"draft": True}, headers=h["admin"])
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF")
    assert "DRAFT" in preview.headers["content-disposition"]
    assert "DRAFT" in _pdf_text(preview.content)

    status = (await client.get(f"{base}/status", headers=h["admin"])).json()
    assert status["approved"] == 0 and status["ready"] is False
    for row in (await client.get(f"{base}/actions", headers=h["admin"])).json():
        await client.put(
            f"{base}/actions/{row['id']}", headers=h["admin"], json={"status": "approved"}
        )
    assert (await client.get(f"{base}/status", headers=h["hod"])).json()["ready"] is True

    pdf = await client.get(f"{base}.pdf", headers=h["admin"])
    docx = await client.get(f"{base}.docx", headers=h["admin"])
    assert pdf.status_code == 200 and docx.status_code == 200
    teacher = world["faculty"]["name"]
    for text in (_pdf_text(pdf.content), _docx_text(docx.content)):
        flat = " ".join(text.split())
        assert "DRAFT" not in flat
        assert "5. Action Taken Report" in flat
        assert "98480" not in flat and "useless" not in flat  # raw phone, hidden answer
        assert teacher not in flat  # no teacher is named in the published report
    assert (await client.get(f"{base}.pdf", headers=h["hod"])).status_code == 403
