"""Inter-annotator agreement and gold labels for the evaluation set (SPEC §8.2).

Pure functions over label documents, shared by the labelling API (live progress) and
`ml.evaluate` (the reported numbers), so both always agree.

A label: {item_id, annotator_id, sentiment, aspects: [{key, polarity}], sarcastic, skipped, at}.
Each item is labelled blind by two annotators; the first two (by time) form its pair.
Gold for an item = the adjudicator's decision if there is one, else the pair's label when the
two agree on sentiment and on every aspect with its polarity.
"""

from collections import defaultdict
from typing import Any

from app.feedback_spec import ASPECT_KEYS

SENTIMENTS = ("negative", "neutral", "positive")
MIN_PAIRS_FOR_KAPPA = 30


def aspect_map(label: dict[str, Any]) -> dict[str, str]:
    return {a["key"]: a["polarity"] for a in label.get("aspects") or []}


def pairs(labels: list[dict[str, Any]]) -> dict[Any, tuple[dict, dict]]:
    """item_id -> the first two non-skipped labels from different annotators."""
    by_item: dict[Any, list[dict]] = defaultdict(list)
    for label in sorted(labels, key=lambda x: x["at"]):
        if label.get("skipped"):
            continue
        group = by_item[label["item_id"]]
        if len(group) < 2 and all(g["annotator_id"] != label["annotator_id"] for g in group):
            group.append(label)
    return {item: (group[0], group[1]) for item, group in by_item.items() if len(group) == 2}


def agrees(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a["sentiment"] == b["sentiment"] and aspect_map(a) == aspect_map(b)


def kappa(first: list, second: list) -> float | None:
    """Cohen's kappa; None when undefined (fewer than 2 items, or one category throughout)."""
    if len(first) < 2:
        return None
    from sklearn.metrics import cohen_kappa_score

    if len(set(first) | set(second)) < 2:
        return None
    value = cohen_kappa_score(first, second)
    return None if value != value else round(float(value), 3)  # NaN -> None


def agreement(labels: list[dict[str, Any]]) -> dict[str, Any]:
    """Kappa per task over the paired items: sentiment, aspect presence, aspect polarity."""
    paired = list(pairs(labels).values())
    out: dict[str, Any] = {"pairs": len(paired), "min_pairs": MIN_PAIRS_FOR_KAPPA}
    if len(paired) < MIN_PAIRS_FOR_KAPPA:
        out["status"] = "pending"
        return out
    out["status"] = "ok"
    out["sentiment"] = kappa(
        [a["sentiment"] for a, _ in paired], [b["sentiment"] for _, b in paired]
    )
    out["raw_agreement"] = round(sum(agrees(a, b) for a, b in paired) / len(paired), 3)

    presence: dict[str, dict[str, Any]] = {}
    polarity_a, polarity_b = [], []
    for key in ASPECT_KEYS:
        first = [key in aspect_map(a) for a, _ in paired]
        second = [key in aspect_map(b) for _, b in paired]
        presence[key] = {"kappa": kappa(first, second), "marked": sum(first) + sum(second)}
        for a, b in paired:
            pa, pb = aspect_map(a).get(key), aspect_map(b).get(key)
            if pa and pb:
                polarity_a.append(pa)
                polarity_b.append(pb)
    out["aspect_presence"] = presence
    out["aspect_polarity"] = {
        "kappa": kappa(polarity_a, polarity_b),
        "items": len(polarity_a),
    }
    return out


def gold(
    labels: list[dict[str, Any]], adjudications: list[dict[str, Any]]
) -> dict[Any, dict[str, Any]]:
    """item_id -> {sentiment, aspects, how}, for agreed or adjudicated items only."""
    out: dict[Any, dict[str, Any]] = {}
    for item, (a, b) in pairs(labels).items():
        if agrees(a, b):
            out[item] = {"sentiment": a["sentiment"], "aspects": aspect_map(a), "how": "agreed"}
    for adj in adjudications:
        out[adj["item_id"]] = {
            "sentiment": adj["sentiment"],
            "aspects": aspect_map(adj),
            "how": "adjudicated",
        }
    return out


def disagreements(
    labels: list[dict[str, Any]], adjudications: list[dict[str, Any]]
) -> list[tuple[Any, dict, dict]]:
    done = {adj["item_id"] for adj in adjudications}
    return [
        (item, a, b)
        for item, (a, b) in pairs(labels).items()
        if item not in done and not agrees(a, b)
    ]
