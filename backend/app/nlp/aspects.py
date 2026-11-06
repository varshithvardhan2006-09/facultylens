"""Teaching-aspect detection (SPEC §5 steps 5-6).

A sentence gets an aspect when its MiniLM embedding is close enough (cosine >= ASPECT_SIM) to
that aspect's prototype - the mean embedding of its seed phrases, label and question - or when
one of its seed phrases appears in the sentence. At most two aspects per sentence. The polarity
of each (sentence, aspect) pair then comes from the ABSA model.
"""

import re
import threading
from functools import lru_cache

import numpy as np

from app.config import get_settings
from app.feedback_spec import ASPECT_KEYS, TEACHING_ASPECTS
from app.nlp import registry

MAX_ASPECTS = 2
SECOND_MARGIN = 0.12  # chosen on the seed-style smoke sentences; Phase 8 tunes on labelled data
# The aspect term passed to the ABSA model with each sentence.
ASPECT_TERMS = {
    "knowledge": "subject knowledge",
    "clarity": "explanation",
    "punctuality": "punctuality",
    "interaction": "doubt clearing",
    "practical": "practical examples",
    "assessment": "marking and evaluation",
    "behaviour": "behaviour",
    "pace": "pace",
}

_lock = threading.Lock()
_prototypes: dict[str, np.ndarray] = {}


def prototype_texts() -> dict[str, list[str]]:
    return {key: [*seeds, label, question] for key, label, question, seeds in TEACHING_ASPECTS}


def prototypes() -> np.ndarray:
    """(8, dim) unit vectors, computed once per model version."""
    version = registry.model_version()
    with _lock:
        if version not in _prototypes:
            texts = prototype_texts()
            vectors = []
            for key in ASPECT_KEYS:
                emb = registry.get("embeddings").encode(texts[key])
                mean = emb.mean(axis=0)
                vectors.append(mean / (np.linalg.norm(mean) or 1.0))
            _prototypes[version] = np.vstack(vectors)
        return _prototypes[version]


@lru_cache
def _lexicon() -> list[tuple[str, re.Pattern]]:
    out = []
    for key, _, _, seeds in TEACHING_ASPECTS:
        for phrase in seeds:
            out.append((key, re.compile(rf"\b{re.escape(phrase.lower())}\b")))
    return out


def lexicon_hits(sentence: str) -> set[str]:
    text = sentence.lower()
    return {key for key, pattern in _lexicon() if pattern.search(text)}


def assign(sims: np.ndarray, sentences: list[str]) -> list[list[tuple[str, float, str]]]:
    """Per sentence: up to 2 (aspect, similarity, how) with how = 'embedding' | 'lexicon'."""
    threshold = get_settings().aspect_sim
    out = []
    for row, sentence in zip(sims, sentences, strict=True):
        hits = lexicon_hits(sentence)
        found = []
        for i, key in enumerate(ASPECT_KEYS):
            sim = float(row[i])
            if sim >= threshold:
                found.append((key, round(sim, 4), "embedding"))
            elif key in hits:
                found.append((key, round(sim, 4), "lexicon"))
        found.sort(key=lambda f: -f[1])
        # A second aspect must be nearly as close as the first, or named outright; otherwise a
        # generic prototype ("knowledge") attaches weakly to every sentence.
        kept = found[:1] + [
            f
            for f in found[1:MAX_ASPECTS]
            if f[2] == "lexicon" or f[1] >= found[0][1] - SECOND_MARGIN
        ]
        out.append(kept)
    return out


def detect(sentences: list[str]) -> list[list[tuple[str, float, str]]]:
    if not sentences:
        return []
    emb = registry.get("embeddings").encode(sentences)
    return assign(emb @ prototypes().T, sentences)
