"""Aggregate arithmetic on a hand-made set where every number can be checked by eye."""

from app.feedback_spec import ASPECT_KEYS
from app.pipeline.aggregate import compute_stats, effective_field, spearman


def field(name, label, sentences=(), status="visible", uncertain=False, decision=None, text=None):
    f = {
        "field": name,
        "redacted": text or " ".join(s[0] for s in sentences) or "ok",
        "language": "en",
        "moderation_status": status,
        "sentiment": {"label": label, "probs": {label: 0.9}},
        "emotion": {"joy": 1.0} if label == "positive" else {"anger": 1.0},
        "sentiment_uncertain": uncertain,
        "sentences": [
            {
                "text": t,
                "start": 0,
                "end": len(t),
                "aspects": [{"key": k, "polarity": p, "conf": c}],
            }
            for t, k, p, c in sentences
        ],
    }
    if decision:
        f["moderation"] = {"decision": decision, "text": "edited by admin"}
    return f


def row(i, ratings, fields, overall):
    return {
        "response": {"_id": i, "likert": {k: ratings.get(k, 3) for k in ASPECT_KEYS}},
        "analysis": {
            "_id": f"a{i}",
            "fields": fields,
            "overall_sentiment": {"label": overall} if overall else None,
        },
    }


def test_compute_stats_teaching():
    rows = [
        row(
            1,
            {"pace": 2},
            [field("improve", "negative", [("Too fast.", "pace", "negative", 0.9)])],
            "negative",
        ),
        row(
            2,
            {"pace": 5},
            [field("liked", "positive", [("Good pace.", "pace", "positive", 0.8)])],
            "positive",
        ),
        row(
            3,
            {"pace": 4},
            [field("liked", "positive", [("Nice speed.", "pace", "positive", 0.7)])],
            "positive",
        ),
        # sarcastic positive counts half
        row(
            4,
            {"pace": 1},
            [
                field(
                    "other",
                    "positive",
                    [("Wow, great pace.", "pace", "positive", 0.95)],
                    uncertain=True,
                )
            ],
            "positive",
        ),
        # hidden: no evidence, no comment, counted as hidden
        row(
            5,
            {},
            [
                field(
                    "other",
                    "negative",
                    [("Useless teacher.", "behaviour", "negative", 0.9)],
                    status="hidden",
                )
            ],
            "negative",
        ),
        # not analysed yet
        {"response": {"_id": 6, "likert": {k: 3 for k in ASPECT_KEYS}}, "analysis": None},
    ]
    stats = compute_stats(rows, "teaching")
    assert stats["responses"] == 6 and stats["analysed"] == 5
    assert stats["sentiment"] == {"positive": 2.5, "neutral": 0, "negative": 2.0}
    assert stats["net_score"] == round((2.5 - 2.0) / 4.5, 3)
    assert stats["hidden_comments"] == 1 and stats["sarcasm_rate"] == 0.2

    pace = stats["aspects"]["pace"]
    assert pace["mentions"] == 4 and pace["polarity"] == {
        "positive": 3,
        "neutral": 0,
        "negative": 1,
    }
    assert pace["likert_mean"] == round((2 + 5 + 4 + 1 + 3 + 3) / 6, 3)
    assert pace["agreement"]["n"] == 4 and pace["agreement"]["rho"] is None  # fewer than 5 pairs
    # sarcastic evidence goes last
    assert [e["text"] for e in pace["evidence"]["positive"]] == [
        "Good pace.",
        "Nice speed.",
        "Wow, great pace.",
    ]
    assert pace["evidence"]["positive"][0]["id"] == "a2:liked:0"
    assert stats["aspects"]["behaviour"]["mentions"] == 0  # the hidden comment taught us nothing
    assert all("Useless" not in c["text"] for pool in stats["top_comments"].values() for c in pool)


def test_admin_decisions_override_model():
    hidden_then_approved = field(
        "other",
        "negative",
        [("Harsh but fair.", "assessment", "negative", 0.8)],
        status="hidden",
        decision="approve",
    )
    assert effective_field(hidden_then_approved) == (True, "Harsh but fair.")
    redacted = field("other", "negative", status="review", decision="redact")
    assert effective_field(redacted) == (True, "edited by admin")
    hide = field("liked", "positive", decision="hide")
    assert effective_field(hide)[0] is False


def test_spearman():
    assert spearman([1, 2, 3, 4, 5], [-1, -0.5, 0, 0.5, 1]) == 1.0
    assert spearman([1, 2, 3, 4], [1, 2, 3, 4]) is None  # n < 5
    assert spearman([3, 3, 3, 3, 3], [1, 0, -1, 0, 1]) is None  # constant ratings


def test_curriculum_stats():
    rows = [
        {
            "response": {
                "_id": i,
                "likert": {
                    "syllabus_relevance": r,
                    "outcomes_clarity": 4,
                    "lab_adequacy": 3,
                    "reference_material": 2,
                },
            },
            "analysis": {
                "_id": f"c{i}",
                "fields": [field("comment", "negative", text="More lab hours.")],
                "overall_sentiment": {"label": "negative"},
            },
        }
        for i, r in enumerate([4, 5, 3])
    ]
    stats = compute_stats(rows, "curriculum")
    assert stats["likert_means"]["syllabus_relevance"] == 4.0
    assert (
        "aspects" not in stats and stats["top_comments"]["negative"][0]["text"] == "More lab hours."
    )
