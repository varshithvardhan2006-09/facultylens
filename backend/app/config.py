"""Application settings, read from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "FacultyLens"
    app_version: str = "0.1.0"
    institution_name: str = "Maturi Venkata Subba Rao (MVSR) Engineering College"
    # Who students and staff write to about their data (shown on the privacy notice).
    privacy_contact: str = "the college office"
    frontend_origin: str = "http://localhost:5173"
    api_docs: bool = True  # /docs and /openapi.json; set false on a public deployment
    jwt_secret: str = Field(default="change-me", min_length=8)
    jwt_access_minutes: int = 60
    jwt_refresh_days: int = 7
    student_hash_salt: str = Field(default="change-me", min_length=8)
    roll_no_regex: str = r"\b\d{4}-\d{2}-\d{3}-\d{3}\b"
    min_responses_for_display: int = Field(default=5, ge=1)
    analysis_on_submit: bool = True  # queue each new response for background analysis
    demo_password: str = Field(default="facultylens-demo", min_length=8)

    # ---- Auth ----
    login_rate_limit: str = "30/minute"  # per address; a campus shares one
    refresh_cookie_name: str = "fl_refresh"
    cookie_secure: bool = False  # set true when served over HTTPS
    bcrypt_rounds: int = Field(default=12, ge=4, le=15)

    # ---- Database ----
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "facultylens"

    # ---- ML (CPU only) ----
    ml_mode: Literal["light", "full"] = "light"
    torch_num_threads: int = Field(default=4, ge=1)
    nlp_batch_size: int = Field(default=16, ge=1)
    hf_home: str = "./.hf_cache"
    tox_hide: float = 0.70
    tox_review: float = 0.40
    aspect_sim: float = 0.35
    sarc_flag: float = 0.95

    # ---- Bias & sarcasm panel (SPEC §11.7) ----
    bias_min_group_faculty: int = Field(default=3, ge=2)
    bias_min_group_answers: int = Field(default=30, ge=1)

    # ---- LLM ----
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "openai/gpt-oss-20b"
    llm_timeout_seconds: float = 30

    # ---- Profile imports ----
    s2_api_key: str = ""
    import_timeout_seconds: float = Field(default=15, gt=0, le=60)

    @property
    def hf_home_path(self) -> Path:
        """HF cache directory; relative paths are resolved against backend/, not the cwd."""
        path = Path(self.hf_home)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def placeholder_secrets(self) -> list[str]:
        """Secrets still at a shipped placeholder; anyone could forge logins or undo anonymity."""
        secrets = {"JWT_SECRET": self.jwt_secret, "STUDENT_HASH_SALT": self.student_hash_salt}
        return [
            name
            for name, value in secrets.items()
            if value.startswith("change-me") or len(value) < MIN_SECRET_LENGTH
        ]

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
