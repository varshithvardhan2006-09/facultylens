"""Liveness and model health. Neither endpoint loads a model."""

import os

import psutil
from fastapi import APIRouter, Response, status

from app import db
from app.auth.deps import AdminUser
from app.config import get_settings
from app.nlp import llm, registry

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(response: Response) -> dict:
    settings = get_settings()
    mongo_ok = await db.ping()
    if not mongo_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if mongo_ok else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "institution": settings.institution_name,
        "privacy_contact": settings.privacy_contact,
        "mongo": "ok" if mongo_ok else "unreachable",
        "ml_mode": settings.ml_mode,
        "llm_configured": settings.llm_configured,
    }


@router.get("/models")
async def models(_: AdminUser) -> dict:
    settings = get_settings()
    proc = psutil.Process(os.getpid())
    rows = registry.status()
    return {
        "ml_mode": settings.ml_mode,
        "model_version": registry.model_version(),
        "torch_num_threads": settings.torch_num_threads,
        "process_rss_mb": round(proc.memory_info().rss / 2**20, 1),
        "system_available_mb": round(psutil.virtual_memory().available / 2**20, 1),
        "loaded_count": sum(r["loaded"] for r in rows),
        "llm": llm.llm_status(),
        "models": rows,
    }
