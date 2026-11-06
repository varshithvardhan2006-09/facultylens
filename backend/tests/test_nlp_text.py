"""Preprocessing, PII redaction and scoring rules: no models needed."""

import pytest

from app.nlp import pii, preprocess, scoring


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("  Sooo   good!!!  ", "So good!"),
        ("Very goooood teacher", "Very good teacher"),
        ("It’s “fine”", 'It\'s "fine"'),
        ("line one\n\n  line two", "line one\nline two"),
        ("Wait....", "Wait..."),
        ("", ""),
    ],
)
def test_normalise(raw, clean):
    assert preprocess.normalise(raw) == clean


def test_contractions_for_baseline_only():
    assert preprocess.expand_contractions("Can't explain, won't stop, it's late") == (
        "cannot explain, will not stop, it is late"
    )


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("The teacher explains every concept clearly.", "en"),
        ("Good", "en"),
        ("sir chala baga cheptaru kani konchem fast ga untundi class lo", "low_confidence"),
        ("సార్ బాగా చెప్తారు", "non_english"),
    ],
)
def test_language_flags(text, lang):
    assert preprocess.detect_language(text) == lang


def test_sentence_spans_point_at_the_text():
    text = "Clear teaching. Too fast at times!\nPlease slow down"
    spans = preprocess.split_sentences(text)
    assert [text[s:e] for s, e in spans] == [
        "Clear teaching.",
        "Too fast at times!",
        "Please slow down",
    ]


def test_pii_teacher_name_other_names_and_numbers():
    text = (
        "Dr. Kavitha Reddy explains well but Ravi Kumar disturbs. Call 98480 12345 or "
        "+91-9876543210, mail me at abc.d@gmail.com, see www.example.com. I am 2451-24-751-999. "
        "Taught here 2016 - 2020."
    )
    ravi = text.index("Ravi Kumar")
    persons = [(0, 17), (ravi, ravi + len("Ravi Kumar"))]  # what spaCy would return
    spans = pii.find_spans(text, persons, ["Dr. Kavitha Reddy"])
    redacted, counts = pii.redact(text, spans)
    assert redacted.startswith("[FACULTY] explains well but [NAME] disturbs.")
    assert "Call [PHONE] or [PHONE]" in redacted
    assert "[EMAIL]" in redacted and "see [URL]." in redacted and "I am [ROLL]." in redacted
    assert "2016 - 2020" in redacted  # a year range is not a phone number
    assert counts == {"FACULTY": 1, "NAME": 1, "PHONE": 2, "EMAIL": 1, "URL": 1, "ROLL": 1}
    assert "Kavitha" not in redacted and "9876543210" not in redacted


def test_teacher_name_caught_without_ner():
    redacted, counts = pii.redact(
        "Reddy mam is very kind.",
        pii.find_spans("Reddy mam is very kind.", [], ["Dr. Kavitha Reddy"]),
    )
    assert redacted == "[FACULTY] mam is very kind." and counts == {"FACULTY": 1}


def test_toxicity_ignores_identity_mentions():
    probs = {"toxicity": 0.2, "insult": 0.81, "muslim": 0.99, "male": 0.97}
    assert scoring.toxicity_score(probs) == (0.81, "insult")


@pytest.mark.parametrize(
    ("score", "status"), [(0.9, "hidden"), (0.7, "hidden"), (0.55, "review"), (0.1, "visible")]
)
def test_moderation_thresholds(score, status):
    assert scoring.moderation_status(score) == status


def test_sentiment_and_sarcasm_rules():
    probs = {"negative": 0.1, "neutral": 0.2, "positive": 0.7}
    assert scoring.sentiment_label(probs) == "positive"
    assert scoring.polarity_value(probs) == 0.6
    assert scoring.sarcasm_flag(0.97, "positive") is True
    assert scoring.sarcasm_flag(0.9, "positive") is False  # tweet-trained model: calibrated at 0.95
    assert scoring.sarcasm_flag(0.97, "negative") is False
    assert scoring.sarcasm_flag(0.5, "positive") is False
    mean = scoring.weighted_mean([probs, {"negative": 1.0}], [3, 1])
    assert mean == {"negative": 0.325, "neutral": 0.15, "positive": 0.525}
