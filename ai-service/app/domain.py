import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIAGNOSTIC_FIELD_NAMES = (
    "runtime_mismatch",
    "input_reading_issue",
    "line_parsing_issue",
    "token_parsing_issue",
    "whitespace_issue",
    "eof_issue",
    "numeric_issue",
    "output_format_issue",
    "performance_issue",
)
SENSITIVE_OUTPUT_PATTERN = re.compile(
    r"(?i)(?:s3|minio)://|object[_ ]key|source_object_key|hidden_(?:input|output|test)|"
    r"standard_answer|reference_(?:solution|implementation)|docker(?:_image| image| socket)|"
    r"compile_command|api[_-]?key|bearer\s+eyJ"
)


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
    language_slug: str
    problem_title: str
    problem_description: str
    input_description: str
    output_description: str
    sample_input: str
    sample_output: str


class DiagnosticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected: bool
    summary: str = Field(min_length=1, max_length=1000)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        return value.strip()


class AIAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_mismatch: DiagnosticFinding
    input_reading_issue: DiagnosticFinding
    line_parsing_issue: DiagnosticFinding
    token_parsing_issue: DiagnosticFinding
    whitespace_issue: DiagnosticFinding
    eof_issue: DiagnosticFinding
    numeric_issue: DiagnosticFinding
    output_format_issue: DiagnosticFinding
    performance_issue: DiagnosticFinding
    suggestions: list[str] = Field(min_length=1, max_length=8)
    guiding_questions: list[str] = Field(min_length=1, max_length=8)
    confidence: Literal["low", "medium", "high"]

    @field_validator("suggestions", "guiding_questions")
    @classmethod
    def validate_list_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 1000 for item in value):
            raise ValueError("items must be non-empty and no longer than 1000 characters")
        return [item.strip() for item in value]

    @model_validator(mode="after")
    def reject_sensitive_output(self) -> "AIAnalysisOutput":
        if SENSITIVE_OUTPUT_PATTERN.search(self.model_dump_json()):
            raise ValueError("structured diagnosis contains forbidden infrastructure fields")
        return self

    def diagnostic_report(self) -> dict[str, dict[str, object]]:
        return {
            field_name: getattr(self, field_name).model_dump()
            for field_name in DIAGNOSTIC_FIELD_NAMES
        }


@dataclass(frozen=True)
class ProviderResult:
    output: AIAnalysisOutput
    prompt_tokens: int
    completion_tokens: int
    request_id: str | None
    latency_ms: int
