"""Department and faculty analytics and the bias & sarcasm panel (SPEC §11.5, §11.7).

Pure functions over data the router has already loaded: stored aggregates, summaries and
visible, redacted answers. Nothing here touches the database or runs a model, and nothing
here ever returns a teacher's gender next to their name; the bias panel works on groups only.
"""

import re
from typing import Any

import numpy as np

from app.feedback_spec import ABILITY_WORDS, ASPECT_KEYS, ASPECT_LABELS, WARMTH_WORDS
from app.nlp.summarize import choose_aspects

GROUPS = ("female", "male")

CAVEAT = (
    "This panel looks for possible bias in students' evaluations, not in the teachers. "
    "Differences between groups can come from the subjects, sections and years taught, or from "
    "chance; with only a few teachers per group, wide intervals are expected. Use it to ask "
    "questions about the feedback process, never to judge an individual."
)


# --------------------------------------------------------------------------- one form / teacher


def form_status(form: dict[str, Any], minimum: int) -> str:
    if form["responses"] < minimum:
        return "below_minimum"
    if not (form.get("stats") or {}).get("analysed"):
        return "awaiting_analysis"
    return "available"


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def overall_rating(likert_means: dict[str, float] | None) -> float | None:
    values = [v for v in (likert_means or {}).values() if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def _weighted(pairs: list[tuple[float | None, float]]) -> float | None:
    pairs = [(v, w) for v, w in pairs if v is not None and w > 0]
    total = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / total, 3) if total else None


