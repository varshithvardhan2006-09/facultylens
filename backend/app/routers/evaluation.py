"""Evaluation results (SPEC §8.9) and the faculty usefulness survey (SPEC §8.7).

The results are computed offline by `python -m ml.evaluate` (models and metrics stay out of the
API) and read here from `ml/results/evaluation.json`.
"""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth.deps import AdminUser, Db, User, require_roles
from app.utils import now

router = APIRouter(tags=["evaluation"])
RESULTS_FILE = Path(__file__).resolve().parents[2] / "ml" / "results" / "evaluation.json"
SURVEY_QUESTIONS = ("usefulness", "accuracy", "fairness", "actionability")
Teacher = Annotated[User, Depends(require_roles("faculty", "hod"))]


@router.get("/evaluation/results")
async def results(admin: AdminUser) -> dict[str, Any]:
    if not RESULTS_FILE.exists():
        return {"status": "not_run"}
    return {"status": "ok", **json.loads(RESULTS_FILE.read_text(encoding="utf-8"))}


class SurveyAnswers(BaseModel):
    usefulness: int = Field(ge=1, le=5)
    accuracy: int = Field(ge=1, le=5)
    fairness: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)


class SurveyIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    answers: SurveyAnswers
    comment: str | None = Field(default=None, max_length=2000)


def _survey_out(doc: dict[str, Any] | None) -> dict[str, Any]:
    if not doc:
        return {"answered": False}
    return {
        "answered": True,
        "answers": doc["answers"],
        "comment": doc.get("comment"),
        "updated_at": doc["updated_at"],
    }


@router.post("/survey")
async def answer_survey(body: SurveyIn, db: Db, user: Teacher) -> dict[str, Any]:
    """One answer per teacher; answering again replaces it."""
    doc = {
        "answers": body.answers.model_dump(),
        "comment": body.comment or None,
        "updated_at": now(),
    }
    await db.survey_responses.update_one(
        {"faculty_id": user["_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now()}},
        upsert=True,
    )
    return _survey_out(doc)


@router.get("/survey/mine")
async def my_survey(db: Db, user: Teacher) -> dict[str, Any]:
    return _survey_out(await db.survey_responses.find_one({"faculty_id": user["_id"]}))
