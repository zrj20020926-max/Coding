from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass(frozen=True)
class AnalysisJob:
    analysis_id: UUID
    submission_id: UUID
    user_id: UUID
    status: str
    source_object_key: str
    submission_status: str
    compiler_output: str | None
    error_message: str | None
    time_used_ms: int | None
    memory_used_kb: int | None
    passed_case_count: int
    total_case_count: int
    language_slug: str
    problem_title: str
    problem_description: str
    input_description: str
    output_description: str
    sample_input: str
    sample_output: str
    time_limit_ms: int
    memory_limit_mb: int


class AIAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_reason: str = Field(min_length=1, max_length=2000)
    time_complexity: str = Field(min_length=1, max_length=100)
    space_complexity: str = Field(min_length=1, max_length=100)
    suggestions: list[str] = Field(min_length=1, max_length=8)
    guiding_questions: list[str] = Field(min_length=1, max_length=8)
    confidence: Literal["low", "medium", "high"]

    @field_validator("suggestions", "guiding_questions")
    @classmethod
    def validate_list_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 1000 for item in value):
            raise ValueError("items must be non-empty and no longer than 1000 characters")
        return [item.strip() for item in value]


@dataclass(frozen=True)
class ProviderResult:
    output: AIAnalysisOutput
    prompt_tokens: int
    completion_tokens: int
    request_id: str | None
    latency_ms: int
