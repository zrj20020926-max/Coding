from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.submission import SubmissionMode, SubmissionStatus


class SubmissionCreate(BaseModel):
    problem_id: int = Field(gt=0)
    language: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9+#-]+$")
    source_code: str = Field(min_length=1)
    mode: SubmissionMode = SubmissionMode.JUDGE


class SubmissionProblemPublic(BaseModel):
    id: int
    slug: str
    title: str


class SubmissionLanguagePublic(BaseModel):
    id: int
    slug: str
    display_name: str
    version: str


class SubmissionPublic(BaseModel):
    id: UUID
    problem: SubmissionProblemPublic
    language: SubmissionLanguagePublic
    status: SubmissionStatus
    mode: SubmissionMode
    time_used_ms: Optional[int]
    memory_used_kb: Optional[int]
    passed_case_count: int
    total_case_count: int
    score: Decimal
    judged_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class SubmissionCreated(SubmissionPublic):
    idempotent_replay: bool


class SubmissionDetail(SubmissionPublic):
    source_code: str
    compiler_output: Optional[str]
    error_message: Optional[str]
    sample_output: Optional[str]
    attempts: list["SubmissionAttemptPublic"] = Field(default_factory=list)


class SubmissionAttemptGroupPublic(BaseModel):
    name: str
    sequence: int
    status: SubmissionStatus
    score: Decimal
    passed_case_count: int
    total_case_count: int
    skipped: bool


class SubmissionAttemptPublic(BaseModel):
    sequence: int
    kind: str
    status: SubmissionStatus
    time_used_ms: Optional[int]
    memory_used_kb: Optional[int]
    passed_case_count: int
    total_case_count: int
    score: Decimal
    judged_at: Optional[datetime]
    groups: list[SubmissionAttemptGroupPublic] = Field(default_factory=list)


class SubmissionPage(BaseModel):
    items: list[SubmissionPublic]
    total: int
    page: int
    page_size: int
    pages: int
