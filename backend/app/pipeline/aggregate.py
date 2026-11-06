"""Aggregates per teaching form (faculty x course x cycle) and per curriculum form (SPEC §5).

`compute_stats` is pure: it takes responses joined with their analyses and returns the stats.
Hidden comments never become evidence; an admin decision on a comment (approve / hide / redact)
overrides the model's moderation status.
"""

from collections import Counter, defaultdict
from typing import Any

from app.feedback_spec import ASPECT_KEYS, CURRICULUM_KEYS
from app.utils import now

SARCASM_WEIGHT = 0.5
EVIDENCE_PER_POLARITY = 3
MIN_AGREEMENT_PAIRS = 5
POLARITY_SCORE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}


def effective_field(field: dict[str, Any]) -> tuple[bool, str]:
    """(visible to faculty?, text to show) after any admin decision."""
    decision = (field.get("moderation") or {}).get("decision")
    if decision == "hide":
        return False, field["redacted"]
    if decision == "redact":
        return True, field["moderation"].get("text") or field["redacted"]
    if decision == "approve":
        return True, field["redacted"]
    return field.get("moderation_status") != "hidden", field["redacted"]


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < MIN_AGREEMENT_PAIRS or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    from scipy.stats import spearmanr

    rho = spearmanr(xs, ys).statistic
    return None if rho != rho else round(float(rho), 3)  # NaN check


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def compute_stats(rows: list[dict[str, Any]], form_type: str) -> dict[str, Any]:
    """rows: [{"response": {...}, "analysis": {...} | None}] for one form."""
    likert_keys = ASPECT_KEYS if form_type == "teaching" else CURRICULUM_KEYS
    analysed = [r for r in rows if r.get("analysis")]
    likert = {
        k: _mean([r["response"]["likert"][k] for r in rows if k in r["response"].get("likert", {})])
        for k in likert_keys
    }

    weights = Counter()
    answers = 0
    sarcastic = 0
    hidden = review = 0
    languages = Counter()
    emotion_sum: dict[str, float] = defaultdict(float)
    aspect_mentions: dict[str, Counter] = {k: Counter() for k in ASPECT_KEYS}
    aspect_weights: dict[str, Counter] = {k: Counter() for k in ASPECT_KEYS}
    aspect_pairs: dict[str, list[tuple[float, float]]] = {k: [] for k in ASPECT_KEYS}
    evidence: dict[str, dict[str, list[dict]]] = {
        k: {"positive": [], "neutral": [], "negative": []} for k in ASPECT_KEYS
    }
    comment_pool: dict[str, list[dict]] = {"positive": [], "neutral": [], "negative": []}

    for row in analysed:
        analysis, response = row["analysis"], row["response"]
        overall = analysis.get("overall_sentiment")
        if overall:
            # Half weight only when the answer behind the overall label may be sarcastic: flagged
            # "Great teacher." beside a long complaint must not halve the complaint.
            uncertain = any(
                f.get("sentiment_uncertain") and f["sentiment"]["label"] == overall["label"]
                for f in analysis["fields"]
            )
            weights[overall["label"]] += SARCASM_WEIGHT if uncertain else 1.0
        per_aspect_text: dict[str, list[float]] = defaultdict(list)
        for f in analysis["fields"]:
            answers += 1
            sarcastic += bool(f.get("sentiment_uncertain"))
            languages[f.get("language", "en")] += 1
            for k, v in (f.get("emotion") or {}).items():
                emotion_sum[k] += v
            visible, text = effective_field(f)
            decision = (f.get("moderation") or {}).get("decision")
            if not visible:
                hidden += 1
                continue
            if f.get("moderation_status") == "review" and not decision:
                review += 1
            comment_pool[f["sentiment"]["label"]].append(
                {
                    "id": f"{analysis['_id']}:{f['field']}",
                    "text": text,
                    "conf": f["sentiment"]["probs"][f["sentiment"]["label"]],
                    "uncertain": bool(f.get("sentiment_uncertain")),
                }
            )
            if decision == "redact":
                continue  # sentence offsets no longer match an admin-edited text
            for index, s in enumerate(f["sentences"]):
                for a in s.get("aspects", []):
                    polarity = a.get("polarity", "neutral")
                    aspect_mentions[a["key"]][polarity] += 1
                    aspect_weights[a["key"]][polarity] += (
                        SARCASM_WEIGHT if f.get("sentiment_uncertain") else 1.0
                    )
                    per_aspect_text[a["key"]].append(POLARITY_SCORE[polarity])
                    evidence[a["key"]][polarity].append(
                        {
                            "id": f"{analysis['_id']}:{f['field']}:{index}",
                            "text": s["text"],
                            "field": f["field"],
                            "start": s["start"],
                            "end": s["end"],
                            "conf": a.get("conf", 0.0),
                            "uncertain": bool(f.get("sentiment_uncertain")),
                        }
                    )
        for key, scores in per_aspect_text.items():
            rating = response.get("likert", {}).get(key)
            if rating is not None:
                aspect_pairs[key].append((float(rating), sum(scores) / len(scores)))

    total_weight = sum(weights.values())
    stats: dict[str, Any] = {
        "responses": len(rows),
        "analysed": len(analysed),
        "answers": answers,
        "sentiment": {k: round(weights[k], 2) for k in ("positive", "neutral", "negative")},
        "net_score": round((weights["positive"] - weights["negative"]) / total_weight, 3)
        if total_weight
        else None,
        "likert_means": likert,
        "emotion_mix": {k: round(v / answers, 3) for k, v in sorted(emotion_sum.items())}
        if answers
        else {},
        "sarcasm_rate": round(sarcastic / answers, 3) if answers else None,
        "hidden_comments": hidden,
        "in_review": review,
        "languages": dict(languages),
        "top_comments": {
            label: sorted(pool, key=lambda c: (c["uncertain"], -c["conf"]))[:EVIDENCE_PER_POLARITY]
            for label, pool in comment_pool.items()
        },
    }
    if form_type == "teaching":
        stats["aspects"] = {}
        for key in ASPECT_KEYS:
            pairs = aspect_pairs[key]
            stats["aspects"][key] = {
                "mentions": sum(aspect_mentions[key].values()),
                "polarity": {
                    p: aspect_mentions[key][p] for p in ("positive", "neutral", "negative")
                },
                "weighted_polarity": {
                    p: round(aspect_weights[key][p], 2) for p in ("positive", "negative")
                },
                "likert_mean": likert.get(key),
                "agreement": {
                    "rho": spearman([p[0] for p in pairs], [p[1] for p in pairs]),
                    "n": len(pairs),
                },
                "evidence": {polarity: _top(items) for polarity, items in evidence[key].items()},
            }
    return stats


