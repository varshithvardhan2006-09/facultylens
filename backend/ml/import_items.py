"""Build the evaluation items (SPEC §8.1): `python -m ml.import_items --rmp [--app]`.

--rmp  The public RateMyProfessors sample (Jibo He, Mendeley Data, DOI 10.17632/fvtfjyvw7d.2,
       CC BY 4.0), saved as ml/data/rmp/RateMyProfessor_Sample data.csv. Only the comment, the
       student's own star rating and a one-way professor key are kept; each comment is redacted
       (the professor's name becomes [FACULTY]) before it is stored. Names, schools, departments,
       dates and demographic columns are never stored.
--app  The app's own teaching comments from real (non-synthetic) responses, as already
       redacted and moderated by the pipeline. Hidden answers are left out.

Sets: `label` (300 comments both annotators label), `benchmark` (about 3,000 comments scored
against the student's own star rating) and `group` (20 professors' comments for reference
summaries). Everything is drawn with a fixed seed.
"""

import argparse
import hashlib
import random
import sys
from pathlib import Path
from typing import Any

from app import db
from app.nlp import pii, preprocess
from app.pipeline.aggregate import effective_field
from app.utils import now

SEED = 2026
DATA = Path(__file__).resolve().parent / "data" / "rmp" / "RateMyProfessor_Sample data.csv"
LABEL_SIZE = 300
BENCHMARK_SIZE = 3000
GROUPS = 20
GROUP_MIN, GROUP_MAX = 8, 12
MIN_WORDS, MAX_WORDS = 3, 120
APP_ORDER_START = 100_000  # the app's comments come after the public ones in the queue


def star_label(star: float) -> str:
    """RateMyProfessors' own bands: 3.5-5 good, 2.5-3.4 average, 1-2.4 poor."""
    if star >= 3.5:
        return "positive"
    if star >= 2.5:
        return "neutral"
    return "negative"


def clean(text: Any) -> str | None:
    if not isinstance(text, str):
        return None
    text = preprocess.normalise(text.replace("\\'", "'").replace('\\"', '"'))
    words = len(text.split())
    if not MIN_WORDS <= words <= MAX_WORDS or text.lower().startswith("no comments"):
        return None
    if preprocess.detect_language(text) != "en":
        return None
    return text


def group_key(professor: str, school: str) -> str:
    return hashlib.sha256(f"{professor}|{school}".encode()).hexdigest()[:12]


def read_rmp(path: Path) -> list[dict[str, Any]]:
    import pandas as pd

    frame = pd.read_csv(path, usecols=["professor_name", "school_name", "student_star", "comments"])
    rows = []
    for index, row in enumerate(frame.itertuples(index=False)):
        text = clean(row.comments)
        if text is None or row.student_star != row.student_star:  # NaN star
            continue
        rows.append(
            {
                "ref": f"rmp:{index}",
                "text": text,
                "professor": str(row.professor_name),
                "star": float(row.student_star),
                "group": group_key(str(row.professor_name), str(row.school_name)),
            }
        )
    return rows


def _stratified(rows: list[dict], size: int, rng: random.Random, balanced: bool) -> list[dict]:
    by_label: dict[str, list[dict]] = {}
    for row in rows:
        by_label.setdefault(star_label(row["star"]), []).append(row)
    picked = []
    for _label, members in sorted(by_label.items()):
        share = 1 / len(by_label) if balanced else len(members) / len(rows)
        picked += rng.sample(members, min(len(members), round(size * share)))
    rng.shuffle(picked)
    return picked


def select(rows: list[dict[str, Any]], seed: int = SEED) -> dict[str, Any]:
    """Pure selection: groups, label set and benchmark, never sharing a professor."""
    rng = random.Random(seed)
    by_group: dict[str, list[dict]] = {}
    for row in rows:
        by_group.setdefault(row["group"], []).append(row)
    candidates = sorted(g for g, members in by_group.items() if len(members) >= GROUP_MIN)
    chosen = rng.sample(candidates, min(GROUPS, len(candidates)))
    groups = [rng.sample(by_group[g], min(GROUP_MAX, len(by_group[g]))) for g in chosen]

    rest = [r for r in rows if r["group"] not in set(chosen)]
    label = _stratified(rest, LABEL_SIZE, rng, balanced=True)
    taken = {r["ref"] for r in label}
    benchmark = _stratified(
        [r for r in rest if r["ref"] not in taken], BENCHMARK_SIZE, rng, balanced=False
    )
    # 80/20 by professor, so no teacher's comments sit on both sides of the split.
    professors = sorted({r["group"] for r in benchmark})
    rng.shuffle(professors)
    test = set(professors[: round(len(professors) * 0.2)])
    for r in benchmark:
        r["split"] = "test" if r["group"] in test else "train"
    return {"groups": groups, "label": label, "benchmark": benchmark}


