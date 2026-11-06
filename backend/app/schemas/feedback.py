from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.feedback_spec import MAX_TEXT
from app.utils import CONTROL_CHARS

Term = Literal["odd", "even"]
FormType = Literal["teaching", "curriculum"]
CycleStatus = Literal["draft", "open", "closed"]


class CycleIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=80, examples=["2026-27 Odd Sem"])
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    term: Term
    opens_at: datetime
    closes_at: datetime

    @field_validator("opens_at", "closes_at")
    @classmethod
    def _with_timezone(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    @model_validator(mode="after")
    def _dates(self):
        start, end = int(self.academic_year[:4]), int(self.academic_year[5:])
        if (start + 1) % 100 != end:
            raise ValueError("Academic year runs over consecutive years, e.g. 2026-27.")
        if self.closes_at <= self.opens_at:
            raise ValueError("The closing date must be after the opening date.")
        return self


class CycleCounts(BaseModel):
    teaching_forms: int
    curriculum_forms: int
    responses: int
    eligible: int
    response_rate: float | None


class CycleOut(BaseModel):
    id: str
    name: str
    academic_year: str
    term: Term
    opens_at: datetime
    closes_at: datetime
    status: CycleStatus
    published_at: datetime | None = None
    closed_at: datetime | None = None
    counts: CycleCounts | None = None


class PreviewOut(BaseModel):
    offerings: int
    teaching_forms: int
    curriculum_forms: int
    already_created: int
    without_teacher: list[str]


class Person(BaseModel):
    id: str
    name: str


class CourseBrief(BaseModel):
    id: str
    code: str
    name: str
    academic_year: str
    semester: int
    section: str
    department_id: str


class CycleBrief(BaseModel):
    id: str
    name: str
    status: CycleStatus
    opens_at: datetime
    closes_at: datetime


class Question(BaseModel):
    key: str
    label: str
    text: str
    kind: Literal["likert", "text"]


class FormOut(BaseModel):
    id: str
    type: FormType
    cycle: CycleBrief
    course: CourseBrief
    faculty: Person | None = None
    questions: list[Question]
    submitted: bool | None = None  # students only
    responses: int | None = None  # staff only
    eligible: int | None = None  # staff only


class MyForm(BaseModel):
    id: str
    type: FormType
    cycle: CycleBrief
    course: CourseBrief
    faculty: Person | None = None
    submitted: bool


class ResponseIn(BaseModel):
    """Ratings 1-5 for every question key; free text optional, at most 2,000 characters."""

    likert: dict[str, int]
    texts: dict[str, str | None] = Field(default_factory=dict)

    @field_validator("likert")
    @classmethod
    def _range(cls, v: dict[str, int]) -> dict[str, int]:
        for key, value in v.items():
            if not 1 <= value <= 5:
                raise ValueError(f"Rating for {key} must be between 1 and 5.")
        return v

    @field_validator("texts")
    @classmethod
    def _texts(cls, v: dict[str, str | None]) -> dict[str, str | None]:
        out = {}
        for key, value in v.items():
            text = " ".join(CONTROL_CHARS.sub("", value or "").split())
            if len(text) > MAX_TEXT:
                raise ValueError(f"Keep each answer under {MAX_TEXT} characters.")
            out[key] = text or None
        return out


class FormStats(BaseModel):
    form_id: str
    cycle: CycleBrief
    course: CourseBrief
    responses: int
    eligible: int
    min_required: int
    visible: bool
    likert_means: dict[str, float] | None = None
    comments: list[dict] = Field(default_factory=list)
    comments_status: Literal["hidden_below_minimum", "awaiting_analysis", "available"]
