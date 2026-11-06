"""Grounded summaries: evidence selection, the no-LLM fallback, and grounding of LLM output."""

import pytest

from app.feedback_spec import ASPECT_KEYS
from app.nlp import summarize


def ev(i, polarity, aspect, uncertain=False):
    return {
        "id": f"a{i}:liked:0",
        "text": f"{aspect} {polarity} sentence {i}.",
        "field": "liked",
        "start": 0,
        "end": 10,
        "conf": 0.9,
        "uncertain": uncertain,
    }


def aspect(pos=0, neu=0, neg=0, likert=None, start=0):
    return {
        "mentions": pos + neu + neg,
        "polarity": {"positive": pos, "neutral": neu, "negative": neg},
        "likert_mean": likert,
        "agreement": {"rho": None, "n": 0},
        "evidence": {
            "positive": [ev(start + i, "positive", "x") for i in range(min(pos, 3))],
            "neutral": [ev(start + 10 + i, "neutral", "x") for i in range(min(neu, 3))],
            "negative": [ev(start + 20 + i, "negative", "x") for i in range(min(neg, 3))],
        },
    }


@pytest.fixture
def stats():
    aspects = {k: aspect(start=100 * n) for n, k in enumerate(ASPECT_KEYS)}
    aspects["clarity"] = aspect(pos=30, neg=2, likert=4.4, start=1000)
    aspects["knowledge"] = aspect(pos=12, neg=1, likert=4.1, start=2000)
    aspects["pace"] = aspect(pos=1, neg=9, likert=2.6, start=3000)
    aspects["practical"] = aspect(pos=1, neg=1, likert=3.0, start=4000)  # too few to call
    aspects["assessment"] = aspect(pos=5, neg=3, likert=2.5, start=5000)  # low rating
    return {
        "responses": 40,
        "analysed": 40,
        "sentiment": {"positive": 25.0, "neutral": 5.0, "negative": 10.0},
        "aspects": aspects,
    }


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    monkeypatch.setattr(summarize, "digest", lambda pool: "A short digest.")


def test_evidence_pool_is_capped_balanced_and_sarcasm_last():
    many = {k: aspect(pos=3, neu=3, neg=3, start=100 * n) for n, k in enumerate(ASPECT_KEYS)}
    for item in many["clarity"]["evidence"]["positive"]:
        item["uncertain"] = True
    pool = summarize.evidence_pool({"aspects": many})
    assert len(pool) == summarize.MAX_EVIDENCE
    assert {e["aspect"] for e in pool} == set(ASPECT_KEYS)
    flags = [e["uncertain"] for e in pool]
    assert any(flags) and flags == sorted(flags)  # sarcastic sentences last
    assert len({e["id"] for e in pool}) == len(pool)


def test_fallback_ranks_strengths_and_improvements(stats):
    out = summarize.summarise(stats)
    assert out["engine"] == "fallback"
    assert [s["aspect"] for s in out["strengths"]] == ["clarity", "knowledge"]
    # clarity is criticised twice but praised far more: a strength, never also a gap;
    # assessment is praised more than criticised but rated below 3, so it is a gap.
    assert [i["aspect"] for i in out["improvements"]] == ["pace", "assessment"]
    pace = out["improvements"][0]
    assert "9 negative mentions" in pace["text"] and "2.6 out of 5" in pace["text"]
    assert pace["suggested_action"] and pace["evidence_ids"] == [
        e["id"] for e in stats["aspects"]["pace"]["evidence"]["negative"]
    ]
    assert out["overall_summary"].startswith("40 students responded; 62% ")
    assert out["digest"] == "A short digest."