def redact(rows: list[dict[str, Any]]) -> None:
    out = pii.redact_batch([r["text"] for r in rows], [[r["professor"]] for r in rows])
    for row, (text, found) in zip(rows, out, strict=True):
        row["text"] = text
        row["pii"] = found


def _item(row: dict, set_name: str, order: int, stamp) -> dict[str, Any]:
    doc = {
        "source": "rmp",
        "ref": row["ref"],
        "set": set_name,
        "order": order,
        "text": row["text"],
        "star": row["star"],
        "star_label": star_label(row["star"]),
        "group": row["group"],
        "created_at": stamp,
    }
    if "split" in row:
        doc["split"] = row["split"]
    return doc


def import_rmp(database, path: Path = DATA, replace: bool = False) -> dict[str, int]:
    existing = database.eval_items.count_documents({"source": "rmp"})
    if existing and not replace:
        print("Public-dataset items already exist; pass --replace to rebuild them.")
        return {"existing": existing}
    rmp_ids = [i["_id"] for i in database.eval_items.find({"source": "rmp"}, {"_id": 1})]
    if database.labels.count_documents({"item_id": {"$in": rmp_ids}}):
        raise SystemExit("People have already labelled these items; rebuilding would lose that.")
    database.eval_items.delete_many({"source": "rmp"})
    database.eval_groups.delete_many({"source": "rmp"})

    picked = select(read_rmp(path))
    every = picked["label"] + picked["benchmark"] + [r for g in picked["groups"] for r in g]
    redact(every)
    stamp = now()
    docs = [_item(r, "label", i, stamp) for i, r in enumerate(picked["label"])]
    docs += [_item(r, "benchmark", i, stamp) for i, r in enumerate(picked["benchmark"])]
    database.eval_items.insert_many(docs)
    for order, members in enumerate(picked["groups"]):
        group_docs = [_item(r, "group", i, stamp) for i, r in enumerate(members)]
        ids = database.eval_items.insert_many(group_docs).inserted_ids
        database.eval_groups.insert_one(
            {"source": "rmp", "order": order, "item_ids": ids, "created_at": stamp}
        )
    return {
        "label": len(picked["label"]),
        "benchmark": len(picked["benchmark"]),
        "groups": len(picked["groups"]),
        "pii_redacted": sum(sum(r["pii"].values()) for r in every),
    }


def import_app(database) -> dict[str, int]:
    """Real teaching answers (never synthetic), as faculty would see them."""
    added = 0
    rng = random.Random(SEED)
    for analysis in database.analyses.find({"type": "teaching", "is_synthetic": {"$ne": True}}):
        for field in analysis.get("fields", []):
            visible, text = effective_field(field)
            if not visible or not text or field.get("language") != "en":
                continue
            ref = f"app:{analysis['response_id']}:{field['field']}"
            result = database.eval_items.update_one(
                {"source": "app", "ref": ref},
                {
                    "$setOnInsert": {
                        "set": "label",
                        "order": APP_ORDER_START + rng.randrange(1_000_000),
                        "text": text,
                        "created_at": now(),
                    }
                },
                upsert=True,
            )
            added += bool(result.upserted_id)
    return {"app_added": added}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rmp", action="store_true", help="import the public dataset sample")
    parser.add_argument("--app", action="store_true", help="add the app's real comments")
    parser.add_argument("--replace", action="store_true", help="rebuild the public items")
    args = parser.parse_args(argv)
    if not (args.rmp or args.app):
        parser.error("choose --rmp and/or --app")
    database = db.get_sync_db()
    if args.rmp:
        if not DATA.exists():
            print(f"Download the dataset first: {DATA}", file=sys.stderr)
            return 1
        print(import_rmp(database, replace=args.replace))
    if args.app:
        print(import_app(database))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
