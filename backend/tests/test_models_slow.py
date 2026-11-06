"""One real-model integration test per model (run with `pytest -m slow`)."""

import pytest

from app.nlp import registry

pytestmark = pytest.mark.slow

TEXT = "The lectures are clear but the pace is far too fast."


@pytest.mark.parametrize("task", ["sentiment", "toxicity", "emotion", "irony"])
def test_classifier_probabilities(task):
    out = registry.get(task).predict([TEXT, "Great teacher."])
    assert len(out) == 2
    assert all(0.0 <= p <= 1.0 for p in out[0].values())


def test_sentiment_labels():
    probs = registry.get("sentiment").predict(["Excellent, very clear teaching."])[0]
    assert set(probs) == {"negative", "neutral", "positive"}
    assert max(probs, key=probs.get) == "positive"


def test_absa_pair():
    probs = registry.get("absa").predict([TEXT], ["pace"])[0]
    assert max(probs, key=probs.get) == "negative"


def test_embeddings_normalised():
    vec = registry.get("embeddings").encode([TEXT, "clear explanation"])
    assert vec.shape[0] == 2
    assert abs(float((vec[0] ** 2).sum()) - 1.0) < 1e-3


def test_summarizer_generates():
    out = registry.get("summarizer").summarize(" ".join([TEXT] * 6), max_new_tokens=40)
    assert isinstance(out, str) and len(out) > 10


def test_spacy_person():
    ents = registry.get("ner").entities(["Dr. Ramesh Kumar teaches DBMS."])[0]
    assert any(label == "PERSON" for _, label, _, _ in ents)
