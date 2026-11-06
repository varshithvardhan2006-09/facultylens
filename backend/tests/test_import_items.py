import json
from pathlib import Path

import pandas as pd

from app import db
from app.nlp import pii
from ml import import_items

SET_FILE = Path(import_items.__file__).parent / "data" / "moderation_pii_set.jsonl"


SURNAMES = ["Morgan", "Hayes", "Quinn", "Parker", "Ellis", "Brooks", "Reyes", "Foster"]


def _csv(tmp_path):
    rows = []
    for p in range(8):
        for c in range(6):
            star = [1.0, 2.5, 3.0, 4.5, 5.0, 2.0][(p + c) % 6]
            rows.append(
                {
                    "professor_name": f"Alex {SURNAMES[p]}",
                    "school_name": f"School {p % 3}",
                    "department_name": "Physics",
                    "student_star": star,
                    "gender": "x",
                    "comments": f"{SURNAMES[p]} explains topic {c} well, I'd take it again.",
                }
            )
    rows.append({**rows[0], "comments": "No Comments"})
    rows.append({**rows[0], "comments": "ok"})
    path = tmp_path / "rmp.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _no_spacy(monkeypatch):
    def redact_batch(texts, names):
        return [pii.redact(t, pii.find_spans(t, [], n)) for t, n in zip(texts, names, strict=True)]

    monkeypatch.setattr(pii, "redact_batch", redact_batch)


def _small(monkeypatch):
    for name, value in {
        "GROUPS": 2,
        "GROUP_MIN": 4,
        "GROUP_MAX": 4,
        "LABEL_SIZE": 9,
        "BENCHMARK_SIZE": 12,
    }.items():
        monkeypatch.setattr(import_items, name, value)


def test_star_bands_and_cleaning():
    assert [import_items.star_label(s) for s in (1, 2, 2.5, 3, 3.5, 5)] == [
        "negative",
        "negative",
        "neutral",
        "neutral",
        "positive",
        "positive",
    ]
    assert import_items.clean("I\\'d take it again, great prof") == "I'd take it again, great prof"
    assert import_items.clean("No Comments") is None
    assert import_items.clean("ok") is None
    assert import_items.clean(None) is None


def test_selection_is_repeatable_and_keeps_professors_apart(tmp_path, monkeypatch):
    _small(monkeypatch)
    rows = import_items.read_rmp(_csv(tmp_path))
    assert len(rows) == 48  # the two junk comments are dropped
    first, again = import_items.select(rows), import_items.select(rows)
    assert [r["ref"] for r in first["label"]] == [r["ref"] for r in again["label"]]
    group_keys = {g[0]["group"] for g in first["groups"]}
    assert len(group_keys) == 2
    assert not group_keys & {r["group"] for r in first["label"] + first["benchmark"]}
    labels = [import_items.star_label(r["star"]) for r in first["label"]]
    assert sorted(set(labels)) == ["negative", "neutral", "positive"]
    train = {r["group"] for r in first["benchmark"] if r["split"] == "train"}
    test = {r["group"] for r in first["benchmark"] if r["split"] == "test"}
    assert train and test and not train & test


async def test_import_redacts_and_stores_no_names(tmp_path, monkeypatch, mongo):
    _small(monkeypatch)
    _no_spacy(monkeypatch)
    sync = db.get_sync_db()
    out = import_items.import_rmp(sync, _csv(tmp_path))
    assert out["label"] == 9 and out["groups"] == 2 and out["pii_redacted"] > 0
    items = list(sync.eval_items.find({}))
    stored = json.dumps(
        [{k: v for k, v in i.items() if k not in ("_id", "created_at")} for i in items]
    )
    assert not any(n in stored for n in [*SURNAMES, "Alex", "School"])
    assert "[FACULTY]" in stored
    assert set(items[0]) <= {
        "_id",
        "source",
        "ref",
        "set",
        "order",
        "text",
        "star",
        "star_label",
        "group",
        "split",
        "created_at",
    }
    assert sync.eval_groups.count_documents({}) == 2
    # A second run leaves the items alone; rebuilding is refused once anyone has labelled.
    assert "existing" in import_items.import_rmp(sync, _csv(tmp_path))
    sync.labels.insert_one({"item_id": items[0]["_id"], "annotator_id": "a"})
    try:
        import_items.import_rmp(sync, _csv(tmp_path), replace=True)
        raise AssertionError("expected a refusal")
    except SystemExit as exc:
        assert "labelled" in str(exc)


async def test_app_items_are_real_visible_redacted_teaching_answers(mongo):
    sync = db.get_sync_db()
    field = {"field": "liked", "redacted": "[FACULTY] explains well.", "language": "en"}
    sync.analyses.insert_many(
        [
            {
                "response_id": 1,
                "type": "teaching",
                "fields": [field, {**field, "field": "improve", "moderation_status": "hidden"}],
            },
            {"response_id": 2, "type": "teaching", "is_synthetic": True, "fields": [field]},
            {"response_id": 3, "type": "curriculum", "fields": [field]},
        ]
    )
    assert import_items.import_app(sync) == {"app_added": 1}
    assert import_items.import_app(sync) == {"app_added": 0}  # idempotent
    item = sync.eval_items.find_one({"source": "app"})
    assert item["text"] == "[FACULTY] explains well." and item["set"] == "label"


def test_moderation_pii_set_is_well_formed():
    rows = [json.loads(line) for line in SET_FILE.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 50 and len({r["id"] for r in rows}) == 50
    kinds = {k for r in rows for k in r["pii"]}
    assert kinds == {"FACULTY", "NAME", "PHONE", "ROLL", "EMAIL", "URL"}
    assert 8 <= sum(r["toxic"] for r in rows) <= 15