def test_llm_items_without_real_evidence_are_dropped(stats, monkeypatch):
    real = stats["aspects"]["clarity"]["evidence"]["positive"][0]["id"]

    def fake(system, user, schema):
        assert real in user and "useless" not in user
        return schema.model_validate(
            {
                "strengths": [
                    {"text": "Invented.", "aspect": "clarity", "evidence_ids": ["made:up:2"]},
                    {"text": "Clear.", "aspect": "clarity", "evidence_ids": [real, "made:up:1"]},
                    {"text": "Odd aspect.", "aspect": "charisma", "evidence_ids": [real]},
                ],
                "improvements": [],
                "overall_summary": "Students value clear teaching.",
            }
        ), {"engine": "groq:openai/gpt-oss-120b"}

    monkeypatch.setattr(summarize.llm, "complete_json", fake)
    out = summarize.summarise(stats)
    assert out["engine"] == "groq:openai/gpt-oss-120b"
    # The LLM's clarity item is kept; knowledge and both gaps, which it skipped, come from the
    # template, so the summary still covers exactly what the counts chose.
    assert out["strengths"][0] == {"text": "Clear.", "aspect": "clarity", "evidence_ids": [real]}
    assert [s["aspect"] for s in out["strengths"]] == ["clarity", "knowledge"]
    assert [i["aspect"] for i in out["improvements"]] == ["pace", "assessment"]
    assert out["dropped_ungrounded"] == 2 and out["filled_from_template"] == 3
    assert out["digest"] is None


def test_llm_cannot_turn_a_concern_into_a_strength(stats, monkeypatch):
    """The bug seen live: the LLM praised punctuality although most students criticised it."""
    pace_praise = stats["aspects"]["pace"]["evidence"]["positive"][0]["id"]
    pace_criticism = stats["aspects"]["pace"]["evidence"]["negative"][0]["id"]
    knowledge = stats["aspects"]["knowledge"]["evidence"]["positive"][0]["id"]
    clarity = stats["aspects"]["clarity"]["evidence"]["positive"][0]["id"]
    seen = {}

    def fake(system, user, schema):
        seen["prompt"] = user
        return schema.model_validate(
            {
                "strengths": [
                    # a concern dressed up as a strength, citing the one student who liked it
                    {"text": "Great pace.", "aspect": "pace", "evidence_ids": [pace_praise]},
                    # the right aspect, but citing another aspect's sentence
                    {"text": "Clear.", "aspect": "clarity", "evidence_ids": [knowledge]},
                    {"text": "Knows it.", "aspect": "knowledge", "evidence_ids": [knowledge]},
                    {"text": "Clear again.", "aspect": "clarity", "evidence_ids": [clarity]},
                ],
                "improvements": [
                    {
                        "text": "Too fast.",
                        "aspect": "pace",
                        "evidence_ids": [pace_criticism, pace_praise],
                        "suggested_action": "Slow down.",
                    }
                ],
                "overall_summary": "Clear and knowledgeable; the pace worries students.",
            }
        ), {"engine": "groq:m"}

    monkeypatch.setattr(summarize.llm, "complete_json", fake)
    out = summarize.summarise(stats)
    # The LLM only ever saw pace as an area to improve, with its critical sentences.
    assert pace_praise not in seen["prompt"] and pace_criticism in seen["prompt"]
    assert [s["aspect"] for s in out["strengths"]] == ["clarity", "knowledge"]
    assert [s["text"] for s in out["strengths"]] == ["Clear again.", "Knows it."]
    pace = out["improvements"][0]
    assert pace["aspect"] == "pace" and pace["evidence_ids"] == [pace_criticism]
    assert pace["suggested_action"] == "Slow down."
    assert out["dropped_ungrounded"] == 2


def test_llm_with_nothing_grounded_falls_back(stats, monkeypatch):
    def fake(system, user, schema):
        return schema.model_validate(
            {"strengths": [{"text": "x y z", "aspect": "clarity", "evidence_ids": ["no"]}]}
        ), {"engine": "groq:m"}

    monkeypatch.setattr(summarize.llm, "complete_json", fake)
    assert summarize.summarise(stats)["engine"] == "fallback"


def test_no_evidence_means_no_items():
    out = summarize.summarise({"responses": 6, "analysed": 6, "sentiment": {}, "aspects": {}})
    assert out["strengths"] == [] and out["improvements"] == []
    assert out["overall_summary"] == "6 students responded."
