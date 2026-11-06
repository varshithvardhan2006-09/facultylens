"""Measure the whole pipeline on a real cycle: `python -m app.pipeline.bench [--cycle ID]`.

Runs one analysis job from cold (models not yet loaded) on every unanalysed response in the
cycle, then a second job to prove the cache (it must score 0 responses). Records total time,
per-response time per batch (mean, p95), peak process RAM and what the pipeline found, to
ml/results/pipeline_check.json and a section of docs/MODEL_CHECK.md.

Run it on demo data (python -m app.seed) or a copy; it writes analyses like a normal run.
"""

import argparse
import json
import os
import statistics
import threading
import time
from datetime import UTC, datetime

import psutil
from bson import ObjectId

from app import db
from app.config import BACKEND_DIR, get_settings
from app.nlp import analyze, registry
from app.pipeline import jobs

RESULTS = BACKEND_DIR / "ml" / "results" / "pipeline_check.json"
DOC = BACKEND_DIR.parent / "docs" / "MODEL_CHECK.md"
MARKER = "## Full pipeline on a seeded cycle"


def _peak_rss(stop: threading.Event, box: dict) -> None:
    proc = psutil.Process(os.getpid())
    while not stop.is_set():
        box["peak"] = max(box.get("peak", 0), proc.memory_info().rss)
        time.sleep(0.2)


