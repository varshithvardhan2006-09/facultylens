"""app/nlp/llm.py with a fake Groq: validation, repair, model fallback, never raising."""

import httpx
import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.nlp import llm


class Out(BaseModel):
    answer: str


def _status_error(cls, status, message):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=request), body=None)


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def fake_chat(monkeypatch, replies):
    """Each reply is a string (returned) or an exception (raised); records the models asked."""
    calls = []

    def _chat(model, messages):
        calls.append(model)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm, "_chat", _chat)
    return calls


def test_no_key_never_calls_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    calls = fake_chat(monkeypatch, [])
    out, meta = llm.complete_json("s", "u", Out)
    assert out is None and meta["engine"] == "fallback" and meta["reason"] == "no_key"
    assert calls == []


def test_valid_json(keyed, monkeypatch):
    calls = fake_chat(monkeypatch, ['{"answer": "yes"}'])
    out, meta = llm.complete_json("s", "u", Out)
    assert out.answer == "yes" and meta["engine"] == "groq:openai/gpt-oss-120b"
    assert calls == ["openai/gpt-oss-120b"]


def test_invalid_json_is_repaired_once(keyed, monkeypatch):
    fake_chat(monkeypatch, ["not json", '{"answer": "fixed"}'])
    out, _ = llm.complete_json("s", "u", Out)
    assert out.answer == "fixed"


def test_invalid_twice_falls_back(keyed, monkeypatch):
    fake_chat(monkeypatch, ['{"wrong": 1}', '{"wrong": 2}'])
    out, meta = llm.complete_json("s", "u", Out)
    assert out is None and meta["reason"] == "llm_failed"


def test_decommissioned_model_switches_to_fallback(keyed, monkeypatch):
    import groq

    gone = _status_error(groq.BadRequestError, 400, "The model has been decommissioned")
    calls = fake_chat(monkeypatch, [gone, '{"answer": "ok"}'])
    out, meta = llm.complete_json("s", "u", Out)
    assert out.answer == "ok" and meta["engine"] == "groq:openai/gpt-oss-20b"
    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]


@pytest.mark.parametrize("kind", ["timeout", "server", "ratelimit", "boom"])
def test_failures_return_none(keyed, monkeypatch, kind):
    import groq

    request = httpx.Request("POST", "https://api.groq.com")
    error = {
        "timeout": groq.APITimeoutError(request=request),
        "server": _status_error(groq.InternalServerError, 503, "down"),
        "ratelimit": _status_error(groq.RateLimitError, 429, "slow down"),
        "boom": RuntimeError("unexpected"),
    }[kind]
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)
    fake_chat(monkeypatch, [error] * (4 if kind == "ratelimit" else 1))
    out, meta = llm.complete_json("s", "u", Out)
    assert out is None and meta["engine"] == "fallback" and meta["error"]
    assert llm.llm_status()["last_error"]


def test_rate_limit_wait_reads_groqs_hint():
    assert llm.rate_limit_wait("Please try again in 3.825s. Need more tokens?") == 4.325
    assert llm.rate_limit_wait("try again in 1m2.5s") == llm.MAX_RATE_LIMIT_WAIT  # capped
    assert llm.rate_limit_wait("slow down") == 10.0


def test_rate_limit_waits_then_succeeds(keyed, monkeypatch):
    import groq

    slept = []
    monkeypatch.setattr(llm, "_sleep", slept.append)
    limit = _status_error(groq.RateLimitError, 429, "Please try again in 3.825s.")
    calls = fake_chat(monkeypatch, [limit, '{"answer": "ok"}'])
    out, meta = llm.complete_json("s", "u", Out)
    assert out.answer == "ok" and meta["engine"].startswith("groq:")
    assert slept == [4.325] and len(calls) == 2


def test_rate_limit_gives_up_after_the_cap(keyed, monkeypatch):
    import groq

    slept = []
    monkeypatch.setattr(llm, "_sleep", slept.append)
    limits = [_status_error(groq.RateLimitError, 429, "slow down") for _ in range(5)]
    fake_chat(monkeypatch, limits)
    out, meta = llm.complete_json("s", "u", Out)
    assert out is None and meta["engine"] == "fallback" and "RateLimitError" in meta["error"]
    assert sum(slept) <= llm.MAX_RATE_LIMIT_WAIT and len(slept) == 3
