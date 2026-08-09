from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.problem import ProblemDifficulty, ProblemVisibility


class ProblemProgressStatus(str, Enum):
    SOLVED = "solved"
    ATTEMPTED = "attempted"
    UNATTEMPTED = "unattempted"
    FAVORITED = "favorited"


class ProblemSort(str, Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    TITLE = "title"
    DIFFICULTY = "difficulty"
    ACCEPTANCE = "acceptance"


class TagPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str


class LanguagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display_name: str
    version: str
    monaco_language: str
    source_filename: str
    sort_order: int


class ProblemSummary(BaseModel):
    id: int
    slug: str
    title: str
    difficulty: ProblemDifficulty
    source: Optional[str]
    accepted_count: int
    submission_count: int
    tags: list[TagPublic]
    solved: Optional[bool] = None
    attempted: Optional[bool] = None
    attempt_count: Optional[int] = None
    favorited: Optional[bool] = None

    @computed_field
    @property
    def acceptance_rate(self) -> float:
        if self.submission_count == 0:
            return 0.0
        return round(self.accepted_count * 100 / self.submission_count, 2)


class ProblemDetail(ProblemSummary):
    description: str
    input_description: str
    output_description: str
    sample_input: str
    sample_output: str
    time_limit_ms: int
    memory_limit_mb: int
    created_at: datetime
    updated_at: datetime


class ProblemPage(BaseModel):
    items: list[ProblemSummary]
    total: int
    page: int
    page_size: int
    pages: int


class ProblemWriteBase(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    difficulty: ProblemDifficulty
    input_description: str = Field(min_length=1)
    output_description: str = Field(min_length=1)
    sample_input: str = ""
    sample_output: str = ""
    time_limit_ms: int = Field(default=1000, ge=100, le=30000)
    memory_limit_mb: int = Field(default=256, ge=16, le=2048)
    source: Optional[str] = Field(default=None, max_length=200)
    tag_slugs: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("tag_slugs")
    @classmethod
    def unique_tag_slugs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("tag_slugs must not contain duplicates")
        return value


class ProblemCreate(ProblemWriteBase):
    visibility: ProblemVisibility = ProblemVisibility.DRAFT


class ProblemUpdate(BaseModel):
    slug: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1)
    difficulty: Optional[ProblemDifficulty] = None
    input_description: Optional[str] = Field(default=None, min_length=1)
    output_description: Optional[str] = Field(default=None, min_length=1)
    sample_input: Optional[str] = None
    sample_output: Optional[str] = None
    time_limit_ms: Optional[int] = Field(default=None, ge=100, le=30000)
    memory_limit_mb: Optional[int] = Field(default=None, ge=16, le=2048)
    source: Optional[str] = Field(default=None, max_length=200)
    tag_slugs: Optional[list[str]] = Field(default=None, max_length=30)

    @field_validator("tag_slugs")
    @classmethod
    def unique_optional_tag_slugs(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("tag_slugs must not contain duplicates")
        return value


class AdminProblem(ProblemDetail):
    visibility: ProblemVisibility
    created_by: Optional[str]