def _sarcasm_check(sync_db, cycle_id) -> dict:
    """Flags against the seed's own sarcastic lines (a sanity check, not the Phase 8 metric)."""
    from app.seed import SARCASM

    form_ids = [f["_id"] for f in sync_db.forms.find({"cycle_id": cycle_id}, {"_id": 1})]
    flagged = truth = hits = 0
    for a in sync_db.analyses.find({"form_id": {"$in": form_ids}}, {"fields": 1}):
        for f in a["fields"]:
            seeded = f["redacted"] in SARCASM
            truth += seeded
            flagged += bool(f["sentiment_uncertain"])
            hits += seeded and bool(f["sentiment_uncertain"])
    return {
        "threshold": get_settings().sarc_flag,
        "seeded_sarcastic_answers": truth,
        "flagged": flagged,
        "flagged_and_seeded": hits,
        "precision": round(hits / flagged, 2) if flagged else None,
        "recall": round(hits / truth, 2) if truth else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.pipeline.bench")
    parser.add_argument("--cycle", help="cycle id (default: the open cycle)")
    args = parser.parse_args()
    sync_db = db.get_sync_db()
    cycle = (
        sync_db.feedback_cycles.find_one({"_id": ObjectId(args.cycle)})
        if args.cycle
        else sync_db.feedback_cycles.find_one({"status": "open"}, sort=[("opens_at", -1)])
    )
    if not cycle:
        raise SystemExit("No cycle found. Seed demo data first: python -m app.seed")

    batch_times: list[float] = []
    original = analyze.analyze_batch

    def timed(items):
        t = time.perf_counter()
        docs = original(items)
        batch_times.append((time.perf_counter() - t) / max(len(items), 1))
        return docs

    analyze.analyze_batch = timed
    stop, box = threading.Event(), {}
    watcher = threading.Thread(target=_peak_rss, args=(stop, box), daemon=True)
    watcher.start()
    rss_before = psutil.Process(os.getpid()).memory_info().rss
    t0 = time.perf_counter()
    first = jobs.run_job(jobs.create_job_sync({"kind": "cycle", "cycle_id": cycle["_id"]}), sync_db)
    first_seconds = time.perf_counter() - t0
    second = jobs.run_job(
        jobs.create_job_sync({"kind": "cycle", "cycle_id": cycle["_id"]}), sync_db
    )
    stop.set()
    watcher.join()
    analyze.analyze_batch = original

    if first["status"] != "done":
        raise SystemExit(f"The job failed: {first.get('error')}")
    warm = batch_times[1:] or batch_times  # the first batch includes loading every model
    settings = get_settings()
    sarcasm = _sarcasm_check(sync_db, cycle["_id"])
    result = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cycle": cycle["name"],
        "model_version": registry.model_version(),
        "torch_num_threads": settings.torch_num_threads,
        "batch_size": settings.nlp_batch_size,
        "machine": {
            "cpu": os.environ.get("PROCESSOR_IDENTIFIER", ""),
            "logical_cores": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        },
        "responses_analysed": first["total"],
        "total_seconds_cold": round(first_seconds, 1),
        "per_response_ms_warm_mean": round(1000 * statistics.mean(warm), 1),
        "per_response_ms_warm_p95": round(1000 * statistics.quantiles(warm, n=20)[18], 1)
        if len(warm) >= 2
        else round(1000 * warm[0], 1),
        "first_batch_ms_per_response": round(1000 * batch_times[0], 1),
        "rss_before_mb": round(rss_before / 2**20),
        "peak_rss_mb": round(box.get("peak", 0) / 2**20),
        "found": first.get("counts", {}),
        "cache_check_responses_rescored": second["total"],
        "sarcasm_vs_seeded_lines": sarcasm,
        "budget": "300 responses in under 10 minutes on a 4-core CPU (SPEC §13)",
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2), encoding="utf-8")

    rows = [
        ("Responses analysed (teaching + curriculum)", result["responses_analysed"], ""),
        ("Total time, cold start (includes loading all models)", result["total_seconds_cold"], "s"),
        ("Per response, warm batches, mean", result["per_response_ms_warm_mean"], "ms"),
        ("Per response, warm batches, p95", result["per_response_ms_warm_p95"], "ms"),
        ("First batch per response (model loading)", result["first_batch_ms_per_response"], "ms"),
        ("Peak process RAM", result["peak_rss_mb"], "MB"),
        (
            "Responses re-scored on a second run (cache check)",
            result["cache_check_responses_rescored"],
            "",
        ),
    ]
    lines = [
        MARKER,
        "",
        f"Measured {result['measured_at']} with `python -m app.pipeline.bench` on "
        f"**{result['cycle']}** (synthetic seed data), "
        f"`TORCH_NUM_THREADS={result['torch_num_threads']}`, batch size "
        f"{result['batch_size']}, `model_version={result['model_version']}`.",
        "",
        "| Measure | Value |",
        "|---|---:|",
        *(f"| {label} | {f'{value} {unit}'.strip()} |" for label, value, unit in rows),
        "",
        "What the pipeline flagged: "
        + ", ".join(f"{k} {v}" for k, v in result["found"].items())
        + " (answers; PII is the number of items redacted).",
        f"Budget: {result['budget']}.",
        "",
        f"Sarcasm flag (`SARC_FLAG={sarcasm['threshold']}`) against the seed's own sarcastic "
        f"lines: {sarcasm['flagged']} answers flagged, {sarcasm['flagged_and_seeded']} of the "
        f"{sarcasm['seeded_sarcastic_answers']} seeded sarcastic answers among them (precision "
        f"{sarcasm['precision']}, recall {sarcasm['recall']}). The irony model is trained on "
        "tweets and scores short sincere praise almost as high as sarcasm (0.97-0.99 against "
        "0.98-0.99), so no threshold separates them; at the earlier 0.70 it flagged 181 answers "
        "for 22 seeded ones (precision 0.12). Flags are shown as *possibly* sarcastic and only "
        "halve an answer's weight; Phase 8 measures this on hand-labelled comments.",
        "",
    ]
    doc = DOC.read_text(encoding="utf-8") if DOC.exists() else "# Model check (CPU)\n"
    section = "\n".join(lines).rstrip() + "\n"
    if MARKER in doc:
        # Replace this section only; later sections (written by other phases) stay.
        start = doc.index(MARKER)
        end = doc.find("\n## ", start + len(MARKER))
        rest = doc[end + 1 :] if end != -1 else ""
        doc = doc[:start] + section + ("\n" + rest if rest else "")
    else:
        doc = doc.rstrip() + "\n\n" + section
    DOC.write_text(doc, encoding="utf-8")
    print(json.dumps(result, indent=2))
    db.close_sync_client()


if __name__ == "__main__":
    main()
