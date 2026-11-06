"""`python -m app.nlp.registry --download | --check [--threads N]`.

--download  fetch every model for the current ML_MODE (by loading it once) + NLTK data.
--check     load every model one at a time, keep them loaded, and measure load time,
            RAM increase, batched latency per comment and single-comment p95.
            Writes ml/results/model_check_t{threads}.json and regenerates docs/MODEL_CHECK.md
            from every model_check_t*.json present.

The 16 timing sentences below are hand-written for benchmarking speed only.
They are not feedback data and are never used for evaluation.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import sys
import time
import traceback
from datetime import UTC, datetime

import psutil

from app.config import BACKEND_DIR, get_settings
from app.nlp import registry

RESULTS_DIR = BACKEND_DIR / "ml" / "results"
DOC_PATH = BACKEND_DIR.parent / "docs" / "MODEL_CHECK.md"
NLTK_PACKAGES = ["punkt_tab", "stopwords", "wordnet", "omw-1.4", "vader_lexicon"]
SLOW_LIMIT_MS = 1500  # SPEC §6: > 1.5 s per comment in batches of 16 is too slow

TIMING_TEXTS = [
    "Sir explains every concept clearly and gives real-world examples from industry.",
    "The classes are too fast and we could not follow the derivations at all.",
    "Madam is always on time and completes the syllabus well before the exams.",
    "Internal marks were not fair and the assignments were never returned with feedback.",
    "Very approachable after class, happy to clear doubts even during lunch.",
    "Lab sessions were useful but the record work took too much of our time.",
    "Great, another lecture where we just read the slides aloud. Very helpful.",
    "Strict about attendance but the teaching is excellent and motivating.",
    "Sometimes cancels class without informing, which makes us lose portions.",
    "Deep knowledge of the subject; answers every question patiently.",
    "Please slow down while solving problems on the board and explain each step.",
    "The course outcomes were clear and the reference books were good.",
    "Not engaging, but the notes are informative and well organised.",
    "Friendly and respectful towards students, never rude even when we are late.",
    "More practical applications and mini projects would make this subject interesting.",
    "Overall a good teacher, though the pace of the last unit was rushed.",
]
ASPECTS = [
    "clarity",
    "pace",
    "punctuality",
    "assessment",
    "interaction",
    "practical",
    "behaviour",
    "behaviour",
    "punctuality",
    "knowledge",
    "clarity",
    "knowledge",
    "interaction",
    "behaviour",
    "practical",
    "pace",
]


def _rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 2**20


def _run(task: str, model, texts: list[str]) -> None:
    kind = registry.MODELS[task].kind
    if kind == "classifier":
        model.predict(texts)
    elif kind == "pair_classifier":
        model.predict(texts, ASPECTS[: len(texts)])
    elif kind == "embedder":
        model.encode(texts)
    elif kind == "spacy":
        model.entities(texts)
    elif kind == "seq2seq":
        model.summarize(" ".join(texts))


def _sample_output(task: str, model) -> str:
    kind = registry.MODELS[task].kind
    text = TIMING_TEXTS[1]
    if kind == "classifier":
        top = max(model.predict([text])[0].items(), key=lambda kv: kv[1])
        return f"{top[0]} ({top[1]:.2f})"
    if kind == "pair_classifier":
        top = max(model.predict([text], ["pace"])[0].items(), key=lambda kv: kv[1])
        return f"pace -> {top[0]} ({top[1]:.2f})"
    if kind == "embedder":
        return f"dim={model.encode([text]).shape[1]}"
    if kind == "spacy":
        return str(model.entities(["Dr. Ramesh Kumar teaches DBMS in Hyderabad."])[0])
    return model.summarize(" ".join(TIMING_TEXTS))[:160]


def download() -> int:
    import nltk

    failed = 0
    for pkg in NLTK_PACKAGES:
        ok = nltk.download(pkg, quiet=True)
        print(f"nltk {pkg}: {'ok' if ok else 'FAILED'}")
        failed += not ok
    for task in registry.MODELS:
        mid = registry.model_id(task)
        try:
            t0 = time.perf_counter()
            registry.get(task)
            print(f"{task:<11} {mid}: ok ({time.perf_counter() - t0:.1f}s)")
        except Exception as exc:  # report and keep going so one bad ID doesn't hide others
            failed += 1
            print(f"{task:<11} {mid}: FAILED {type(exc).__name__}: {exc}")
        registry.unload(task)
        gc.collect()
    return failed


def check(threads: int) -> dict:
    settings = get_settings()
    rows = []
    base_rss = _rss_mb()
    batch = settings.nlp_batch_size
    for task in registry.MODELS:
        mid = registry.model_id(task)
        row: dict = {"task": task, "model_id": mid}
        try:
            before = _rss_mb()
            t0 = time.perf_counter()
            model = registry.get(task)
            row["load_s"] = round(time.perf_counter() - t0, 2)
            _run(task, model, TIMING_TEXTS[:2])  # warm-up
            row["rss_increase_mb"] = round(_rss_mb() - before, 1)

            if registry.MODELS[task].kind == "seq2seq":
                runs = []
                for _ in range(3):
                    t = time.perf_counter()
                    _run(task, model, TIMING_TEXTS)
                    runs.append(time.perf_counter() - t)
                row["unit"] = "per summary of 16 comments"
                row["batch_ms_per_comment"] = round(1000 * statistics.mean(runs), 1)
                row["single_p95_ms"] = round(1000 * max(runs), 1)
            else:
                runs = []
                for _ in range(5):
                    t = time.perf_counter()
                    _run(task, model, TIMING_TEXTS[:batch])
                    runs.append((time.perf_counter() - t) / min(batch, len(TIMING_TEXTS)))
                singles = []
                for text in TIMING_TEXTS:
                    t = time.perf_counter()
                    _run(task, model, [text])
                    singles.append(time.perf_counter() - t)
                row["unit"] = "per comment"
                row["batch_ms_per_comment"] = round(1000 * statistics.mean(runs), 1)
                row["single_p95_ms"] = round(1000 * statistics.quantiles(singles, n=20)[18], 1)
            row["sample"] = _sample_output(task, model)
            row["status"] = "ok"
            if row["unit"] == "per comment" and row["batch_ms_per_comment"] > SLOW_LIMIT_MS:
                row["status"] = "too slow"
        except Exception as exc:
            row["status"] = f"FAILED: {type(exc).__name__}: {exc}"
            traceback.print_exc()
        rows.append(row)
        print(json.dumps(row))

    vm = psutil.virtual_memory()
    import torch

    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ml_mode": settings.ml_mode,
        "model_version": registry.model_version(),
        "torch_num_threads": threads,
        "nlp_batch_size": batch,
        "machine": {
            "cpu": platform.processor() or platform.machine(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "ram_gb": round(vm.total / 2**30, 1),
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "baseline_rss_mb": round(base_rss, 1),
        "all_loaded_rss_mb": round(_rss_mb(), 1),
        "models": rows,
    }


def write_doc() -> None:
    runs = [json.loads(p.read_text()) for p in sorted(RESULTS_DIR.glob("model_check_t*.json"))]
    if not runs:
        return
    m = runs[0]["machine"]
    lines = [
        "# Model check (CPU)",
        "",
        "Generated by `python -m app.nlp.registry --check`. Every number here was measured on the "
        "machine below; re-run the command on the demo PC and commit the new file.",
        "",
        f"- **CPU:** {m['cpu']} ({m['physical_cores']} cores / {m['logical_cores']} threads), "
        f"**RAM:** {m['ram_gb']} GB, **OS:** {m['os']}",
        f"- **Python** {m['python']}, **torch** {m['torch']}, `ML_MODE={runs[0]['ml_mode']}`, "
        f"batch size {runs[0]['nlp_batch_size']}, `model_version={runs[0]['model_version']}`",
        "- *Batch ms/comment*: mean over 5 batches of 16 comments, divided by 16. "
        "*Single p95*: 95th percentile over 16 one-comment calls. "
        "*RAM +MB*: process RSS increase after loading the model and one warm-up call.",
        f"- Budget (SPEC §6): at most {SLOW_LIMIT_MS} ms per comment in batches of 16.",
        "- Caveat: the timing texts are single sentences of about 12 words. Real responses have "
        "three answers and run longer, so Phase 4 re-measures on seeded data end to end.",
        "",
    ]
    for run in runs:
        lines += [
            f"## `TORCH_NUM_THREADS={run['torch_num_threads']}` (measured {run['measured_at']})",
            "",
            "| Task | Model | Load (s) | RAM +MB | Batch ms/comment | Single p95 ms | Status |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for r in run["models"]:
            lines.append(
                f"| {r['task']} | `{r['model_id']}` | {r.get('load_s', '–')} | "
                f"{r.get('rss_increase_mb', '–')} | {r.get('batch_ms_per_comment', '–')} | "
                f"{r.get('single_p95_ms', '–')} | {r['status']} |"
            )
        per_comment = sum(
            r.get("batch_ms_per_comment", 0)
            for r in run["models"]
            if r.get("unit") == "per comment"
        )
        lines += [
            "",
            f"- Process RSS with **all models loaded**: **{run['all_loaded_rss_mb']} MB** "
            f"(baseline {run['baseline_rss_mb']} MB).",
            f"- Sum of per-comment model time (every classifier/embedder once per comment, "
            f"before ABSA runs once per detected aspect): **{per_comment:.0f} ms**.",
            "- The summariser row is per summary (one call over 16 comments), not per comment.",
            "",
        ]
    lines += ["## Sample outputs (sanity check)", ""]
    for r in runs[0]["models"]:
        lines.append(f"- **{r['task']}**: {r.get('sample', r['status'])}")
    full_only = sorted(
        {s.full for s in registry.MODELS.values()} - {s.light for s in registry.MODELS.values()}
    )
    lines += [
        "",
        "## Not measured yet",
        "",
        "`ML_MODE=full` models (not downloaded in Phase 0): "
        + ", ".join(f"`{x}`" for x in full_only),
        "",
    ]
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DOC_PATH}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.nlp.registry")
    parser.add_argument("--download", action="store_true", help="download every model")
    parser.add_argument("--check", action="store_true", help="load and time every model")
    parser.add_argument("--threads", type=int, help="override TORCH_NUM_THREADS for --check")
    args = parser.parse_args(argv)
    if not (args.download or args.check):
        parser.print_help()
        return
    if args.threads:
        os.environ["TORCH_NUM_THREADS"] = str(args.threads)
        get_settings.cache_clear()
    if args.download and download():
        sys.exit(1)
    if args.check:
        threads = get_settings().torch_num_threads
        result = check(threads)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"model_check_t{threads}.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"wrote {out}")
        write_doc()
