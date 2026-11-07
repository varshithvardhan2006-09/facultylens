"""Keep each teaching form's summary in step with its aggregate (synchronous, worker thread).

A summary is rebuilt only when its fingerprint changes: a hash of the aggregate statistics,
the model version and whether an LLM is configured (adding a Groq key later upgrades every
template summary on the next run). Below MIN_RESPONSES_FOR_DISPLAY no summary is kept.
"""

import hashlib
import json
import logging
import time
from typing import Any

from app.config import get_settings
from app.nlp import summarize
from app.utils import now

log = logging.getLogger("facultylens.summaries")


def fingerprint(stats: dict[str, Any], model_version: str) -> str:
    payload = {
        "stats": stats,
        "model_version": model_version,
        "llm": get_settings().llm_configured,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def refresh_form(sync_db, form: dict[str, Any], model_version: str, force: bool = False) -> str:
    """Rebuild one form's summary if needed. Returns "built", "kept", "removed" or "skipped"."""
    if form.get("type") != "teaching":
        return "skipped"
    aggregate = sync_db.aggregates.find_one({"form_id": form["_id"]})
    stats = (aggregate or {}).get("stats") or {}
    if (
        not aggregate
        or aggregate.get("model_version") != model_version
        or stats.get("responses", 0) < get_settings().min_responses_for_display
        or not stats.get("analysed")
    ):
        removed = sync_db.summaries.delete_one({"form_id": form["_id"]}).deleted_count
        return "removed" if removed else "skipped"

    print_ = fingerprint(stats, model_version)
    existing = sync_db.summaries.find_one({"form_id": form["_id"]}, {"fingerprint": 1, "engine": 1})
    outage_template = (
        existing is not None
        and existing.get("engine") == "fallback"
        and get_settings().llm_configured
    )
    if existing and existing.get("fingerprint") == print_ and not force and not outage_template:
        return "kept"

    started = time.perf_counter()
    result = summarize.summarise(stats)
    sync_db.summaries.update_one(
        {"form_id": form["_id"]},
        {
            "$set": {
                "form_id": form["_id"],
                "faculty_id": form.get("faculty_id"),
                "course_id": form["course_id"],
                "cycle_id": form["cycle_id"],
                "fingerprint": print_,
                "model_version": model_version,
                **result,
                "seconds": round(time.perf_counter() - started, 2),
                "generated_at": now(),
            }
        },
        upsert=True,
    )
    return "built"


def refresh_forms(sync_db, forms: list[dict[str, Any]], model_version: str) -> dict[str, int]:
    """Refresh several forms; one failure never stops the rest (or the analysis job)."""
    counts: dict[str, int] = {}
    for form in forms:
        try:
            outcome = refresh_form(sync_db, form, model_version)
        except Exception:
            log.exception("summary for form %s failed", form.get("_id"))
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts
