"""User schemas. `gender` exists only in admin-facing models (SPEC §7: admin-only, aggregate bias
checks only). Students sign in with a roll number; staff with an email."""

import re
from datetime import datetime
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.config import get_settings

Role = Literal["admin", "hod", "faculty", "student"]
Gender = Literal["female", "male", "other", "undisclosed"]
# Phase 8 labelling: an annotator labels comments blind; an adjudicator settles disagreements.
Annotator = Literal["annotator", "adjudicator"]
NEEDS_DEPARTMENT = {"hod", "faculty", "student"}
MAY_HAVE_GENDER = {"hod", "faculty"}


@lru_cache
def _roll_re(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def normalise_roll_no(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().upper()
    # "2451 24 733 001" or "2451 - 24 - 733 - 001" means 2451-24-733-001, if that is the format.
    hyphenated = re.sub(r"\s*-\s*|\s+", "-", value)
    if hyphenated != value and _roll_re(get_settings().roll_no_regex).fullmatch(hyphenated):
        return hyphenated
    return value or None


def roll_no_problem(value: str) -> str | None:
    if not _roll_re(get_settings().roll_no_regex).fullmatch(value):
        return "Roll number doesn't match the college format (ROLL_NO_REGEX)."
    return None


def role_rule_problems(
    role: str, email: str | None, roll_no: str | None, department: object, gender: str | None
) -> list[str]:
    """Cross-field rules shared by single create, bulk create and edit."""
    problems = []
    if role == "student":
        if not roll_no:
            problems.append("Students need a roll number.")
    else:
        if roll_no:
            problems.append("Only students have a roll number.")
        if not email:
            problems.append("Staff accounts need an email.")
    if role in NEEDS_DEPARTMENT and not department:
        problems.append("This role needs a department.")
    if gender and role not in MAY_HAVE_GENDER:
        problems.append("Gender is recorded for faculty and HoDs only.")
    if roll_no and (msg := roll_no_problem(roll_no)):
        problems.append(msg)
    return problems


class _UserFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    role: Role
    email: EmailStr | None = None
    roll_no: str | None = Field(default=None, max_length=20)
    gender: Gender | None = None

    @field_validator("email")
    @classmethod
    def _lower(cls, v):
        return v.lower() if v else v

    @field_validator("roll_no")
    @classmethod
    def _upper(cls, v):
        return normalise_roll_no(v)


class UserCreate(_UserFields):
    department_id: str | None = None

    @model_validator(mode="after")
    def _rules(self):
        problems = role_rule_problems(
            self.role, self.email, self.roll_no, self.department_id, self.gender
        )
        if problems:
            raise ValueError(" ".join(problems))
        return self


class BulkRow(_UserFields):
    """One row of a bulk upload; the department is given by its code."""

    department_code: str | None = Field(default=None, max_length=12)

    @field_validator("department_code")
    @classmethod
    def _code(cls, v):
        return v.strip().upper() or None if v else None

    @model_validator(mode="after")
    def _rules(self):
        problems = role_rule_problems(
            self.role, self.email, self.roll_no, self.department_code, self.gender
        )
        if problems:
            raise ValueError(" ".join(problems))
        return self


class BulkJson(BaseModel):
    users: list[dict] = Field(min_length=1, max_length=1000)


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    email: EmailStr | None = None
    roll_no: str | None = Field(default=None, max_length=20)
    department_id: str | None = None
    gender: Gender | None = None
    is_active: bool | None = None
    annotator: Annotator | None = None

    @field_validator("email")
    @classmethod
    def _lower(cls, v):
        return v.lower() if v else v

    @field_validator("roll_no")
    @classmethod
    def _upper(cls, v):
        return normalise_roll_no(v)


class UserOut(BaseModel):
    id: str
    role: Role
    name: str
    email: str | None = None
    roll_no: str | None = None
    department_id: str | None = None
    is_active: bool = True
    must_change_pw: bool = False
    created_at: datetime | None = None
    annotator: Annotator | None = None


class UserAdminOut(UserOut):
    gender: Gender | None = None
    last_login_at: datetime | None = None


class UserPage(BaseModel):
    items: list[UserAdminOut] | list[UserOut]
    total: int
    page: int
    page_size: int


class Credential(BaseModel):
    name: str
    role: Role
    email: str | None = None
    roll_no: str | None = None
    temp_password: str


class UserCreated(BaseModel):
    user: UserAdminOut
    temp_password: str
