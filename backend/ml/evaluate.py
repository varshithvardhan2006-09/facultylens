# ruff: noqa: E501  (Markdown table rows in report_md read better unwrapped)
"""The evaluation (SPEC §8): `python -m ml.evaluate [--finetune] [--skip-summaries]`.

Writes ml/results/evaluation.json (read by the admin Evaluation page), PNG charts and
ml/results/RESULTS.md. Every section reports real numbers or says what it is still waiting for;
nothing is estimated or filled in. Synthetic seed data is never used.

Data: the public RateMyProfessors sample imported by `ml.import_items` (comments scored against
each student's own star rating, and the comments people label in the app), the app's own real
comments once labelled, and a hand-built 50-sentence moderation/PII test set.
"""

import argparse
import json
import random
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import db
from app.config import get_settings
from app.feedback_spec import ASPECT_KEYS, ASPECT_LABELS
from app.nlp import aspects, pii, preprocess, registry, scoring
from app.services import agreement
from ml import baseline

RESULTS = Path(__file__).resolve().parent / "results"
SET_FILE = Path(__file__).resolve().parent / "data" / "moderation_pii_set.jsonl"
SENTIMENTS = list(agreement.SENTIMENTS)
GOLD_MIN = 100  # gold labels needed before the human-labelled comparison is reported
FINETUNE_MIN = 300  # SPEC §8.3: fine-tune only on a gold set of at least 300
REFERENCES_MIN = 20  # SPEC §8.6: 20 groups with human references
SIM_GRID = [round(0.25 + 0.025 * i, 3) for i in range(11)]  # 0.25 .. 0.50
NEGATION = re.compile(
    r"\b(?:not|no|never|hardly|nothing|nobody|neither|nor|without)\b|n't", re.IGNORECASE
)
SEED = 2026
DATASET = {
    "name": "Big Data Set from RateMyProfessor.com for Professors' Teaching Evaluation",
    "author": "Jibo He",
    "doi": "10.17632/fvtfjyvw7d.2",
    "licence": "CC BY 4.0",
    "url": "https://data.mendeley.com/datasets/fvtfjyvw7d/2",
}


def pending(have: int, need: int, what: str) -> dict[str, Any]:
    return {"status": "pending", "have": have, "need": need, "what": what}


# ---------------------------------------------------------------- metrics


def classification(y_true: list[str], y_pred: list[str], labels=None) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

    labels = labels or SENTIMENTS
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    # A class with no true and no predicted items would score 0 and drag the average down.
    seen = set(y_true) | set(y_pred)
    present = [i for i, lab in enumerate(labels) if lab in seen]
    return {
        "n": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 3),
        "macro_f1": round(float(sum(f[i] for i in present) / len(present)), 3) if present else None,
        "per_class": {
            lab: {
                "precision": round(float(p[i]), 3),
                "recall": round(float(r[i]), 3),
                "f1": round(float(f[i]), 3),
                "support": int(s[i]),
            }
            for i, lab in enumerate(labels)
        },
        "confusion": {
            "labels": labels,
            "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        },
    }


