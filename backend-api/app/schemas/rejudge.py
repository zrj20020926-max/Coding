from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SingleRejudgeCreate(BaseModel):
    submission_id: UUID


class BatchRejudgeCreate(BaseModel):
    problem_id: int = Field(gt=0)
    test_set_id: UUID


class RejudgeTaskPublic(BaseModel):
    id: UUID
    mode: Literal["single", "batch"]
    problem_id: int
    test_set_id: UUID
    status: Literal["queued", "running", "completed", "completed_with_errors"]
    total_count: int
    queued_count: int
    running_count: int
    success_count: int
    failed_count: int
    created_at: datetime


class RejudgeTaskPage(BaseModel):
    items: list[RejudgeTaskPublic]
    total: int
    page: int
    page_size: int
    pages: int
