"""analyze_batch and aspect assignment with fake models (fast, deterministic)."""

import numpy as np
import pytest

from app.feedback_spec import ASPECT_KEYS
from app.nlp import analyze, aspects, registry


def _probs(label, high=0.8):
    rest = (1 - high) / 2
    return {k: (high if k == label else rest) for k in ("negative", "neutral", "positive")}


class FakeToxicity:
    def predict(self, texts):
        return [
            {"toxicity": 0.95 if "useless" in t else 0.5 if "lazy" in t else 0.01, "muslim": 0.9}
            for t in texts
        ]


class FakeSentiment:
    def predict(self, texts):
        out = []
        for t in texts:
            low = t.lower()
            if "fast" in low or "useless" in low or "lazy" in low:
                out.append(_probs("negative"))
            elif "good" in low or "clear" in low or "helpful" in low:
                out.append(_probs("positive"))
            else:
                out.append(_probs("neutral"))
        return out


class FakeAbsa:
    def predict(self, texts, terms):
        return [
            {"negative": 0.9, "neutral": 0.05, "positive": 0.05}
            if "fast" in t
            else {"negative": 0.05, "neutral": 0.05, "positive": 0.9}
            for t in texts
        ]


class FakeEmotion:
    def predict(self, texts):
        return [{"joy": 0.7, "neutral": 0.3, "anger": 0.0} for _ in texts]


class FakeIrony:
    def predict(self, texts):
        return [{"irony": 0.95 if t.startswith("Wow") else 0.1, "non_irony": 0.05} for t in texts]


class FakeNer:
    def entities(self, texts):
        return [[] for _ in texts]


@pytest.fixture
def fake_models(monkeypatch):
    models = {
        "toxicity": FakeToxicity(),
        "sentiment": FakeSentiment(),
        "absa": FakeAbsa(),
        "emotion": FakeEmotion(),
        "irony": FakeIrony(),
        "ner": FakeNer(),
    }
    monkeypatch.setattr(registry, "get", lambda task: models[task])

    def fake_detect(sentences):
        out = []
        for s in sentences:
            if "fast" in s:
                out.append([("pace", 0.6, "embedding")])
            elif "clear" in s:
                out.append([("clarity", 0.7, "embedding")])
            else:
                out.append([])
        return out

    monkeypatch.setattr(aspects, "detect", fake_detect)


def item(i, texts, kind="teaching"):
    return {
        "response_id": i,
        "form_id": 7,
        "type": kind,
        "texts": texts,
        "faculty_names": ["Dr. Kavitha Reddy"],
    }


def test_analyze_batch_decisions(fake_models):
    docs = analyze.analyze_batch(
        [
            item(
                1,
                {
                    "liked": "Very clear teaching. Good examples.",
                    "improve": "The pace is too fast.",
                },
            ),
            item(2, {"liked": "Wow, so helpful.", "other": None}),
            item(3, {"other": "This teacher is useless."}),
            item(4, {"other": "Kavitha mam, call me on 98480 12345."}),
            item(5, {"liked": "", "improve": None}),
            item(6, {"comment": "A bit lazy syllabus."}, kind="curriculum"),
        ]
    )
    by_id = {d["response_id"]: d for d in docs}
    assert all(d["model_version"] == registry.model_version() for d in docs)

    first = by_id[1]
    liked, improve = first["fields"]
    assert liked["sentiment"]["label"] == "positive" and improve["sentiment"]["label"] == "negative"
    assert [s["text"] for s in liked["sentences"]] == ["Very clear teaching.", "Good examples."]
    pace = improve["sentences"][0]["aspects"][0]
    assert (pace["key"], pace["polarity"]) == ("pace", "negative")
    sentence = improve["sentences"][0]
    assert improve["redacted"][sentence["start"] : sentence["end"]] == sentence["text"]
    assert first["moderation_status"] == "visible" and first["overall_sentiment"]["label"]

    assert by_id[2]["fields"][0]["sentiment_uncertain"] is True  # positive + ironic
    assert by_id[3]["moderation_status"] == "hidden"
    assert by_id[3]["fields"][0]["toxicity"] == {"max": 0.95, "label": "toxicity"}

    pii = by_id[4]["fields"][0]
    assert pii["redacted"] == "[FACULTY] mam, call me on [PHONE]."
    assert pii["pii_found"] == {"FACULTY": 1, "PHONE": 1}

    assert by_id[5]["fields"] == [] and by_id[5]["overall_sentiment"] is None
    curriculum = by_id[6]["fields"][0]
    assert curriculum["moderation_status"] == "review"
    assert all(s["aspects"] == [] for s in curriculum["sentences"])


def test_assign_threshold_lexicon_and_second_margin():
    def row(**sims):
        return np.array([sims.get(k, 0.0) for k in ASPECT_KEYS])

    sims = np.vstack(
        [
            row(clarity=0.66, knowledge=0.50),  # second too far below the first: dropped
            row(knowledge=0.38, interaction=0.37),  # both close: kept
            row(behaviour=0.30),  # below threshold, but "strict" names it
            row(),  # nothing
        ]
    )
    sentences = [
        "Explains clearly.",
        "Not engaging but informative.",
        "Too strict with us.",
        "Okay.",
    ]
    out = aspects.assign(sims, sentences)
    assert [[a[0] for a in s] for s in out] == [
        ["clarity"],
        ["knowledge", "interaction"],
        ["behaviour"],
        [],
    ]
    assert out[2][0][2] == "lexicon"


def test_lexicon_word_boundaries():
    assert aspects.lexicon_hits("She always comes late.") == {"punctuality"}
    assert aspects.lexicon_hits("The translation was poor.") == set()  # 'late' inside a word


def test_ratings_only_responses_load_no_model(monkeypatch):
    """A response with no written answers must not load any model (each one costs seconds)."""

    def refuse(task):
        raise AssertionError(f"{task} was loaded for a response with no text")

    monkeypatch.setattr(registry, "get", refuse)
    docs = analyze.analyze_batch([item(1, {"liked": "", "improve": None}), item(2, {})])
    assert [d["fields"] for d in docs] == [[], []]
