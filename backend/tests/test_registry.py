import pytest

from app.config import get_settings
from app.nlp import registry


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch):
    monkeypatch.setattr(registry, "_loaded", {})
    monkeypatch.setattr(registry, "_stats", {t: registry.Stats() for t in registry.MODELS})
    monkeypatch.setattr(registry, "_init_runtime", lambda: None)


class FakeModel:
    instances = 0

    def __init__(self, repo, stats):
        FakeModel.instances += 1
        self.repo, self.stats = repo, stats


def test_every_spec_task_present():
    assert set(registry.MODELS) == {
        "sentiment",
        "embeddings",
        "absa",
        "toxicity",
        "emotion",
        "irony",
        "summarizer",
        "ner",
    }


def test_model_id_follows_ml_mode(monkeypatch):
    monkeypatch.setenv("ML_MODE", "light")
    get_settings.cache_clear()
    assert registry.model_id("embeddings") == "sentence-transformers/all-MiniLM-L6-v2"
    light_version = registry.model_version()
    monkeypatch.setenv("ML_MODE", "full")
    get_settings.cache_clear()
    assert registry.model_id("embeddings") == "sentence-transformers/all-mpnet-base-v2"
    assert registry.model_id("summarizer") == "facebook/bart-large-cnn"
    assert registry.model_version() != light_version
    assert registry.model_version().startswith("full-")


def test_get_loads_lazily_once(monkeypatch):
    FakeModel.instances = 0
    monkeypatch.setitem(registry._WRAPPERS, "classifier", FakeModel)
    assert not registry.is_loaded("sentiment")
    first = registry.get("sentiment")
    second = registry.get("sentiment")
    assert first is second and FakeModel.instances == 1
    assert first.repo == registry.model_id("sentiment")
    row = next(r for r in registry.status() if r["task"] == "sentiment")
    assert row["loaded"] is True and row["load_seconds"] is not None


def test_unknown_task_raises():
    with pytest.raises(KeyError):
        registry.get("nope")


def test_stats_average():
    s = registry.Stats()
    s.record(4, 0.2)
    s.record(4, 0.2)
    assert s.avg_ms_per_item == 50.0
    assert registry.Stats().avg_ms_per_item is None
