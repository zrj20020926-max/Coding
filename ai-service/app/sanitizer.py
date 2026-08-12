import re
from typing import Any

from app.core.config import Settings
from app.domain import AnalysisJob

REDACTION_RULES = (
    (re.compile(r"(?i)\b(?:bearer\s+)?eyJ[a-zA-Z0-9_.-]{20,}"), "[REDACTED_TOKEN]"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|secret|password|passwd|token|authorization)\s*[:=]\s*['\"]?[^\s'\"]+"
        ),
        r"\1=[REDACTED_SECRET]",
    ),
    (re.compile(r"(?i)\b(?:s3|minio)://[^\s]+"), "[REDACTED_OBJECT_LOCATION]"),
    (re.compile(r"https?://[^\s'\"<>]+"), "[REDACTED_URL]"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}\b"), "[REDACTED_ID]"),
    (re.compile(r"(?<!\w)[A-Za-z]:\\(?:[^\s\\]+\\)*[^\s]*"), "[REDACTED_PATH]"),
    (re.compile(r"(?<!\w)/(?:tmp|var|home|root|workspace|app)/[^\s]*"), "[REDACTED_PATH]"),
)


def sanitize_text(value: str | None, limit: int) -> str:
    text = (value or "").replace("\x00", "")
    for pattern, replacement in REDACTION_RULES:
        text = pattern.sub(replacement, text)
    if len(text) > limit:
        return text[:limit] + "\n[TRUNCATED]"
    return text


def build_safe_input(job: AnalysisJob, source_code: str, settings: Settings) -> dict[str, Any]:
    problem = {
        "title": sanitize_text(job.problem_title, 500),
        "description": sanitize_text(job.problem_description, settings.max_problem_chars),
        "input_description": sanitize_text(job.input_description, 8000),
        "output_description": sanitize_text(job.output_description, 8000),
        "sample_input": sanitize_text(job.sample_input, 8000),
        "sample_output": sanitize_text(job.sample_output, 8000),
        "time_limit_ms": job.time_limit_ms,
        "memory_limit_mb": job.memory_limit_mb,
    }
    return {
        "problem": problem,
        "language": sanitize_text(job.language_slug, 50),
        "source_code": sanitize_text(source_code, settings.max_source_chars),
        "compiler_output": sanitize_text(
            job.compiler_output, settings.max_compiler_output_chars
        ),
        "failure_summary": {
            "status": job.submission_status,
            "time_used_ms": job.time_used_ms,
            "memory_used_kb": job.memory_used_kb,
            "passed_case_count": job.passed_case_count,
            "total_case_count": job.total_case_count,
        },
    }
