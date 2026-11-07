"""Departments and course offerings (code + academic year + semester + section)."""

import re

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.users import normalise_roll_no

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")


class DepartmentIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=12)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.upper()
        if not re.fullmatch(r"[A-Z0-9]{2,12}", v):
            raise ValueError("Use 2-12 letters or digits, e.g. CSE.")
        return v


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=120)


class DepartmentOut(BaseModel):
    id: str
    name: str
    code: str


class CourseIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=160)
    department_id: str
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2026-27"])
    semester: int = Field(ge=1, le=8)
    section: str = Field(min_length=1, max_length=4)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.upper()
        if not _CODE.fullmatch(v):
            raise ValueError("Use letters, digits and hyphens, e.g. CS501.")
        return v

    @field_validator("section")
    @classmethod
    def _section(cls, v: str) -> str:
        v = v.upper()
        if not v.isalnum():
            raise ValueError("Section is letters or digits, e.g. A.")
        return v

    @field_validator("academic_year")
    @classmethod
    def _year(cls, v: str) -> str:
        start, end = int(v[:4]), int(v[5:])
        if (start + 1) % 100 != end:
            raise ValueError("Academic year runs over consecutive years, e.g. 2026-27.")
        return v


class CourseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=160)


class EnrolIn(BaseModel):
    add_roll_numbers: list[str] = Field(default_factory=list, max_length=500)
    remove_roll_numbers: list[str] = Field(default_factory=list, max_length=500)
    faculty_ids: list[str] | None = Field(default=None, max_length=10)

    @field_validator("faculty_ids")
    @classmethod
    def _ids(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and not all(ObjectId.is_valid(i) for i in v):
            raise ValueError("Each teacher must be an id from the user list.")
        return v

    @field_validator("add_roll_numbers", "remove_roll_numbers")
    @classmethod
    def _norm(cls, v: list[str]) -> list[str]:
        return sorted({r for r in (normalise_roll_no(x) for x in v) if r})


class PersonRef(BaseModel):
    id: str
    name: str
    roll_no: str | None = None


class CourseOut(BaseModel):
    id: str
    code: str
    name: str
    department_id: str
    academic_year: str
    semester: int
    section: str
    faculty: list[PersonRef]
    student_count: int


class CourseDetail(CourseOut):
    students: list[PersonRef] | None = None  # admin and the department's HoD only


class EnrolResult(BaseModel):
    course: CourseDetail
    unknown_roll_numbers: list[str]
