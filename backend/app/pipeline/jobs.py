"""Background analysis jobs (SPEC §3 step 4, CLAUDE.md §3).

One worker thread per API process runs one job at a time, in batches of NLP_BATCH_SIZE, with
its own synchronous MongoDB client so CPU-heavy model calls never block the event loop.
Results are cached: a response that already has an analysis for the current model_version is
never scored again, so re-running a cycle (or an interrupted job) only does the missing work.

Job kinds: "cycle" (every unanalysed response in a cycle, started by an admin) and "auto"
(responses submitted since the last auto job; each submission is queued).
"""

import contextlib
import logging
import queue
import threading
import time
from typing import Any

from bson import ObjectId
from pymongo.errors import BulkWriteError

from app import db
from app.config import get_settings
from app.nlp import registry
from app.pipeline import summaries
from app.pipeline.aggregate import recompute_form
from app.utils import anon_id, now, today

log = logging.getLogger("facultylens.jobs")

_queue: "queue.Queue[ObjectId | None]" = queue.Queue()
_auto: set[ObjectId] = set()
_auto_lock = threading.Lock()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


# --------------------------------------------------------------------------- selection


def pending_response_ids(sync_db, form_ids: list[ObjectId]) -> list[ObjectId]:
    """Responses in these forms with no analysis for the current model version."""
    version = registry.model_version()
    ids = [r["_id"] for r in sync_db.responses.find({"form_id": {"$in": form_ids}}, {"_id": 1})]
    done = {
        a["response_id"]
        for a in sync_db.analyses.find(
            {"response_id": {"$in": ids}, "model_version": version}, {"response_id": 1}
        )
    }
    return [i for i in ids if i not in done]