def _top(items: list[dict]) -> list[dict]:
    """Highest confidence first, sarcastic last, one copy of each sentence text."""
    seen, out = set(), []
    for item in sorted(items, key=lambda e: (e["uncertain"], -e["conf"])):
        norm = " ".join(item["text"].lower().split())
        if norm in seen:
            continue
        seen.add(norm)
        out.append(item)
        if len(out) == EVIDENCE_PER_POLARITY:
            break
    return out


def recompute_form(sync_db, form: dict[str, Any], model_version: str) -> dict[str, Any]:
    """Recompute and store the aggregate for one form (synchronous PyMongo, worker thread)."""
    responses = list(sync_db.responses.find({"form_id": form["_id"]}))
    analyses = {
        a["response_id"]: a
        for a in sync_db.analyses.find(
            {"response_id": {"$in": [r["_id"] for r in responses]}, "model_version": model_version}
        )
    }
    rows = [{"response": r, "analysis": analyses.get(r["_id"])} for r in responses]
    stats = compute_stats(rows, form["type"])
    key = {
        "faculty_id": form.get("faculty_id"),
        "course_id": form["course_id"],
        "cycle_id": form["cycle_id"],
        "type": form["type"],
    }
    sync_db.aggregates.update_one(
        key,
        {
            "$set": {
                **key,
                "form_id": form["_id"],
                "model_version": model_version,
                "stats": stats,
                "updated_at": now(),
            }
        },
        upsert=True,
    )
    return stats


__all__ = ["compute_stats", "effective_field", "recompute_form", "spearman"]
