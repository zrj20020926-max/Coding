from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai import AIAnalysisStatus


class AIDiagnosticFindingPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected: bool
    summary: str = Field(min_length=1, max_length=1000)


class AIAnalysisPublic(BaseModel):
    id: UUID
    submission_id: UUID
    status: AIAnalysisStatus
    runtime_mismatch: Optional[AIDiagnosticFindingPublic]
    input_reading_issue: Optional[AIDiagnosticFindingPublic]
    line_parsing_issue: Optional[AIDiagnosticFindingPublic]
    token_parsing_issue: Optional[AIDiagnosticFindingPublic]
    whitespace_issue: Optional[AIDiagnosticFindingPublic]
    eof_issue: Optional[AIDiagnosticFindingPublic]
    numeric_issue: Optional[AIDiagnosticFindingPublic]
    output_format_issue: Optional[AIDiagnosticFindingPublic]
    performance_issue: Optional[AIDiagnosticFindingPublic]
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