def combine(stats_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Several forms' aggregates as one: counts summed, means weighted by their own n."""
    sentiment = {
        k: round(sum((s.get("sentiment") or {}).get(k, 0) for s in stats_list), 2)
        for k in ("positive", "neutral", "negative")
    }
    total = sum(sentiment.values())
    keys = sorted({k for s in stats_list for k in (s.get("likert_means") or {})})
    emotions = sorted({k for s in stats_list for k in (s.get("emotion_mix") or {})})
    aspects = {}
    for key in ASPECT_KEYS:
        parts = [(s.get("aspects") or {}).get(key) for s in stats_list]
        parts = [(p, s) for p, s in zip(parts, stats_list, strict=True) if p]
        if not parts:
            continue
        polarity = {
            p: sum(a["polarity"][p] for a, _ in parts) for p in ("positive", "neutral", "negative")
        }
        aspects[key] = {
            "label": ASPECT_LABELS[key],
            "mentions": sum(polarity.values()),
            "polarity": polarity,
            "likert_mean": _weighted([(a.get("likert_mean"), s["responses"]) for a, s in parts]),
            "evidence": {},
        }
    return {
        "responses": sum(s.get("responses", 0) for s in stats_list),
        "analysed": sum(s.get("analysed", 0) for s in stats_list),
        "answers": sum(s.get("answers", 0) for s in stats_list),
        "sentiment": sentiment,
        "net_score": round((sentiment["positive"] - sentiment["negative"]) / total, 3)
        if total
        else None,
        "likert_means": {
            k: _weighted(
                [((s.get("likert_means") or {}).get(k), s["responses"]) for s in stats_list]
            )
            for k in keys
        },
        "aspects": aspects,
        "emotion_mix": {
            e: _weighted(
                [((s.get("emotion_mix") or {}).get(e), s.get("answers", 0)) for s in stats_list]
            )
            for e in emotions
        },
        "sarcasm_rate": _weighted(
            [(s.get("sarcasm_rate"), s.get("answers", 0)) for s in stats_list]
        ),
        "hidden_comments": sum(s.get("hidden_comments", 0) for s in stats_list),
        "in_review": sum(s.get("in_review", 0) for s in stats_list),
    }


def _top(stats: dict[str, Any]) -> tuple[dict | None, dict | None]:
    strengths, gaps = choose_aspects(stats, need_evidence=False)
    pick = lambda rows: {"aspect": rows[0]["aspect"], "label": rows[0]["label"]} if rows else None
    return pick(strengths), pick(gaps)


def offering_row(form: dict[str, Any], minimum: int) -> dict[str, Any]:
    """One teaching offering for the 'across your courses' table."""
    status = form_status(form, minimum)
    row = {
        "form_id": str(form["form_id"]),
        "course": form["course"],
        "responses": form["responses"],
        "eligible": form["eligible"],
        "status": status,
        "net_score": None,
        "rating": None,
        "top_strength": None,
        "top_gap": None,
        "sarcasm_rate": None,
    }
    if status == "available":
        stats = form["stats"]
        strength, gap = _top(stats)
        row.update(
            net_score=stats.get("net_score"),
            rating=overall_rating(stats.get("likert_means")),
            top_strength=strength,
            top_gap=gap,
            sarcasm_rate=stats.get("sarcasm_rate"),
        )
    return row


def teacher_row(
    teacher: dict[str, Any], forms: list[dict[str, Any]], minimum: int
) -> dict[str, Any]:
    """A teacher's offerings in one cycle, combined over the ones with enough analysed data."""
    usable = [f for f in forms if form_status(f, minimum) == "available"]
    row = {
        "id": str(teacher["_id"]),
        "name": teacher["name"],
        "offerings": len(forms),
        "responses": sum(f["responses"] for f in forms),
        "eligible": sum(f["eligible"] for f in forms),
        "status": "available"
        if usable
        else (
            "awaiting_analysis"
            if any(form_status(f, minimum) == "awaiting_analysis" for f in forms)
            else "below_minimum"
        ),
        "net_score": None,
        "rating": None,
        "top_strength": None,
        "top_gap": None,
        "sarcasm_rate": None,
    }
    if usable:
        stats = combine([f["stats"] for f in usable])
        strength, gap = _top(stats)
        row.update(
            net_score=stats["net_score"],
            rating=overall_rating(stats["likert_means"]),
            top_strength=strength,
            top_gap=gap,
            sarcasm_rate=stats["sarcasm_rate"],
        )
    return row


def department_view(
    teachers: list[dict[str, Any]], forms_by_teacher: dict[Any, list[dict[str, Any]]], minimum: int
) -> dict[str, Any]:
    rows = [teacher_row(t, forms_by_teacher.get(t["_id"], []), minimum) for t in teachers]
    usable = [
        f["stats"]
        for forms in forms_by_teacher.values()
        for f in forms
        if form_status(f, minimum) == "available"
    ]
    combined = combine(usable) if usable else None
    all_forms = [f for forms in forms_by_teacher.values() for f in forms]
    return {
        "teachers": sorted(rows, key=lambda r: r["name"]),
        "totals": {
            "teachers": len(rows),
            "offerings": len(all_forms),
            "responses": sum(f["responses"] for f in all_forms),
            "eligible": sum(f["eligible"] for f in all_forms),
            "net_score": combined["net_score"] if combined else None,
            "hidden_comments": combined["hidden_comments"] if combined else 0,
            "in_review": combined["in_review"] if combined else 0,
            "forms_shown": len(usable),
        },
        "aspects": (combined or {}).get("aspects", {}),
        "likert_means": (combined or {}).get("likert_means", {}),
    }


# --------------------------------------------------------------------------- bias panel


def _pattern(words: list[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


ABILITY_RE = _pattern(ABILITY_WORDS)
WARMTH_RE = _pattern(WARMTH_WORDS)


def lexicon_rates(texts: list[str]) -> dict[str, Any]:
    """Answers that use at least one ability / warmth word, per 1,000 answers."""
    n = len(texts)
    ability = sum(bool(ABILITY_RE.search(t)) for t in texts)
    warmth = sum(bool(WARMTH_RE.search(t)) for t in texts)
    per = lambda c: round(1000 * c / n, 1) if n else None
    return {
        "answers": n,
        "ability": ability,
        "warmth": warmth,
        "ability_per_1000": per(ability),
        "warmth_per_1000": per(warmth),
    }


def teacher_gap(group_a: list[list[float]], group_b: list[list[float]]) -> dict[str, Any] | None:
    """Mean of A's teacher averages minus B's, with a 95% Welch t-interval over teachers.

    Each inner list is one teacher's ratings. Ratings of one teacher are not independent, so
    each teacher counts once (their average), and the small-sample t value keeps the interval
    honest when a group has only a few teachers. (A bootstrap over 3 teachers has only 10
    distinct resamples and gives intervals that are too narrow; it was tried and dropped.)
    """
    a = np.array([np.mean(x) for x in group_a if len(x)], dtype=float)
    b = np.array([np.mean(x) for x in group_b if len(x)], dtype=float)
    if len(a) < 2 or len(b) < 2:
        return None
    from scipy import stats

    gap = float(a.mean() - b.mean())
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = float(np.sqrt(va + vb))
    if se == 0:
        low = high = gap
    else:
        df = (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
        half = float(stats.t.ppf(0.975, df)) * se
        low, high = gap - half, gap + half
    return {
        "gap": round(gap, 3),
        "low": round(low, 3),
        "high": round(high, 3),
        "clear": bool(low > 0 or high < 0),
        "teachers": [len(a), len(b)],
        "ratings": [int(sum(len(x) for x in group_a)), int(sum(len(x) for x in group_b))],
    }


def bias_panel(
    teachers: list[dict[str, Any]], min_faculty: int, min_answers: int
) -> dict[str, Any]:
    """teachers: [{gender, answers: [{text, emotion, uncertain}], ratings: {aspect: [1-5]}}].

    Only "female" and "male" form groups; anyone else is left out and counted. Below the
    thresholds the result carries group sizes and nothing else.
    """
    grouped = {g: [t for t in teachers if t.get("gender") == g] for g in GROUPS}
    excluded = sum(t.get("gender") not in GROUPS for t in teachers)
    sizes = {
        g: {
            "teachers": len(grouped[g]),
            "answers": sum(len(t["answers"]) for t in grouped[g]),
        }
        for g in GROUPS
    }
    base = {
        "caveat": CAVEAT,
        "groups": sizes,
        "excluded_teachers": excluded,
        "needed": {"teachers": min_faculty, "answers": min_answers},
        "lexicons": {"ability": ABILITY_WORDS, "warmth": WARMTH_WORDS},
    }
    if any(sizes[g]["teachers"] < min_faculty or sizes[g]["answers"] < min_answers for g in GROUPS):
        return {**base, "status": "too_small"}

    language: dict[str, Any] = {
        g: lexicon_rates([a["text"] for t in grouped[g] for a in t["answers"]]) for g in GROUPS
    }
    # The same teacher-level interval for the word rates: each teacher's own rate counts once.
    language["gap_per_1000"] = {}
    for name, pattern in (("ability", ABILITY_RE), ("warmth", WARMTH_RE)):
        result = teacher_gap(
            *[
                [[float(bool(pattern.search(a["text"]))) for a in t["answers"]] for t in grouped[g]]
                for g in GROUPS
            ]
        )
        if result:
            language["gap_per_1000"][name] = {
                **result,
                **{k: round(1000 * result[k], 1) for k in ("gap", "low", "high")},
            }
    gaps = {}
    for key in ASPECT_KEYS:
        result = teacher_gap(
            [t["ratings"].get(key, []) for t in grouped["female"]],
            [t["ratings"].get(key, []) for t in grouped["male"]],
        )
        if result:
            gaps[key] = {"label": ASPECT_LABELS[key], **result}
    emotions = sorted({e for t in teachers for a in t["answers"] for e in (a.get("emotion") or {})})
    emotion_mix = {
        g: {
            e: _mean(
                [(a.get("emotion") or {}).get(e, 0.0) for t in grouped[g] for a in t["answers"]]
            )
            for e in emotions
        }
        for g in GROUPS
    }
    sarcasm = {
        g: {
            "flagged": sum(a["uncertain"] for t in grouped[g] for a in t["answers"]),
            "answers": sizes[g]["answers"],
            "rate": round(
                sum(a["uncertain"] for t in grouped[g] for a in t["answers"])
                / max(sizes[g]["answers"], 1),
                3,
            ),
        }
        for g in GROUPS
    }
    return {
        **base,
        "status": "available",
        "language": language,
        "rating_gaps": gaps,
        "emotion_mix": emotion_mix,
        "sarcasm": sarcasm,
    }
