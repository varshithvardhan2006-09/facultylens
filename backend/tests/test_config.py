from pathlib import Path

import pytest

from app.config import BACKEND_DIR, Settings, get_settings
from app.main import create_app


def test_defaults_and_env_override(monkeypatch):
    monkeypatch.setenv("ML_MODE", "full")
    monkeypatch.setenv("TORCH_NUM_THREADS", "2")
    s = Settings(_env_file=None)
    assert s.ml_mode == "full"
    assert s.torch_num_threads == 2


def test_groq_defaults(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    assert Settings(_env_file=None).groq_model == "openai/gpt-oss-120b"


def test_relative_hf_home_resolves_against_backend():
    s = Settings(_env_file=None, hf_home="./.hf_cache")
    assert s.hf_home_path == (BACKEND_DIR / ".hf_cache").resolve()
    assert Settings(_env_file=None, hf_home=str(Path.cwd())).hf_home_path == Path.cwd()


def test_llm_configured_reflects_key():
    assert Settings(_env_file=None, groq_api_key="").llm_configured is False
    assert Settings(_env_file=None, groq_api_key="  ").llm_configured is False
    assert Settings(_env_file=None, groq_api_key="gsk_x").llm_configured is True


def test_placeholder_secrets_are_reported():
    placeholder = Settings(
        _env_file=None,
        jwt_secret="change-me-to-a-long-random-string",
        student_hash_salt="change-me",
    )
    assert placeholder.placeholder_secrets == ["JWT_SECRET", "STUDENT_HASH_SALT"]
    real = Settings(_env_file=None, jwt_secret="a" * 64, student_hash_salt="b" * 64)
    assert real.placeholder_secrets == []


async def test_app_refuses_to_start_with_placeholder_secrets(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "change-me")
    get_settings.cache_clear()
    app = create_app()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        async with app.router.lifespan_context(app):
            pass
