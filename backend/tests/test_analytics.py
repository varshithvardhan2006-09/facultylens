"""Analytics: combining forms, teacher rows, lexicon rates, the cluster bootstrap, thresholds."""

import numpy as np

from app.pipeline import analytics


def stats(responses=10, pos=6.0, neu=1.0, neg=3.0, likert=4.0, clarity=(8, 0, 1), pace=(1, 0, 5)):
    def aspect(p, n0, n, mean):
        return {
            "mentions": p + n0 + n,
            "polarity": {"positive": p, "neutral": n0, "negative": n},
            "likert_mean": mean,
            "agreement": {"rho": None, "n": 0},
            "evidence": {},
        }

    return {
        "responses": responses,
        "analysed": responses,
        "answers": responses * 2,
        "sentiment": {"positive": pos, "neutral": neu, "negative": neg},
        "net_score": round((pos - neg) / (pos + neu + neg), 3),
        "likert_means": {"clarity": likert, "pace": likert - 1},
        "aspects": {"clarity": aspect(*clarity, likert), "pace": aspect(*pace, likert - 1)},
        "emotion_mix": {"joy": 0.5, "neutral": 0.5},
        "sarcasm_rate": 0.1,
        "hidden_comments": 1,
        "in_review": 0,
    }


def form(responses=10, eligible=12, s=None, faculty="t1"):
    return {
        "form_id": f"f-{faculty}-{responses}",
        "faculty_id": faculty,
        "course": {"code": "CS501"},
        "responses": responses,
        "eligible": eligible,
        "stats": s,
    }


def test_form_status():
    assert analytics.form_status(form(3, s=stats()), 5) == "below_minimum"
    assert analytics.form_status(form(10, s=None), 5) == "awaiting_analysis"
    assert analytics.form_status(form(10, s=stats()), 5) == "available"


def test_combine_weights_by_responses_and_sums_counts():
    a = stats(responses=10, pos=8, neu=0, neg=2, likert=4.0)
    b = stats(responses=30, pos=5, neu=5, neg=10, likert=3.0)
    c = analytics.combine([a, b])
    assert c["responses"] == 40 and c["hidden_comments"] == 2
    assert c["sentiment"] == {"positive": 13, "neutral": 5, "negative": 12}
    assert c["net_score"] == round((13 - 12) / 30, 3)
    assert c["likert_means"]["clarity"] == 3.25  # (4*10 + 3*30) / 40
    assert c["aspects"]["pace"]["polarity"]["negative"] == 10


def test_teacher_row_uses_only_usable_forms_and_the_shared_strength_rule():
    teacher = {"_id": "t1", "name": "Dr. A"}
    row = analytics.teacher_row(teacher, [form(10, s=stats()), form(3, s=stats())], minimum=5)
    assert row["offerings"] == 2 and row["responses"] == 13 and row["status"] == "available"
    assert row["top_strength"]["aspect"] == "clarity" and row["top_gap"]["aspect"] == "pace"
    assert row["rating"] == 3.5  # mean of clarity 4.0 and pace 3.0
    too_few = analytics.teacher_row(teacher, [form(2, s=stats())], minimum=5)
    assert too_few["status"] == "below_minimum" and too_few["net_score"] is None


def test_lexicon_rates_use_word_boundaries():
    texts = [
        "A brilliant teacher.",
        "Very helpful and caring.",
        "Bring your smartphone.",  # not "smart"
        "Organized and kind, and a genius.",
        "Nothing special.",
    ]
    r = analytics.lexicon_rates(texts)
    assert r["answers"] == 5 and r["ability"] == 2 and r["warmth"] == 2
    assert r["ability_per_1000"] == 400.0


def test_teacher_gap_counts_teachers_not_responses():
    rng = np.random.default_rng(1)
    a = [list(rng.normal(4.2, 0.4, 40).clip(1, 5)) for _ in range(6)]
    b = [list(rng.normal(3.2, 0.4, 40).clip(1, 5)) for _ in range(6)]
    real = analytics.teacher_gap(a, b)
    assert real["clear"] and real["low"] > 0.5 and real["teachers"] == [6, 6]
    assert real["ratings"] == [240, 240]
    same = analytics.teacher_gap(a[:3], a[3:])
    assert same["low"] < 0 < same["high"] and not same["clear"]
    assert analytics.teacher_gap(a[:1], b) is None
    # Three teachers per group whose averages happen to differ by 0.6 with real spread
    # between teachers: hundreds of ratings each must not make that look "clear".
    spread_a = [[3.4] * 100, [4.6] * 100, [4.0] * 100]
    spread_b = [[3.0] * 100, [4.0] * 100, [3.2] * 100]
    small = analytics.teacher_gap(spread_a, spread_b)
    assert round(small["gap"], 2) == 0.6 and not small["clear"]


def _teacher(gender, n_answers=20, rating=4.0, text="Helpful teacher."):
    return {
        "gender": gender,
        "answers": [{"text": text, "emotion": {"joy": 1.0}, "uncertain": False}] * n_answers,
        "ratings": {"clarity": [rating] * n_answers},
    }


def test_bias_panel_hides_small_groups_and_counts_excluded():
    small = [_teacher("female")] * 3 + [_teacher("male")] * 2 + [_teacher(None)]
    out = analytics.bias_panel(small, min_faculty=3, min_answers=30)
    assert out["status"] == "too_small" and out["excluded_teachers"] == 1
    assert out["groups"]["male"]["teachers"] == 2
    assert "language" not in out and "rating_gaps" not in out and out["caveat"]


def test_bias_panel_reports_groups_only():
    teachers = [_teacher("female", rating=4.0)] * 3 + [
        _teacher("male", rating=3.0, text="A brilliant mind.")
    ] * 3
    out = analytics.bias_panel(teachers, min_faculty=3, min_answers=30)
    assert out["status"] == "available"
    assert out["language"]["male"]["ability_per_1000"] == 1000.0
    assert out["language"]["female"]["warmth_per_1000"] == 1000.0
    warmth = out["language"]["gap_per_1000"]["warmth"]
    assert warmth["gap"] == 1000.0 and warmth["teachers"] == [3, 3]
    assert out["rating_gaps"]["clarity"]["gap"] == 1.0
    assert out["sarcasm"]["female"]["rate"] == 0.0
    assert "name" not in str(out)
