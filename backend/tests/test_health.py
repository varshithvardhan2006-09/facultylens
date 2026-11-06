import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth.deps import get_current_user
from app.config import BACKEND_DIR
from app.main import create_app
from app.nlp import registry


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def _ping_returns(value):
    async def fake():
        return value

    return fake


def test_health_ok_when_mongo_up(client, monkeypatch):
    monkeypatch.setattr(db, "ping", _ping_returns(True))
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["mongo"] == "ok"
    assert body["ml_mode"] in {"light", "full"}
    assert body["privacy_contact"]  # the privacy notice names who to contact


def test_health_503_when_mongo_down(client, monkeypatch):
    monkeypatch.setattr(db, "ping", _ping_returns(False))
    r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["mongo"] == "unreachable"


def test_health_models_lists_every_task_without_loading(client):
    client.app.dependency_overrides[get_current_user] = lambda: {"_id": "a", "role": "admin"}
    r = client.get("/api/health/models")
    assert r.status_code == 200
    body = r.json()
    assert {m["task"] for m in body["models"]} == set(registry.MODELS)
    assert body["loaded_count"] == 0
    assert body["process_rss_mb"] > 0
    assert body["model_version"] == registry.model_version()


def test_cors_allows_only_frontend_origin(client):
    def preflight(origin):
        return client.options(
            "/api/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

    assert preflight("http://localhost:5173").headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert "access-control-allow-origin" not in preflight("http://evil.example").headers


def test_importing_main_loads_no_ml_library():
    code = (
        "import sys, app.main; "
        "bad = [m for m in ('torch', 'transformers', 'spacy', 'sentence_transformers') "
        "if m in sys.modules]; print(bad); sys.exit(1 if bad else 0)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=BACKEND_DIR
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


async def test_live_ping_and_indexes(mongo):
    assert await db.ping()
    created = await db.ensure_indexes(mongo)
    assert set(created) == set(db.INDEXES)
    responses = await mongo["responses"].index_information()
    assert responses["one_response_per_student"]["unique"] is True
    users = await mongo["users"].index_information()
    assert users["roll_no_unique"]["sparse"] is True
    await db.ensure_indexes(mongo)  # idempotent
