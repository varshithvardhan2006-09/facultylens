"""The full per-response analysis (SPEC §5), run on batches so each model is called once per
batch. Every model after PII redaction sees only redacted text.

Input item: {response_id, form_id, type, texts: {field: str|None}, faculty_names: [str]}
Output: one `analyses` document per item (see SPEC §9), keyed by response_id + model_version.
"""

from typing import Any

from app.nlp import aspects, pii, preprocess, registry, scoring
from app.utils import now

EMOTIONS = ("anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise")


def _round(probs: dict[str, float], keys=None) -> dict[str, float]:
    return {k: round(v, 4) for k, v in probs.items() if keys is None or k in keys}


def _predict(task: str, texts: list[str]) -> list[dict[str, float]]:
    """Run a model only when there is text: a ratings-only response must not load anything."""
    return registry.get(task).predict(texts) if texts else []


def analyze_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    version = registry.model_version()

    # 1-2. Normalise, flag language, redact (one spaCy pass for the batch).
    fields: list[dict[str, Any]] = []  # flat list of every non-empty answer in the batch
    for index, item in enumerate(items):
        for name, raw in (item.get("texts") or {}).items():
            text = preprocess.normalise(raw)
            if text:
                fields.append({"item": index, "field": name, "text": text, "kind": item["type"]})
    redacted = pii.redact_batch(
        [f["text"] for f in fields], [items[f["item"]].get("faculty_names", []) for f in fields]
    )
    sentences: list[dict[str, Any]] = []
    for f, (text, found) in zip(fields, redacted, strict=True):
        f["redacted"] = text
        f["pii_found"] = found
        f["language"] = preprocess.detect_language(text)
        f["sentences"] = []
        for start, end in preprocess.split_sentences(text):
            sentence = {"field": f, "text": text[start:end], "start": start, "end": end}
            f["sentences"].append(sentence)
            sentences.append(sentence)

    field_texts = [f["redacted"] for f in fields]
    sentence_texts = [s["text"] for s in sentences]

    # 3. Moderation on each sentence.
    for s, probs in zip(sentences, _predict("toxicity", sentence_texts), strict=True):
        s["toxicity"] = scoring.toxicity_score(probs)

    # 4. Sentiment for whole answers and for each sentence (one call).
    sentiment = _predict("sentiment", field_texts + sentence_texts)
    for f, probs in zip(fields, sentiment[: len(fields)], strict=True):
        f["sentiment"] = _round(probs)
    for s, probs in zip(sentences, sentiment[len(fields) :], strict=True):
        s["sentiment"] = _round(probs)

    # 5-6. Aspects and their polarity, teaching answers only.
    teaching = [s for s in sentences if s["field"]["kind"] == "teaching"]
    found = aspects.detect([s["text"] for s in teaching])
    pairs = []
    for s, hits in zip(teaching, found, strict=True):
        s["aspects"] = [{"key": key, "sim": sim, "via": via} for key, sim, via in hits]
        pairs += [(s, a) for a in s["aspects"]]
    if pairs:
        polarity = registry.get("absa").predict(
            [s["text"] for s, _ in pairs], [aspects.ASPECT_TERMS[a["key"]] for _, a in pairs]
        )
        for (_, aspect), probs in zip(pairs, polarity, strict=True):
            label = max(probs, key=probs.get)
            aspect["polarity"] = label
            aspect["conf"] = round(probs[label], 4)

    # 7-8. Emotion and irony per answer.
    for f, probs in zip(fields, _predict("emotion", field_texts), strict=True):
        f["emotion"] = _round(probs, EMOTIONS)
    for f, probs in zip(fields, _predict("irony", field_texts), strict=True):
        f["irony"] = round(probs.get("irony", 0.0), 4)

    # Assemble one document per response.
    docs = []
    for index, item in enumerate(items):
        mine = [f for f in fields if f["item"] == index]
        out_fields = []
        for f in mine:
            score, label = max((s["toxicity"] for s in f["sentences"]), default=(0.0, "toxicity"))
            sent_label = scoring.sentiment_label(f["sentiment"])
            out_fields.append(
                {
                    "field": f["field"],
                    "redacted": f["redacted"],
                    "language": f["language"],
                    "pii_found": f["pii_found"],
                    "toxicity": {"max": score, "label": label},
                    "moderation_status": scoring.moderation_status(score),
                    "sentiment": {"label": sent_label, "probs": f["sentiment"]},
                    "emotion": f["emotion"],
                    "irony": f["irony"],
                    "sentiment_uncertain": scoring.sarcasm_flag(f["irony"], sent_label),
                    "sentences": [
                        {
                            "text": s["text"],
                            "start": s["start"],
                            "end": s["end"],
                            "sentiment": scoring.sentiment_label(s["sentiment"]),
                            "toxicity": s["toxicity"][0],
                            "aspects": s.get("aspects", []),
                        }
                        for s in f["sentences"]
                    ],
                }
            )
        statuses = [f["moderation_status"] for f in out_fields]
        overall = (
            scoring.weighted_mean(
                [f["sentiment"]["probs"] for f in out_fields],
                [len(f["redacted"]) for f in out_fields],
            )
            if out_fields
            else None
        )
        docs.append(
            {
                "response_id": item["response_id"],
                "form_id": item["form_id"],
                "type": item["type"],
                "model_version": version,
                "fields": out_fields,
                "overall_sentiment": {
                    "label": scoring.sentiment_label(overall),
                    "probs": overall,
                }
                if overall
                else None,
                "moderation_status": "hidden"
                if "hidden" in statuses
                else "review"
                if "review" in statuses
                else "visible",
                "is_synthetic": item.get("is_synthetic", False),
                "analysed_at": now(),
            }
        )
    return docs
