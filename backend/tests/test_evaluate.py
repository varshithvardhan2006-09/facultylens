import json

import pytest

from app import db
from app.nlp import pii, registry
from ml import baseline
from ml import evaluate as ev


class _Toxicity:
    def predict(self, texts):
        return [{"toxicity": 0.9 if "idiot" in t.lower() else 0.01} for t in texts]


def _no_models(monkeypatch):
    monkeypatch.setattr(registry, "get", lambda task: {"toxicity": _Toxicity()}[task])
    monkeypatch.setattr(
        pii,
        "redact_batch",
        lambda texts, names: [
            pii.redact(t, pii.find_spans(t, [], n)) for t, n in zip(texts, names, strict=True)
        ],
    )


def test_metrics():
    report = ev.classification(
        ["positive", "negative", "neutral"], ["positive", "positive", "neutral"]
    )
    assert report["accuracy"] == 0.667 and report["per_class"]["negative"]["f1"] == 0
    assert report["confusion"]["matrix"][0] == [0, 0, 1]  # the negative went to positive
    b = ev.binary([True, True, False, False], [True, False, True, False])
    assert (b["precision"], b["recall"], b["f1"]) == (0.5, 0.5, 0.5)
    assert ev.binary([False], [False])["precision"] is None


def test_baselines_and_negation_slice():
    words = {
        "positive": "great clear helpful",
        "negative": "awful boring rude",
        "neutral": "okay average fine",
    }
    train = [(f"{w} class {i}", label) for label, w in words.items() for i in range(10)]
    test = [
        ("great and helpful", "positive"),
        ("not great, awful", "negative"),
        ("fine", "neutral"),
    ]
    out = ev.compare_sentiment(train, test, transformer=lambda texts: ["neutral"] * len(texts))
    assert set(out["models"]) == {*baseline.BASELINES, "Twitter-RoBERTa (pretrained, zero-shot)"}
    lr = out["models"]["TF-IDF + Logistic Regression"]
    assert lr["accuracy"] == 1.0 and lr["negation"]["n"] == 1
    assert out["models"]["Twitter-RoBERTa (pretrained, zero-shot)"]["accuracy"] == 0.333


def test_aspect_scoring():
    gold = [{"clarity": "positive"}, {"pace": "negative", "clarity": "negative"}, {}]
    predicted = [{"clarity": "positive"}, {"pace": "positive"}, {"knowledge": "neutral"}]
    out = ev.score_aspects(gold, predicted)
    assert out["per_aspect"]["clarity"]["recall"] == 0.5
    assert out["per_aspect"]["knowledge"]["precision"] == 0
    assert out["polarity"]["n"] == 2 and out["polarity"]["accuracy"] == 0.5
    assert ev.evaluate_aspects([])["status"] == "pending"


async def test_run_writes_honest_pending_sections(mongo, monkeypatch, tmp_path):
    _no_models(monkeypatch)
    monkeypatch.setattr(ev, "RESULTS", tmp_path)
    results = ev.run(db.get_sync_db(), skip_summaries=True)
    assert results["sentiment"]["benchmark"]["status"] == "pending"
    assert results["sentiment"]["gold"] == ev.pending(0, ev.GOLD_MIN, "gold-labelled comments")
    assert results["agreement"]["status"] == "pending"
    assert results["survey"]["status"] == "pending"
    mod = results["moderation_pii"]
    assert mod["status"] == "ok" and mod["moderation"]["n"] == 50
    assert mod["pii"]["per_kind"]["PHONE"]["support"] == 5
    md = ev.report_md(json.loads(json.dumps(results)))
    assert "*Pending:* 0 of 100 gold-labelled comments" in md
    assert "CC BY 4.0" in md


async def test_survey_ignores_synthetic_teachers(mongo):
    sync = db.get_sync_db()
    fake = sync.users.insert_one({"name": "Demo", "is_synthetic": True}).inserted_id
    real = sync.users.insert_one({"name": "Real"}).inserted_id
    answers = {"usefulness": 4, "accuracy": 3, "fairness": 5, "actionability": 2}
    sync.survey_responses.insert_many(
        [
            {"faculty_id": fake, "answers": answers},
            {"faculty_id": real, "answers": answers, "comment": "ok"},
        ]
    )
    out = ev.evaluate_survey(sync)
    assert out["n"] == 1 and out["status"] == "partial"
    assert out["questions"]["fairness"] == {
        "mean": 5.0,
        "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 1},
    }


@pytest.mark.slow
def test_moderation_pii_set_with_real_models():
    rows = [json.loads(line) for line in ev.SET_FILE.read_text(encoding="utf-8").splitlines()]
    out = ev.evaluate_moderation_pii(rows)
    assert out["pii"]["per_kind"]["ROLL"]["recall"] == 1.0
    assert out["moderation"]["hidden"]["recall"] is not None


async def test_demo_accounts_never_count(mongo, monkeypatch, tmp_path):
    _no_models(monkeypatch)
    monkeypatch.setattr(ev, "RESULTS", tmp_path)
    sync = db.get_sync_db()
    item = sync.eval_items.insert_one(
        {"source": "rmp", "ref": "r1", "set": "label", "order": 0, "text": "Clear."}
    ).inserted_id
    demo = [sync.users.insert_one({"name": n, "is_synthetic": True}).inserted_id for n in "ab"]
    for who in demo:
        sync.labels.insert_one(
            {"item_id": item, "annotator_id": who, "sentiment": "positive", "aspects": [], "at": 1}
        )
    results = ev.run(sync, skip_summaries=True)
    assert results["data"]["gold"] == 0 and results["agreement"]["pairs"] == 0
