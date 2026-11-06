"""The one place that knows model IDs, loads models and versions their results.

Rules (CLAUDE.md §3):
- Nothing heavy is imported at module import time. torch / transformers / spaCy are
  imported inside the loaders, so `app.main` can import this module for /health/models.
- Each model is loaded lazily, once per process (thread-safe singleton).
- Inference runs under `torch.inference_mode()` with classifier inputs truncated to 256 tokens.

CLI:
    python -m app.nlp.registry --download        # fetch every model for the current ML_MODE
    python -m app.nlp.registry --check           # time every model, write docs/MODEL_CHECK.md
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import get_settings

Kind = Literal["classifier", "pair_classifier", "embedder", "seq2seq", "spacy"]
MAX_TOKENS = 256

# Bump when pre/post-processing changes in a way that should invalidate cached analyses.
PIPELINE_REVISION = 2


@dataclass(frozen=True)
class ModelSpec:
    task: str
    kind: Kind
    light: str
    full: str
    description: str


# SPEC §6. Change IDs here only.
MODELS: dict[str, ModelSpec] = {
    spec.task: spec
    for spec in [
        ModelSpec(
            "sentiment",
            "classifier",
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "3-class overall sentiment",
        ),
        ModelSpec(
            "embeddings",
            "embedder",
            "sentence-transformers/all-MiniLM-L6-v2",
            "sentence-transformers/all-mpnet-base-v2",
            "Sentence embeddings for aspect detection",
        ),
        ModelSpec(
            "absa",
            "pair_classifier",
            "yangheng/deberta-v3-base-absa-v1.1",
            "yangheng/deberta-v3-base-absa-v1.1",
            "Aspect polarity on (sentence, aspect) pairs",
        ),
        ModelSpec(
            "toxicity",
            "classifier",
            "unitary/unbiased-toxic-roberta",
            "unitary/unbiased-toxic-roberta",
            "Toxicity (multi-label) for moderation",
        ),
        ModelSpec(
            "emotion",
            "classifier",
            "j-hartmann/emotion-english-distilroberta-base",
            "j-hartmann/emotion-english-distilroberta-base",
            "7-class emotion distribution",
        ),
        ModelSpec(
            "irony",
            "classifier",
            "cardiffnlp/twitter-roberta-base-irony",
            "cardiffnlp/twitter-roberta-base-irony",
            "Irony / sarcasm probability",
        ),
        ModelSpec(
            "summarizer",
            "seq2seq",
            "sshleifer/distilbart-cnn-12-6",
            "facebook/bart-large-cnn",
            "No-LLM summarisation fallback",
        ),
        ModelSpec("ner", "spacy", "en_core_web_sm", "en_core_web_sm", "PERSON entities for PII"),
    ]
}


# Used only by `ml.evaluate` (SPEC §8), never by the app's pipeline, so they are kept out of
# MODELS and out of model_version(): adding them must not invalidate cached analyses.
EVAL_MODELS: dict[str, str] = {
    # the base model fine-tuned on CPU for the sentiment comparison, and BERTScore's encoder
    # (the default roberta-large is 1.4 GB and slow on a CPU)
    "finetune_base": "distilbert-base-uncased",
    "bertscore": "distilbert-base-uncased",
}


def eval_model_id(name: str) -> str:
    _init_runtime()
    return EVAL_MODELS[name]


def model_id(task: str) -> str:
    spec = MODELS[task]
    return spec.full if get_settings().ml_mode == "full" else spec.light


def model_version() -> str:
    """Tag stored on every analysis; changes with any model ID, threshold or pipeline change."""
    ids = json.dumps({t: model_id(t) for t in sorted(MODELS)}, sort_keys=True)
    settings = get_settings()
    # The thresholds decide what is hidden or flagged, so a change must not reuse old results.
    limits = (settings.tox_hide, settings.tox_review, settings.sarc_flag, settings.aspect_sim)
    digest = hashlib.sha1(f"{PIPELINE_REVISION}:{ids}:{limits}".encode()).hexdigest()[:8]
    return f"{get_settings().ml_mode}-r{PIPELINE_REVISION}-{digest}"


# --------------------------------------------------------------------------- latency stats


@dataclass
class Stats:
    calls: int = 0
    items: int = 0
    seconds: float = 0.0
    load_seconds: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, n_items: int, seconds: float) -> None:
        with self.lock:
            self.calls += 1
            self.items += n_items
            self.seconds += seconds

    @property
    def avg_ms_per_item(self) -> float | None:
        return round(1000 * self.seconds / self.items, 2) if self.items else None


class _Timed:
    def __init__(self, stats: Stats, n_items: int):
        self.stats, self.n_items = stats, n_items

    def __enter__(self):
        self.t0 = time.perf_counter()

    def __exit__(self, *exc):
        self.stats.record(self.n_items, time.perf_counter() - self.t0)


# --------------------------------------------------------------------------- model wrappers


class ClassifierModel:
    """Sequence classifier returning {label: prob} per text (sigmoid for multi-label models)."""

    def __init__(self, repo: str, stats: Stats):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.repo, self.stats = repo, stats
        self.tokenizer = AutoTokenizer.from_pretrained(repo)
        self.model = AutoModelForSequenceClassification.from_pretrained(repo).eval()
        cfg = self.model.config
        self.labels = [cfg.id2label[i].lower() for i in range(cfg.num_labels)]
        self.multi_label = cfg.problem_type == "multi_label_classification"

    def predict(self, texts: list[str], pairs: list[str] | None = None) -> list[dict[str, float]]:
        import torch

        if not texts:
            return []
        batch = get_settings().nlp_batch_size
        out: list[dict[str, float]] = []
        with _Timed(self.stats, len(texts)), torch.inference_mode():
            for i in range(0, len(texts), batch):
                enc = self.tokenizer(
                    texts[i : i + batch],
                    pairs[i : i + batch] if pairs else None,
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_tensors="pt",
                )
                logits = self.model(**enc).logits
                probs = torch.sigmoid(logits) if self.multi_label else torch.softmax(logits, dim=-1)
                for row in probs.tolist():
                    out.append({lab: round(p, 6) for lab, p in zip(self.labels, row, strict=True)})
        return out


class EmbeddingModel:
    def __init__(self, repo: str, stats: Stats):
        from sentence_transformers import SentenceTransformer

        self.repo, self.stats = repo, stats
        self.model = SentenceTransformer(repo, device="cpu")
        self.model.max_seq_length = min(self.model.max_seq_length, MAX_TOKENS)

    def encode(self, texts: list[str]):
        """Return an (n, dim) float32 numpy array of L2-normalised embeddings."""
        import torch

        with _Timed(self.stats, len(texts)), torch.inference_mode():
            return self.model.encode(
                texts,
                batch_size=get_settings().nlp_batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )


class Seq2SeqModel:
    """Summariser loaded with AutoModelForSeq2SeqLM and called via generate() (no pipeline())."""

    def __init__(self, repo: str, stats: Stats):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.repo, self.stats = repo, stats
        self.tokenizer = AutoTokenizer.from_pretrained(repo)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(repo).eval()
        # The checkpoint's own length limits clash with the *_new_tokens passed to generate()
        # (which win anyway) and log a warning on every call; drop them.
        self.model.generation_config.min_length = 0
        self.model.generation_config.max_length = None

    def summarize(self, text: str, max_new_tokens: int = 120, min_new_tokens: int = 20) -> str:
        import torch

        with _Timed(self.stats, 1), torch.inference_mode():
            enc = self.tokenizer(text, truncation=True, max_length=1024, return_tensors="pt")
            ids = self.model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                min_new_tokens=min_new_tokens,
                num_beams=2,
                no_repeat_ngram_size=3,
                early_stopping=True,
                forced_bos_token_id=self.tokenizer.bos_token_id,
            )
        return self.tokenizer.decode(ids[0], skip_special_tokens=True).strip()


class SpacyModel:
    def __init__(self, name: str, stats: Stats):
        import spacy

        self.repo, self.stats = name, stats
        # Only NER is needed for PII; skip the rest of the pipeline for speed.
        self.nlp = spacy.load(name, disable=["parser", "lemmatizer", "attribute_ruler"])

    def entities(self, texts: list[str]) -> list[list[tuple[str, str, int, int]]]:
        with _Timed(self.stats, len(texts)):
            return [
                [(e.text, e.label_, e.start_char, e.end_char) for e in doc.ents]
                for doc in self.nlp.pipe(texts, batch_size=get_settings().nlp_batch_size)
            ]


_WRAPPERS: dict[Kind, type] = {
    "classifier": ClassifierModel,
    "pair_classifier": ClassifierModel,
    "embedder": EmbeddingModel,
    "seq2seq": Seq2SeqModel,
    "spacy": SpacyModel,
}

# --------------------------------------------------------------------------- singletons

_loaded: dict[str, Any] = {}
_stats: dict[str, Stats] = {t: Stats() for t in MODELS}
_locks: dict[str, threading.Lock] = {t: threading.Lock() for t in MODELS}
_torch_ready = False
_torch_lock = threading.Lock()


def _init_runtime() -> None:
    """Point HF at the project cache and set CPU threads, once per process."""
    global _torch_ready
    with _torch_lock:
        if _torch_ready:
            return
        settings = get_settings()
        os.environ.setdefault("HF_HOME", str(settings.hf_home_path))
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        import torch

        torch.set_num_threads(settings.torch_num_threads)
        _torch_ready = True


def get(task: str):
    """Return the loaded model wrapper for `task`, loading it on first use."""
    if task not in MODELS:
        raise KeyError(f"Unknown model task: {task}")
    if task in _loaded:
        return _loaded[task]
    with _locks[task]:
        if task not in _loaded:
            _init_runtime()
            t0 = time.perf_counter()
            _loaded[task] = _WRAPPERS[MODELS[task].kind](model_id(task), _stats[task])
            _stats[task].load_seconds = round(time.perf_counter() - t0, 2)
    return _loaded[task]


def unload(task: str) -> None:
    _loaded.pop(task, None)


def status() -> list[dict[str, Any]]:
    """Per-model status for /health/models. Never loads anything."""
    rows = []
    for task, spec in MODELS.items():
        s = _stats[task]
        rows.append(
            {
                "task": task,
                "model_id": model_id(task),
                "description": spec.description,
                "loaded": task in _loaded,
                "load_seconds": s.load_seconds,
                "calls": s.calls,
                "items": s.items,
                "avg_ms_per_item": s.avg_ms_per_item,
            }
        )
    return rows


if __name__ == "__main__":
    from app.nlp.model_check import main

    main()
