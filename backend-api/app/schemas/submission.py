from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.submission import SubmissionStatus


class SubmissionCreate(BaseModel):
    problem_id: int = Field(gt=0)
    language: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9+#-]+$")
    source_code: str = Field(min_length=1)


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


class SubmissionPage(BaseModel):
    items: list[SubmissionPublic]
    total: int
    page: int
    page_size: int
    pages: int
