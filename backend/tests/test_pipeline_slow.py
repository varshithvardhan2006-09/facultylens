"""The whole analysis pipeline on real models (pytest -m slow), on seed-style answers."""

import pytest

from app.nlp.analyze import analyze_batch

pytestmark = pytest.mark.slow


def _item(i, texts, kind="teaching"):
    return {
        "response_id": f"r{i}",
        "form_id": "f1",
        "type": kind,
        "texts": texts,
        "faculty_names": ["Dr. Kavitha Reddy"],
        "is_synthetic": True,
    }


def test_pipeline_end_to_end_on_real_models():
    docs = analyze_batch(
        [
            _item(0, {"other": "This teacher is useless and a total waste of time."}),
            _item(1, {"other": "Kavitha madam, my number is 98480 12345, please share notes."}),
            _item(2, {"other": "Wow, another class of reading slides aloud. Very helpful."}),
            _item(3, {"improve": "The pace is too fast to follow."}),
            _item(4, {"liked": "Excellent teacher, I really enjoyed every class."}),
            _item(5, {"comment": "More lab hours would help."}, kind="curriculum"),
        ]
    )
    fields = {d["response_id"]: d["fields"][0] for d in docs}

    assert fields["r0"]["moderation_status"] == "hidden"
    assert docs[0]["moderation_status"] == "hidden"

    redacted = fields["r1"]["redacted"]
    assert "98480" not in redacted and "[PHONE]" in redacted and "[FACULTY]" in redacted
    assert fields["r1"]["pii_found"]["PHONE"] == 1

    assert fields["r2"]["sentiment_uncertain"] is True  # positive words, sarcastic

    pace = [a for s in fields["r3"]["sentences"] for a in s["aspects"] if a["key"] == "pace"]
    assert pace and pace[0]["polarity"] == "negative"

    assert fields["r4"]["sentiment"]["label"] == "positive"
    assert fields["r4"]["moderation_status"] == "visible"
    assert all(not s["aspects"] for s in fields["r5"]["sentences"])  # no aspects on syllabus


def test_fallback_digest_on_real_summariser():
    from app.nlp import summarize

    pool = [
        {"id": f"a{i}:liked:0", "text": t, "polarity": p, "uncertain": False, "aspect": "clarity"}
        for i, (t, p) in enumerate(
            [
                ("Explains every concept clearly with board work.", "positive"),
                ("Gives real-world examples from industry.", "positive"),
                ("Always answers our doubts after class.", "positive"),
                ("The pace is too fast to follow.", "negative"),
                ("The syllabus was rushed in the last week.", "negative"),
            ]
        )
    ]
    text = summarize.digest(pool)
    assert text and 20 < len(text) < 800
