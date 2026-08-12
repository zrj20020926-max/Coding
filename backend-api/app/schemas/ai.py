from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.ai import AIAnalysisStatus


class AIAnalysisPublic(BaseModel):
    id: UUID
    submission_id: UUID
    status: AIAnalysisStatus
    failure_reason: Optional[str]
    time_complexity: Optional[str]
    space_complexity: Optional[str]
    suggestions: list[str]
    guiding_questions: list[str]
    confidence: Optional[Literal["low", "medium", "high"]]
    cached: bool
    retry_count: int
    error_code: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class AIQuotaPublic(BaseModel):
    limit: int
    remaining: int
    reset_after_seconds: int


class AIAnalysisTriggered(BaseModel):
    analysis: AIAnalysisPublic
    quota: Optional[AIQuotaPublic]
    reused: bool