def _items(sync_db, responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Responses -> analyse_batch items, with the teacher names PII redaction must catch."""
    form_ids = list({r["form_id"] for r in responses})
    forms = {f["_id"]: f for f in sync_db.forms.find({"_id": {"$in": form_ids}})}
    courses = {
        c["_id"]: c
        for c in sync_db.courses.find(
            {"_id": {"$in": list({f["course_id"] for f in forms.values()})}}, {"faculty_ids": 1}
        )
    }
    people_ids = {fid for c in courses.values() for fid in c.get("faculty_ids", [])}
    names = {
        u["_id"]: u["name"]
        for u in sync_db.users.find({"_id": {"$in": list(people_ids)}}, {"name": 1})
    }
    items = []
    for r in responses:
        form = forms[r["form_id"]]
        course = courses.get(form["course_id"], {})
        teacher_ids = (
            [form["faculty_id"]] if form.get("faculty_id") else course.get("faculty_ids", [])
        )
        items.append(
            {
                "response_id": r["_id"],
                "form_id": r["form_id"],
                "type": form["type"],
                "texts": r.get("texts", {}),
                "faculty_names": [names[t] for t in teacher_ids if t in names],
                "is_synthetic": r.get("is_synthetic", False),
            }
        )
    return items


def _queue_entries(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for doc in docs:
        for f in doc["fields"]:
            if f["moderation_status"] in ("hidden", "review"):
                decided = f.get("moderation")
                entries.append(
                    {
                        "analysis_id": doc["_id"],
                        "form_id": doc["form_id"],
                        "field": f["field"],
                        "kind": f["moderation_status"],
                        "score": f["toxicity"]["max"],
                        "label": f["toxicity"]["label"],
                        "status": "decided" if decided else "pending",
                        **(
                            {
                                "decision": decided["decision"],
                                "decided_by": decided.get("by"),
                                "decided_at": decided.get("at"),
                            }
                            if decided
                            else {}
                        ),
                        "is_synthetic": doc.get("is_synthetic", False),
                        "created_at": today(),  # the day only: see analyze_batch
                        "_id": anon_id(),
                    }
                )
    return entries


def _retire_old_queue_entries(sync_db, response_ids: list[ObjectId], version: str) -> None:
    """Re-analysed answers replace their older versions: queue entries would list each answer
    twice, and old analyses only take space (decisions were already carried forward)."""
    old = sync_db.analyses.find(
        {"response_id": {"$in": response_ids}, "model_version": {"$ne": version}}, {"_id": 1}
    )
    old_ids = [a["_id"] for a in old]
    if old_ids:
        sync_db.moderation_queue.delete_many({"analysis_id": {"$in": old_ids}})
        sync_db.analyses.delete_many({"_id": {"$in": old_ids}})


def _carry_decisions(sync_db, docs: list[dict[str, Any]]) -> None:
    """A person's moderation decision still holds when the models change and answers are redone."""
    earlier = sync_db.analyses.find(
        {
            "response_id": {"$in": [d["response_id"] for d in docs]},
            "fields.moderation": {"$exists": True},
        },
        {"response_id": 1, "fields.field": 1, "fields.moderation": 1},
    )
    decisions = {
        (a["response_id"], f["field"]): f["moderation"]
        for a in earlier
        for f in a["fields"]
        if f.get("moderation")
    }
    for doc in docs:
        for f in doc["fields"]:
            decision = decisions.get((doc["response_id"], f["field"]))
            if decision:
                f["moderation"] = decision


# --------------------------------------------------------------------------- running


def _analyse_keeping_good(analyze_batch, items: list[dict]) -> tuple[list[dict], int]:
    """Analyse a batch; if it fails, one by one, so one bad answer can't stop the whole run."""
    try:
        return analyze_batch(items), 0
    except Exception as exc:
        # The type only: an error message could quote a student's unredacted answer.
        log.warning("analysis batch of %d failed (%s)", len(items), type(exc).__name__)
    good, failed = [], 0
    for item in items:
        try:
            good.extend(analyze_batch([item]))
        except Exception as exc:
            failed += 1
            log.warning("response could not be analysed (%s)", type(exc).__name__)
    return good, failed


def run_job(job_id: ObjectId, sync_db=None) -> dict[str, Any]:
    """Run one job to completion (called by the worker; tests call it directly)."""
    from app.nlp.analyze import analyze_batch  # heavy imports stay out of app start-up

    sync_db = db.get_sync_db() if sync_db is None else sync_db
    job = sync_db.analysis_jobs.find_one({"_id": job_id})
    started = time.perf_counter()
    version = registry.model_version()
    sync_db.analysis_jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "running", "started_at": now(), "model_version": version}},
    )
    try:
        if job["kind"] == "summaries":
            return _run_summaries(sync_db, job, version, started)
        if job["kind"] == "cycle":
            form_ids = [
                f["_id"] for f in sync_db.forms.find({"cycle_id": job["cycle_id"]}, {"_id": 1})
            ]
            todo = pending_response_ids(sync_db, form_ids)
        else:
            todo = pending_response_ids(
                sync_db,
                list(
                    {
                        r["form_id"]
                        for r in sync_db.responses.find(
                            {"_id": {"$in": job["response_ids"]}}, {"form_id": 1}
                        )
                    }
                ),
            )
            # Every pending answer in these forms, not only the new ones: after a model or
            # threshold change, recomputing a form from one answer would wipe its results.
        total = len(todo)
        sync_db.analysis_jobs.update_one({"_id": job_id}, {"$set": {"total": total, "done": 0}})

        batch_size = get_settings().nlp_batch_size
        touched_forms: set[ObjectId] = set()
        counts = {"hidden": 0, "review": 0, "pii": 0, "sarcastic": 0}
        failed = 0
        for i in range(0, total, batch_size):
            ids = todo[i : i + batch_size]
            responses = list(sync_db.responses.find({"_id": {"$in": ids}}))
            analysed, failures = _analyse_keeping_good(analyze_batch, _items(sync_db, responses))
            failed += failures
            docs = [{"_id": anon_id(), **d} for d in analysed]
            if not docs:
                sync_db.analysis_jobs.update_one(
                    {"_id": job_id}, {"$set": {"done": min(i + batch_size, total)}}
                )
                continue
            _carry_decisions(sync_db, docs)
            try:
                result = sync_db.analyses.insert_many(docs, ordered=False)
                for doc, _id in zip(docs, result.inserted_ids, strict=True):
                    doc["_id"] = _id
            except BulkWriteError:
                # Someone else analysed some of these meanwhile (unique index): keep the others.
                inserted = {
                    a["response_id"]: a["_id"]
                    for a in sync_db.analyses.find(
                        {"response_id": {"$in": ids}, "model_version": version}, {"response_id": 1}
                    )
                }
                for doc in docs:
                    doc["_id"] = inserted.get(doc["response_id"])
            entries = _queue_entries([d for d in docs if d.get("_id")])
            if entries:
                with contextlib.suppress(BulkWriteError):
                    sync_db.moderation_queue.insert_many(entries, ordered=False)
            _retire_old_queue_entries(sync_db, [d["response_id"] for d in docs], version)
            for doc in docs:
                touched_forms.add(doc["form_id"])
                for f in doc["fields"]:
                    counts["hidden"] += f["moderation_status"] == "hidden"
                    counts["review"] += f["moderation_status"] == "review"
                    counts["pii"] += sum(f["pii_found"].values())
                    counts["sarcastic"] += bool(f["sentiment_uncertain"])
            sync_db.analysis_jobs.update_one(
                {"_id": job_id}, {"$set": {"done": min(i + batch_size, total), "counts": counts}}
            )

        if total and failed == total:
            raise RuntimeError(f"All {total} responses failed analysis; see the server log.")
        if job["kind"] == "cycle":
            touched_forms |= set(form_ids)
        forms = list(sync_db.forms.find({"_id": {"$in": list(touched_forms)}}))
        for form in forms:
            recompute_form(sync_db, form, version)
        analysis_seconds = time.perf_counter() - started
        summary_counts = summaries.refresh_forms(sync_db, forms, version)

        elapsed = round(time.perf_counter() - started, 2)
        final = {
            "status": "done",
            "finished_at": now(),
            "seconds": elapsed,
            "per_response_ms": round(1000 * analysis_seconds / total, 1) if total else None,
            "summary_seconds": round(time.perf_counter() - started - analysis_seconds, 2),
            "counts": {**counts, "summaries_built": summary_counts.get("built", 0)},
            "failed_responses": failed,  # still waiting: the next run tries them again
        }
        sync_db.analysis_jobs.update_one({"_id": job_id}, {"$set": final})
        return {**job, **final, "total": total}
    except Exception as exc:  # never kill the worker; record and move on
        log.exception("analysis job %s failed", job_id)
        sync_db.analysis_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "finished_at": now(),
                }
            },
        )
        return {**job, "status": "failed"}


