"""Faculty profile data (SPEC §7 inputs). Every list item carries an `id` so that Phase 5 can cite
the exact facts an LLM sentence was grounded on."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Source = Literal["manual", "orcid", "s2"]
PubType = Literal["journal", "conference", "book", "chapter", "preprint", "thesis", "other"]
AchievementKind = Literal["award", "patent", "funded_project", "certification", "fdp", "other"]
ImportKind = Literal["publication", "experience", "qualification", "interest"]

MAX_YEAR = datetime.now(UTC).year + 1
Year = Field(default=None, ge=1900, le=MAX_YEAR)


class _Item(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id: str | None = Field(default=None, max_length=40)
    source: Source = "manual"


class Qualification(_Item):
    degree: str = Field(min_length=1, max_length=120)
    specialisation: str | None = Field(default=None, max_length=160)
    institution: str = Field(min_length=1, max_length=200)
    year: int | None = Year


class Experience(_Item):
    role: str = Field(min_length=1, max_length=160)
    institution: str = Field(min_length=1, max_length=200)
    department: str | None = Field(default=None, max_length=160)
    from_year: int | None = Year
    to_year: int | None = Year

    @model_validator(mode="after")
    def _order(self):
        if self.from_year and self.to_year and self.to_year < self.from_year:
            raise ValueError("The end year is before the start year.")
        return self


class Publication(_Item):
    title: str = Field(min_length=1, max_length=500)
    venue: str | None = Field(default=None, max_length=300)
    year: int | None = Year
    type: PubType = "other"
    doi: str | None = Field(default=None, max_length=200)
    authors: list[str] = Field(default_factory=list, max_length=50)
    citations: int | None = Field(default=None, ge=0)
    tldr: str | None = Field(default=None, max_length=600)
    url: str | None = Field(default=None, max_length=500)
    s2_paper_id: str | None = Field(default=None, max_length=60)

    @field_validator("authors")
    @classmethod
    def _authors(cls, v: list[str]) -> list[str]:
        return [a.strip()[:120] for a in v if a and a.strip()]

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        if v and not v.startswith(("https://", "http://")):
            raise ValueError("Links must start with https://")
        return v or None


class Achievement(_Item):
    kind: AchievementKind = "award"
    title: str = Field(min_length=1, max_length=300)
    detail: str | None = Field(default=None, max_length=1000)
    year: int | None = Year


class ProfileDataIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    designation: str | None = Field(default=None, max_length=120)
    photo_url: str | None = Field(default=None, max_length=500)
    interests: list[str] = Field(default_factory=list, max_length=30)
    qualifications: list[Qualification] = Field(default_factory=list, max_length=20)
    experience: list[Experience] = Field(default_factory=list, max_length=40)
    publications: list[Publication] = Field(default_factory=list, max_length=1000)
    achievements: list[Achievement] = Field(default_factory=list, max_length=200)

    @field_validator("photo_url")
    @classmethod
    def _photo(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://"):
            raise ValueError("The photo link must start with https://")
        return v or None

    @field_validator("interests")
    @classmethod
    def _interests(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for tag in v:
            tag = " ".join(tag.split())[:60]
            if tag and tag.lower() not in {t.lower() for t in out}:
                out.append(tag)
        return out


ITEM_MODELS: dict[str, type[BaseModel]] = {
    "publication": Publication,
    "experience": Experience,
    "qualification": Qualification,
}


class PendingImport(BaseModel):
    id: str
    kind: ImportKind
    source: Literal["orcid", "s2"]
    data: dict[str, Any]
    fetched_at: datetime | None = None


class ImportLog(BaseModel):
    at: datetime
    added: int
    skipped: int
    enriched: int = 0
    ref: str | None = None


class CourseRef(BaseModel):
    id: str
    code: str
    name: str
    academic_year: str
    semester: int
    section: str


class FacultySummary(BaseModel):
    id: str
    name: str
    role: str
    email: str | None = None
    department_id: str | None = None
    department_code: str | None = None
    department_name: str | None = None


class ProfileDataOut(ProfileDataIn):
    user: FacultySummary
    courses_taught: list[CourseRef]
    orcid: str | None = None
    s2_author_id: str | None = None
    pending_imports: list[PendingImport] = Field(default_factory=list)
    import_log: dict[str, ImportLog] = Field(default_factory=dict)
    updated_at: datetime | None = None
    can_edit: bool = False


class OrcidImportIn(BaseModel):
    orcid: str = Field(min_length=15, max_length=120)


class S2ImportIn(BaseModel):
    author: str = Field(min_length=1, max_length=200, description="Author ID or profile link")


class AcceptIn(BaseModel):
    data: dict[str, Any] | None = None


class BulkDecisionIn(BaseModel):
    accept: list[str] = Field(default_factory=list, max_length=1000)
    reject: list[str] = Field(default_factory=list, max_length=1000)


class ImportResult(BaseModel):
    added: dict[str, int]
    skipped: int
    enriched: int
    profile: ProfileDataOut