def binary(truth: list[bool], predicted: list[bool]) -> dict[str, Any]:
    tp = sum(t and p for t, p in zip(truth, predicted, strict=True))
    fp = sum(p and not t for t, p in zip(truth, predicted, strict=True))
    fn = sum(t and not p for t, p in zip(truth, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    # A class that exists but is never found scores 0, so it still lowers the macro average.
    f1 = None if not tp + fn else 2 * tp / (2 * tp + fp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "support": sum(truth),
        "precision": None if precision is None else round(precision, 3),
        "recall": None if recall is None else round(recall, 3),
        "f1": None if f1 is None else round(f1, 3),
    }


# ---------------------------------------------------------------- sentiment


def transformer_predict(texts: list[str]) -> list[str]:
    return [scoring.sentiment_label(p) for p in registry.get("sentiment").predict(texts)]


def compare_sentiment(
    train: list[tuple[str, str]],
    test: list[tuple[str, str]],
    finetune: bool = False,
    transformer=transformer_predict,
) -> dict[str, Any]:
    """Every model on one train/test split, with the negation slice of the test set."""
    test_texts = [t for t, _ in test]
    truth = [y for _, y in test]
    negated = [i for i, t in enumerate(test_texts) if NEGATION.search(t)]
    predictions: dict[str, list[str]] = {}
    timings: dict[str, float] = {}
    for name, make in baseline.BASELINES.items():
        t0 = time.perf_counter()
        model = make().fit([t for t, _ in train], [y for _, y in train])
        predictions[name] = model.predict(test_texts)
        timings[name] = time.perf_counter() - t0
    t0 = time.perf_counter()
    predictions["Twitter-RoBERTa (pretrained, zero-shot)"] = transformer(test_texts)
    timings["Twitter-RoBERTa (pretrained, zero-shot)"] = time.perf_counter() - t0
    if finetune:
        from ml.finetune import finetune_predict

        t0 = time.perf_counter()
        predictions["DistilBERT (fine-tuned on CPU)"] = finetune_predict(train, test_texts)
        timings["DistilBERT (fine-tuned on CPU)"] = time.perf_counter() - t0

    models = {}
    for name, predicted in predictions.items():
        report = classification(truth, predicted)
        report["negation"] = (
            {
                "n": len(negated),
                "accuracy": round(sum(predicted[i] == truth[i] for i in negated) / len(negated), 3),
                "macro_f1": classification(
                    [truth[i] for i in negated], [predicted[i] for i in negated]
                )["macro_f1"],
            }
            if negated
            else None
        )
        report["seconds"] = round(timings[name], 1)
        models[name] = report
    return {
        "status": "ok",
        "n_train": len(train),
        "n_test": len(test),
        "test_distribution": dict(Counter(truth)),
        "models": models,
    }


def split_gold(rows: list[tuple[str, str]], seed: int = SEED):
    """80/20, stratified when every class has at least 2 items."""
    from sklearn.model_selection import train_test_split

    labels = [y for _, y in rows]
    stratify = labels if min(Counter(labels).values()) >= 2 else None
    return train_test_split(rows, test_size=0.2, random_state=seed, stratify=stratify)


# ---------------------------------------------------------------- aspects


def _sentences(text: str) -> list[str]:
    return [text[s:e] for s, e in preprocess.split_sentences(text)]


def aspect_predictions(texts: list[str], threshold: float | None = None):
    """Comment-level aspects found by the app's detector, with ABSA polarity per aspect."""
    sentences = [_sentences(t) for t in texts]
    flat = [s for group in sentences for s in group]
    if not flat:
        return [{} for _ in texts]
    emb = registry.get("embeddings").encode(flat)
    settings = get_settings()
    original = settings.aspect_sim
    if threshold is not None:
        settings.aspect_sim = threshold
    try:
        hits = aspects.assign(emb @ aspects.prototypes().T, flat)
    finally:
        settings.aspect_sim = original
    pairs, cursor = [], 0
    for index, group in enumerate(sentences):
        for sentence in group:
            for key, _, _ in hits[cursor]:
                pairs.append((index, sentence, key))
            cursor += 1
    out: list[dict[str, tuple[str, float]]] = [{} for _ in texts]
    if pairs:
        probs = registry.get("absa").predict(
            [s for _, s, _ in pairs], [aspects.ASPECT_TERMS[k] for _, _, k in pairs]
        )
        for (index, _, key), p in zip(pairs, probs, strict=True):
            label = max(p, key=p.get)
            if key not in out[index] or p[label] > out[index][key][1]:
                out[index][key] = (label, p[label])
    return [{k: v[0] for k, v in found.items()} for found in out]


def score_aspects(gold: list[dict[str, str]], predicted: list[dict[str, str]]) -> dict[str, Any]:
    per_aspect = {}
    for key in ASPECT_KEYS:
        per_aspect[key] = {
            "label": ASPECT_LABELS[key],
            **binary([key in g for g in gold], [key in p for p in predicted]),
        }
    every = binary(
        [key in g for g in gold for key in ASPECT_KEYS],
        [key in p for p in predicted for key in ASPECT_KEYS],
    )
    f1s = [v["f1"] for v in per_aspect.values() if v["f1"] is not None and v["support"]]
    truth, pred = [], []
    for g, p in zip(gold, predicted, strict=True):
        for key, polarity in g.items():
            if key in p:
                truth.append(polarity)
                pred.append(p[key])
    return {
        "per_aspect": per_aspect,
        "micro": every,
        "macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else None,
        "polarity": classification(truth, pred) if truth else None,
    }


def evaluate_aspects(gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """gold_rows: [{text, aspects: {key: polarity}}]. ASPECT_SIM tuned on train only."""
    if len(gold_rows) < GOLD_MIN:
        return pending(len(gold_rows), GOLD_MIN, "gold-labelled comments")
    train, test = split_gold([(r["text"], json.dumps(r["aspects"])) for r in gold_rows])
    train_gold = [json.loads(a) for _, a in train]
    tuning = []
    for threshold in SIM_GRID:
        predicted = aspect_predictions([t for t, _ in train], threshold)
        tuning.append({"aspect_sim": threshold, **score_aspects(train_gold, predicted)["micro"]})
    best = max(tuning, key=lambda r: (r["f1"] or 0, -abs(r["aspect_sim"] - 0.35)))
    test_gold = [json.loads(a) for _, a in test]
    texts = [t for t, _ in test]
    return {
        "status": "ok",
        "n_train": len(train),
        "n_test": len(test),
        "current_aspect_sim": get_settings().aspect_sim,
        "tuned_aspect_sim": best["aspect_sim"],
        "tuning_on_train": tuning,
        "test_with_current": score_aspects(test_gold, aspect_predictions(texts)),
        "test_with_tuned": score_aspects(test_gold, aspect_predictions(texts, best["aspect_sim"])),
    }


# ---------------------------------------------------------------- moderation and PII


def evaluate_moderation_pii(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    texts = [r["text"] for r in rows]
    sentences = [_sentences(t) or [t] for t in texts]
    flat = [s for group in sentences for s in group]
    scores, cursor = [], 0
    probs = registry.get("toxicity").predict(flat)
    for group in sentences:
        scores.append(
            max(scoring.toxicity_score(p)[0] for p in probs[cursor : cursor + len(group)])
        )
        cursor += len(group)
    truth = [r["toxic"] for r in rows]
    moderation = {
        "n": len(rows),
        "toxic": sum(truth),
        "hide_threshold": settings.tox_hide,
        "review_threshold": settings.tox_review,
        "hidden": binary(truth, [s >= settings.tox_hide for s in scores]),
        "hidden_or_review": binary(truth, [s >= settings.tox_review for s in scores]),
        "false_alarms": [
            r["id"]
            for r, s in zip(rows, scores, strict=True)
            if s >= settings.tox_hide and not r["toxic"]
        ],
        "missed": [
            r["id"]
            for r, s in zip(rows, scores, strict=True)
            if s < settings.tox_hide and r["toxic"]
        ],
    }
    redacted = pii.redact_batch(texts, [[r["faculty"]] for r in rows])
    found = [set(counts) for _, counts in redacted]
    kinds = sorted({k for r in rows for k in r["pii"]})
    per_kind = {k: binary([k in r["pii"] for r in rows], [k in f for f in found]) for k in kinds}
    person = {"NAME", "FACULTY"}
    per_kind["PERSON (name or teacher)"] = binary(
        [bool(person & set(r["pii"])) for r in rows], [bool(person & f) for f in found]
    )
    per_kind["ANY"] = binary([bool(r["pii"]) for r in rows], [bool(f) for f in found])
    return {"status": "ok", "moderation": moderation, "pii": {"n": len(rows), "per_kind": per_kind}}


# ---------------------------------------------------------------- summaries


def system_summary(texts: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the app's own pipeline on one teacher's comments and summarise them."""
    from app.nlp import analyze, summarize
    from app.pipeline.aggregate import compute_stats

    items = [
        {
            "response_id": t["id"],
            "form_id": "eval",
            "type": "teaching",
            "texts": {"other": t["text"]},
            "faculty_names": [],
        }
        for t in texts
    ]
    rows = []
    for item, doc in zip(items, analyze.analyze_batch(items), strict=True):
        doc["_id"] = item["response_id"]
        rows.append({"response": {"likert": {}}, "analysis": doc})
    stats = compute_stats(rows, "teaching")
    out = summarize.summarise(stats)
    pool = {
        e["id"]: e["text"]
        for aspect in (stats.get("aspects") or {}).values()
        for items in (aspect.get("evidence") or {}).values()
        for e in items
    }
    bullets = []
    for kind, key in (("strength", "strengths"), ("improvement", "improvements")):
        for item in out[key]:
            ids = item.get("evidence_ids") or []
            bullets.append(
                {
                    "kind": kind,
                    "text": item["text"],
                    "evidence": [pool[i] for i in ids if i in pool][:3],
                }
            )
    return {"engine": out["engine"], "bullets": bullets, "model_version": registry.model_version()}


def _joined(points: list[str]) -> str:
    return "\n".join(p.strip() for p in points if p.strip())


def score_summaries(candidates: list[str], references: list[list[str]]) -> dict[str, Any]:
    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    rouge: dict[str, list[float]] = {"rouge1": [], "rouge2": [], "rougeL": []}
    for cand, refs in zip(candidates, references, strict=True):
        for key in rouge:
            rouge[key].append(max(scorer.score(ref, cand)[key].fmeasure for ref in refs))
    from bert_score import score as bert

    model = registry.eval_model_id("bertscore")
    _, _, f1 = bert(candidates, references, model_type=model, lang="en", verbose=False)
    return {
        "n": len(candidates),
        **{k: round(sum(v) / len(v), 3) for k, v in rouge.items()},
        "bertscore_f1": round(float(f1.mean()), 3),
        "bertscore_model": model,
    }


def evaluate_summaries(database, skip: bool = False) -> dict[str, Any]:
    groups = list(database.eval_groups.find({}).sort("order", 1))
    if not groups:
        return pending(0, REFERENCES_MIN, "teacher groups (run ml.import_items --rmp)")
    version = registry.model_version()
    built = 0
    if not skip:
        for group in groups:
            current = group.get("system") or {}
            if current.get("model_version") == version:
                continue  # unchanged, so earlier grounding checks still apply
            texts = [
                {"id": str(i["_id"]), "text": i["text"]}
                for i in database.eval_items.find({"_id": {"$in": group["item_ids"]}})
            ]
            group["system"] = system_summary(texts)
            database.eval_groups.update_one(
                {"_id": group["_id"]},
                {"$set": {"system": group["system"]}, "$unset": {"grounding": ""}},
            )
            group.pop("grounding", None)
            built += 1

    # Only real people's work counts: demo accounts may try the tool but never score it.
    demo = demo_users(database)
    for g in groups:
        g["references"] = [r for r in g.get("references") or [] if r["annotator_id"] not in demo]
        g["grounding"] = [e for e in g.get("grounding") or [] if e["annotator_id"] not in demo]
    checks = [c for g in groups for entry in g["grounding"] for c in entry["checks"]]
    grounding = (
        {
            "checked_bullets": len(checks),
            "groups_checked": sum(bool(g["grounding"]) for g in groups),
            "supported_rate": round(sum(c["supported"] for c in checks) / len(checks), 3),
        }
        if checks
        else pending(0, 1, "grounding checks")
    )
    with_refs = [g for g in groups if g.get("references") and g.get("system")]
    out: dict[str, Any] = {
        "groups": len(groups),
        "system_built_now": built,
        "engines": dict(Counter((g.get("system") or {}).get("engine") for g in groups)),
        "grounding": grounding,
        "llm": "not run: no GROQ_API_KEY" if not get_settings().groq_api_key else "see engines",
    }
    if len(with_refs) < REFERENCES_MIN:
        out.update(pending(len(with_refs), REFERENCES_MIN, "groups with a human reference"))
        return out
    candidates = [_joined([b["text"] for b in g["system"]["bullets"]]) for g in with_refs]
    references = [
        [_joined(r["strengths"] + r["improvements"]) for r in g["references"]] for g in with_refs
    ]
    out.update({"status": "ok", **score_summaries(candidates, references)})
    return out


# ---------------------------------------------------------------- survey and performance


def demo_users(database) -> set:
    return {u["_id"] for u in database.users.find({"is_synthetic": True}, {"_id": 1})}


def evaluate_survey(database) -> dict[str, Any]:
    demo = demo_users(database)
    rows = [r for r in database.survey_responses.find({}) if r["faculty_id"] not in demo]
    if not rows:
        return pending(0, 5, "faculty survey answers")
    questions = {}
    for q in ("usefulness", "accuracy", "fairness", "actionability"):
        values = [r["answers"][q] for r in rows]
        questions[q] = {
            "mean": round(sum(values) / len(values), 2),
            "distribution": {str(k): values.count(k) for k in range(1, 6)},
        }
    return {
        "status": "ok" if len(rows) >= 5 else "partial",
        "n": len(rows),
        "questions": questions,
        "comments": sum(bool(r.get("comment")) for r in rows),
    }


def performance() -> dict[str, Any]:
    out = {}
    for name in ("pipeline_check.json", "model_check_t4.json"):
        path = RESULTS / name
        if path.exists():
            out[name.removesuffix(".json")] = json.loads(path.read_text(encoding="utf-8"))
    if not out:
        return pending(0, 1, "performance runs (app.pipeline.bench, registry --check)")
    pipe = out.get("pipeline_check", {})
    check = out.get("model_check_t4", {})
    return {
        "status": "ok",
        "per_response_ms_mean": pipe.get("per_response_ms_warm_mean"),
        "per_response_ms_p95": pipe.get("per_response_ms_warm_p95"),
        "peak_rss_mb": pipe.get("peak_rss_mb"),
        "responses": pipe.get("responses_analysed"),
        "all_models_rss_mb": check.get("all_loaded_rss_mb"),
        "machine": pipe.get("machine") or check.get("machine"),
        "measured_at": pipe.get("measured_at"),
    }


# ---------------------------------------------------------------- charts and report


def charts(results: dict[str, Any]) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written = []
    for key, section in results["sentiment"].items():
        if section.get("status") != "ok":
            continue
        names = list(section["models"])
        values = [section["models"][n]["macro_f1"] for n in names]
        fig, ax = plt.subplots(figsize=(7, 0.6 * len(names) + 1), dpi=150)
        ax.barh(names, values, color="#3b5bdb")
        for y, v in enumerate(values):
            ax.text(v + 0.01, y, f"{v:.2f}", va="center", fontsize=9)
        ax.set_xlim(0, 1)
        ax.invert_yaxis()
        ax.set_xlabel("Macro-F1 (higher is better)")
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        path = RESULTS / f"sentiment_{key}_macro_f1.png"
        fig.savefig(path)
        plt.close(fig)
        written.append(path.name)

        best = max(names, key=lambda n: section["models"][n]["macro_f1"])
        conf = section["models"][best]["confusion"]
        fig, ax = plt.subplots(figsize=(4.2, 3.6), dpi=150)
        ax.imshow(conf["matrix"], cmap="Blues")
        for i, row in enumerate(conf["matrix"]):
            for j, v in enumerate(row):
                ax.text(j, i, str(v), ha="center", va="center", fontsize=9)
        ax.set_xticks(range(3), conf["labels"])
        ax.set_yticks(range(3), conf["labels"])
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title(best, fontsize=9)
        fig.tight_layout()
        path = RESULTS / f"sentiment_{key}_confusion.png"
        fig.savefig(path)
        plt.close(fig)
        written.append(path.name)
    return written


def _fmt(value) -> str:
    return "–" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)


def _pending_line(section: dict[str, Any]) -> str:
    return f"*Pending:* {section['have']} of {section['need']} {section['what']}.\n"


def report_md(results: dict[str, Any]) -> str:
    lines = [
        "# FacultyLens evaluation results",
        "",
        f"Generated by `python -m ml.evaluate` on {results['generated_at']} "
        f"(`model_version={results['model_version']}`). Every number below comes from "
        "`ml/results/evaluation.json`; a section marked *pending* has no number yet because the "
        "human labels it needs do not exist yet.",
        "",
        "## Data",
        "",
        f"- **Public dataset:** {DATASET['name']} ({DATASET['author']}, Mendeley Data, "
        f"DOI {DATASET['doi']}, licence {DATASET['licence']}). Only the comment text, the "
        "student's own star rating and a one-way professor key are kept; every comment was "
        "redacted by the app's PII step before storage.",
        "- **Benchmark labels come from the students' own star ratings** (RateMyProfessors bands:"
        " 3.5–5 positive, 2.5–3 neutral, 1–2 negative). A star rating is not a reading of the "
        "comment's tone, so these are weak labels; the human-labelled set is the real test.",
        "- **Domain gap:** these are reviews of US college teachers, not Indian engineering "
        "colleges. Real MVSR comments join the labelling queue as they are collected.",
        f"- Labelling set: {results['data']['label_set']} comments; gold labels so far: "
        f"{results['data']['gold']}. Synthetic seed data is never used.",
        "",
        "## Inter-annotator agreement (Cohen's kappa)",
        "",
    ]
    agree = results["agreement"]
    if agree["status"] != "ok":
        lines.append(
            f"*Pending:* {agree['pairs']} of {agree['min_pairs']} comments labelled by both "
            "annotators.\n"
        )
    else:
        lines += [
            "| Task | Kappa |",
            "|---|---:|",
            f"| Overall sentiment | {_fmt(agree['sentiment'])} |",
            f"| Aspect polarity (aspects both marked; n={agree['aspect_polarity']['items']}) | "
            f"{_fmt(agree['aspect_polarity']['kappa'])} |",
        ]
        lines += [
            f"| Aspect present: {ASPECT_LABELS[k]} | {_fmt(v['kappa'])} |"
            for k, v in agree["aspect_presence"].items()
        ]
        lines.append(
            f"\nComments both annotators labelled identically: {agree['raw_agreement']:.1%}.\n"
        )

    titles = {
        "benchmark": "Sentiment: benchmark scored against star ratings",
        "gold": "Sentiment: human gold labels",
    }
    for key, title in titles.items():
        section = results["sentiment"][key]
        lines += ["", f"## {title}", ""]
        if section["status"] != "ok":
            lines.append(_pending_line(section))
            continue
        lines += [
            f"Train {section['n_train']}, test {section['n_test']} "
            f"(test classes: {section['test_distribution']}).",
            "",
            "| Model | Accuracy | Macro-F1 | F1 neg | F1 neu | F1 pos | Negation slice macro-F1 (n) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for name, m in section["models"].items():
            neg = m["negation"]
            lines.append(
                f"| {name} | {_fmt(m['accuracy'])} | {_fmt(m['macro_f1'])} | "
                f"{_fmt(m['per_class']['negative']['f1'])} | {_fmt(m['per_class']['neutral']['f1'])} | "
                f"{_fmt(m['per_class']['positive']['f1'])} | "
                f"{_fmt(neg['macro_f1']) if neg else '–'} ({neg['n'] if neg else 0}) |"
            )
        lines += [
            "",
            f"![macro-F1](sentiment_{key}_macro_f1.png) ![confusion](sentiment_{key}_confusion.png)",
        ]

    asp = results["aspects"]
    lines += ["", "## Aspect detection and polarity (human gold)", ""]
    if asp["status"] != "ok":
        lines.append(_pending_line(asp))
    else:
        cur, tuned = asp["test_with_current"], asp["test_with_tuned"]
        lines += [
            f"`ASPECT_SIM` tuned on the train split only: {asp['tuned_aspect_sim']} "
            f"(current {asp['current_aspect_sim']}). Test set: {asp['n_test']} comments.",
            "",
            "| Aspect | Precision | Recall | F1 (current) | F1 (tuned) | Support |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for key in ASPECT_KEYS:
            c, t = cur["per_aspect"][key], tuned["per_aspect"][key]
            lines.append(
                f"| {c['label']} | {_fmt(c['precision'])} | {_fmt(c['recall'])} | {_fmt(c['f1'])} | "
                f"{_fmt(t['f1'])} | {c['support']} |"
            )
        pol = cur["polarity"]
        lines.append(
            f"\nAspect polarity on aspects both gold and the detector found: macro-F1 "
            f"{_fmt(pol['macro_f1']) if pol else '–'} (n={pol['n'] if pol else 0})."
        )

    mod = results["moderation_pii"]
    lines += [
        "",
        "## Moderation and PII (hand-built 50-sentence test set)",
        "",
        "The set (`ml/data/moderation_pii_set.jsonl`) was written by hand for this project with "
        "edge cases: harsh but fair criticism, words like *stupid* or *killing* used harmlessly, "
        "sarcasm, Indian names and titles, phone numbers in several formats, OU roll numbers, "
        "dates and course codes that look like numbers. Its labels follow from how each "
        "sentence was written. It is small, so treat these as a sanity check.",
        "",
        "| Check | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    m = mod["moderation"]
    for name, key in (
        (f"Abuse hidden (≥ {m['hide_threshold']})", "hidden"),
        (f"Abuse hidden or sent to review (≥ {m['review_threshold']})", "hidden_or_review"),
    ):
        b = m[key]
        lines.append(
            f"| {name} | {_fmt(b['precision'])} | {_fmt(b['recall'])} | {_fmt(b['f1'])} | {b['support']} |"
        )
    for kind, b in mod["pii"]["per_kind"].items():
        lines.append(
            f"| PII: {kind} | {_fmt(b['precision'])} | {_fmt(b['recall'])} | {_fmt(b['f1'])} | {b['support']} |"
        )
    lines.append(
        f"\nFalse alarms (hidden but not abusive): sentences {m['false_alarms'] or 'none'}. "
        f"Missed abuse: sentences {m['missed'] or 'none'}."
    )

    summ = results["summaries"]
    lines += ["", "## Summaries", ""]
    lines.append(
        f"{summ.get('groups', 0)} teacher groups; generated by: {summ.get('engines', {})}. "
        f"LLM: {summ.get('llm', '–')}."
    )
    if summ.get("status") == "ok":
        lines += [
            "",
            "| ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 |",
            "|---:|---:|---:|---:|",
            f"| {_fmt(summ['rouge1'])} | {_fmt(summ['rouge2'])} | {_fmt(summ['rougeL'])} | "
            f"{_fmt(summ['bertscore_f1'])} |",
            "",
            f"BERTScore uses `{summ['bertscore_model']}` (CPU-friendly; the default "
            "roberta-large is not), so it is not comparable with papers that use the default.",
        ]
    else:
        lines.append("\n" + _pending_line(summ))
    g = summ.get("grounding", {})
    if g.get("status") == "pending":
        lines.append("Evidence grounding: *pending* (no grounding checks yet).")
    elif g:
        lines.append(
            f"Evidence grounding: {g['supported_rate']:.1%} of {g['checked_bullets']} checked "
            "bullets are supported by the evidence they cite."
        )

    survey = results["survey"]
    lines += ["", "## Faculty usefulness survey", ""]
    if survey["status"] == "pending":
        lines.append(_pending_line(survey))
    else:
        lines += [
            f"{survey['n']} teachers answered (1–5).",
            "",
            "| Question | Mean |",
            "|---|---:|",
        ]
        lines += [f"| {q.title()} | {v['mean']} |" for q, v in survey["questions"].items()]

    perf = results["performance"]
    lines += ["", "## Performance on this CPU", ""]
    if perf["status"] == "ok":
        lines.append(
            f"{perf['responses']} responses: {perf['per_response_ms_mean']} ms per response on "
            f"average, p95 {perf['per_response_ms_p95']} ms, peak RAM {perf['peak_rss_mb']} MB "
            f"(all models loaded: {perf['all_models_rss_mb']} MB). Machine: "
            f"{perf['machine'].get('cpu')}, {perf['machine'].get('logical_cores')} threads, "
            f"{perf['machine'].get('ram_gb')} GB RAM. "
            "See `docs/MODEL_CHECK.md`."
        )
    else:
        lines.append(_pending_line(perf))
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- main


def load_rows(database, query: dict[str, Any]) -> list[dict[str, Any]]:
    return list(database.eval_items.find(query).sort("order", 1))


def run(database, finetune: bool = False, skip_summaries: bool = False) -> dict[str, Any]:
    registry._init_runtime()
    random.seed(SEED)
    demo = list(demo_users(database))
    labels = list(database.labels.find({"annotator_id": {"$nin": demo}}))
    adjudications = list(database.adjudications.find({"by": {"$nin": demo}}))
    gold = agreement.gold(labels, adjudications)
    label_items = {i["_id"]: i for i in load_rows(database, {"set": "label"})}
    gold_rows = [
        {"text": label_items[item]["text"], **g} for item, g in gold.items() if item in label_items
    ]

    bench = load_rows(database, {"set": "benchmark"})
    bench_train = [(i["text"], i["star_label"]) for i in bench if i.get("split") == "train"]
    bench_test = [(i["text"], i["star_label"]) for i in bench if i.get("split") == "test"]
    sentiment: dict[str, Any] = {
        "benchmark": compare_sentiment(bench_train, bench_test, finetune)
        if bench_test
        else pending(0, 1, "benchmark comments (run ml.import_items --rmp)")
    }
    gold_sentiment = [(r["text"], r["sentiment"]) for r in gold_rows]
    if len(gold_sentiment) >= GOLD_MIN:
        train, test = split_gold(gold_sentiment)
        sentiment["gold"] = compare_sentiment(
            train, test, finetune and len(gold_sentiment) >= FINETUNE_MIN
        )
    else:
        sentiment["gold"] = pending(len(gold_sentiment), GOLD_MIN, "gold-labelled comments")

    rows = [json.loads(line) for line in SET_FILE.read_text(encoding="utf-8").splitlines()]
    results = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model_version": registry.model_version(),
        "dataset": DATASET,
        "data": {
            "label_set": len(label_items),
            "gold": len(gold_rows),
            "benchmark": len(bench),
            "app_items": sum(i["source"] == "app" for i in label_items.values()),
        },
        "agreement": agreement.agreement(labels),
        "sentiment": sentiment,
        "aspects": evaluate_aspects(
            [{"text": r["text"], "aspects": r["aspects"]} for r in gold_rows]
        ),
        "moderation_pii": evaluate_moderation_pii(rows),
        "summaries": evaluate_summaries(database, skip=skip_summaries),
        "survey": evaluate_survey(database),
        "performance": performance(),
    }
    results["charts"] = charts(results)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the FacultyLens evaluation (SPEC §8).")
    parser.add_argument("--finetune", action="store_true", help="also fine-tune DistilBERT (slow)")
    parser.add_argument(
        "--skip-summaries", action="store_true", help="don't build missing system summaries"
    )
    args = parser.parse_args(argv)
    RESULTS.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results = run(db.get_sync_db(), finetune=args.finetune, skip_summaries=args.skip_summaries)
    results["seconds"] = round(time.perf_counter() - t0, 1)
    (RESULTS / "evaluation.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (RESULTS / "RESULTS.md").write_text(report_md(results), encoding="utf-8")
    print(f"Wrote {RESULTS / 'evaluation.json'} and RESULTS.md in {results['seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