def _run_summaries(sync_db, job: dict[str, Any], version: str, started: float) -> dict[str, Any]:
    """Rebuild every teaching-form summary in a cycle, even if its fingerprint is unchanged."""
    forms = list(sync_db.forms.find({"cycle_id": job["cycle_id"], "type": "teaching"}))
    sync_db.analysis_jobs.update_one(
        {"_id": job["_id"]}, {"$set": {"total": len(forms), "done": 0}}
    )
    built = 0
    for i, form in enumerate(forms, start=1):
        try:
            built += summaries.refresh_form(sync_db, form, version, force=True) == "built"
        except Exception:
            log.exception("summary for form %s failed", form["_id"])
        sync_db.analysis_jobs.update_one({"_id": job["_id"]}, {"$set": {"done": i}})
    elapsed = round(time.perf_counter() - started, 2)
    final = {
        "status": "done",
        "finished_at": now(),
        "seconds": elapsed,
        "per_response_ms": None,
        "counts": {"summaries_built": built},
    }
    sync_db.analysis_jobs.update_one({"_id": job["_id"]}, {"$set": final})
    return {**job, **final, "total": len(forms)}


def _mark_failed(job_id: ObjectId | None) -> None:
    """Never leave a job showing as running, or the cycle could not be analysed again."""
    if job_id is None:
        return
    db.get_sync_db().analysis_jobs.update_one(
        {"_id": job_id, "status": {"$in": ["queued", "running"]}},
        {
            "$set": {
                "status": "failed",
                "error": "The analysis worker stopped",
                "finished_at": now(),
            }
        },
    )


def _loop() -> None:
    while True:
        job_id = _queue.get()
        try:
            if job_id is None:
                with _auto_lock:
                    ids = list(_auto)
                    _auto.clear()
                if not ids:
                    continue
                job_id = create_job_sync({"kind": "auto", "response_ids": ids})
            run_job(job_id)
        except Exception:  # e.g. the database went away: the next job must still run
            log.exception("analysis worker recovered from an error (job %s)", job_id)
            with contextlib.suppress(Exception):
                _mark_failed(job_id)


def _ensure_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, name="analysis-worker", daemon=True)
            _worker.start()


def create_job_sync(spec: dict[str, Any]) -> ObjectId:
    doc = {**spec, "status": "queued", "total": None, "done": 0, "created_at": now()}
    return db.get_sync_db().analysis_jobs.insert_one(doc).inserted_id


def enqueue(job_id: ObjectId) -> None:
    _ensure_worker()
    _queue.put(job_id)


def submit_auto(response_id: ObjectId) -> None:
    """Queue one new response; the worker groups queued responses into one small job."""
    if not get_settings().analysis_on_submit:
        return
    with _auto_lock:
        _auto.add(response_id)
    _ensure_worker()
    _queue.put(None)


def mark_interrupted(sync_db=None) -> int:
    """At start-up: jobs left running or queued by a previous process can't continue."""
    sync_db = db.get_sync_db() if sync_db is None else sync_db
    result = sync_db.analysis_jobs.update_many(
        {"status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "interrupted", "finished_at": now()}},
    )
    return result.modified_count
