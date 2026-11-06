"""Turning raw model probabilities into the decisions SPEC §5 asks for: moderation status,
sentiment labels, sarcasm flags. Pure functions, so thresholds are unit-tested without models."""

from typing import Literal

from app.config import get_settings

# unitary/unbiased-toxic-roberta: these are harm categories. Its other labels only say which
# identity group a sentence mentions (male, muslim, ...), which is not harm, so they're ignored.
HARM_LABELS = (
    "toxicity",
    "severe_toxicity",
    "obscene",
    "identity_attack",
    "insult",
    "threat",
    "sexual_explicit",
)
Status = Literal["visible", "review", "hidden"]


def toxicity_score(probs: dict[str, float]) -> tuple[float, str]:
    label = max(HARM_LABELS, key=lambda k: probs.get(k, 0.0))
    return round(probs.get(label, 0.0), 4), label


def moderation_status(max_score: float) -> Status:
    s = get_settings()
    if max_score >= s.tox_hide:
        return "hidden"
    if max_score >= s.tox_review:
        return "review"
    return "visible"


def sentiment_label(probs: dict[str, float]) -> str:
    return max(("negative", "neutral", "positive"), key=lambda k: probs.get(k, 0.0))


def sarcasm_flag(irony: float, sentiment: str) -> bool:
    """SPEC §5 step 8: a positive-sounding answer the irony model thinks is ironic."""
    return irony >= get_settings().sarc_flag and sentiment == "positive"


def weighted_mean(probs_list: list[dict[str, float]], weights: list[float]) -> dict[str, float]:
    total = sum(weights) or 1.0
    keys = ("negative", "neutral", "positive")
    return {
        k: round(
            sum(p.get(k, 0.0) * w for p, w in zip(probs_list, weights, strict=True)) / total, 4
        )
        for k in keys
    }
