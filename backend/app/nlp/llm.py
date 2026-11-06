"""Every LLM call goes through here (CLAUDE.md rule 3).

`complete_json()` asks Groq for a JSON object and validates it with a Pydantic model. It never
raises: with no key, Groq down, a timeout or output that fails validation twice it returns
(None, meta) and the caller uses its own no-LLM path. The SDK retries 429/5xx with backoff
itself (max_retries); a decommissioned or unknown model switches to GROQ_FALLBACK_MODEL.
"""

import json
import logging
import re
import threading
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.utils import now

log = logging.getLogger("facultylens.llm")


_client = None
_client_key: str | None = None
_lock = threading.Lock()
_status: dict[str, Any] = {"last_model": None, "last_error": None, "last_at": None, "calls": 0}


def _get_client():
    """One Groq client per key, created on first use (the SDK import stays out of start-up)."""
    global _client, _client_key
    settings = get_settings()
    with _lock:
        if _client is None or _client_key != settings.groq_api_key:
            from groq import Groq

            _client = Groq(
                api_key=settings.groq_api_key,
                timeout=settings.llm_timeout_seconds,
                max_retries=2,
            )
            _client_key = settings.groq_api_key
        return _client


def _model_gone(exc: Exception) -> bool:
    """Model not found or decommissioned: worth trying the fallback model."""
    import groq

    if isinstance(exc, groq.NotFoundError):
        return True
    if isinstance(exc, groq.BadRequestError):
        text = str(exc).lower()
        return any(k in text for k in ("decommission", "model_not_found", "does not exist"))
    return False


def _record(model: str | None, error: str | None) -> None:
    _status.update(last_model=model, last_error=error, last_at=now().isoformat())
    _status["calls"] += 1


MAX_RATE_LIMIT_WAIT = 30.0  # seconds in total per call, before using the no-LLM fallback


def rate_limit_wait(message: str) -> float:
    """Seconds to wait from Groq's "Please try again in 3.825s" (or 1m2s); 10 s if absent."""
    match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", message)
    if not match:
        return 10.0
    return min(int(match.group(1) or 0) * 60 + float(match.group(2)) + 0.5, MAX_RATE_LIMIT_WAIT)


def _chat(model: str, messages: list[dict[str, str]]) -> str:
    response = _get_client().chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        reasoning_effort="low",
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def complete_json[T: BaseModel](
    system: str, user: str, schema: type[T]
) -> tuple[T | None, dict[str, Any]]:
    settings = get_settings()
    if not settings.llm_configured:
        return None, {"engine": "fallback", "reason": "no_key"}

    import groq

    started = time.perf_counter()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    models = [settings.groq_model, settings.groq_fallback_model]
    model_index, attempts, waited = 0, 0, 0.0
    error: str | None = None
    while attempts < 2 and model_index < len(models):
        model = models[model_index]
        try:
            raw = _chat(model, messages)
        except groq.RateLimitError as exc:
            # The free tier allows a few thousand tokens a minute; a batch of summaries goes over
            # it. Wait as long as Groq asks (bounded), then try again before falling back.
            pause = rate_limit_wait(str(exc))
            if waited + pause <= MAX_RATE_LIMIT_WAIT:
                log.info("Groq rate limit; waiting %.1f s", pause)
                time.sleep(pause)
                waited += pause
                continue
            error = f"{type(exc).__name__}: {exc}"
            log.warning("Groq call failed: %s", error)
            break
        except groq.APIError as exc:
            if _model_gone(exc) and model_index == 0:
                log.warning("Groq model %s unavailable (%s); trying %s", model, exc, models[1])
                model_index += 1
                continue
            error = f"{type(exc).__name__}: {exc}"
            log.warning("Groq call failed: %s", error)
            break
        except Exception as exc:  # never let the LLM take the app down
            error = f"{type(exc).__name__}: {exc}"
            log.exception("Unexpected LLM failure")
            break
        attempts += 1
        try:
            parsed = schema.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            error = f"invalid output: {str(exc)[:200]}"
            messages = [
                *messages,
                {"role": "assistant", "content": raw[:4000]},
                {
                    "role": "user",
                    "content": "That was not valid. Reply with one JSON object that matches "
                    f"the requested fields exactly. Problem: {str(exc)[:300]}",
                },
            ]
            continue
        _record(model, None)
        return parsed, {
            "engine": f"groq:{model}",
            "latency_ms": round(1000 * (time.perf_counter() - started)),
        }
    _record(models[min(model_index, len(models) - 1)], error)
    return None, {"engine": "fallback", "reason": "llm_failed", "error": error}


def llm_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "configured": settings.llm_configured,
        "model": settings.groq_model,
        "fallback_model": settings.groq_fallback_model,
        **_status,
    }
