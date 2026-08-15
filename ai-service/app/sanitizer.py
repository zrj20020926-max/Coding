import re
from typing import Any

from app.core.config import Settings
from app.domain import AnalysisJob

REDACTION_RULES = (
    (
        re.compile(r"(?i)\b(?:SECRET_HIDDEN_CASE|HIDDEN_(?:INPUT|OUTPUT|TEST_CASE))\b"),
        "[REDACTED_SENSITIVE]",
    ),
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
    exercise = {
        "title": sanitize_text(job.problem_title, 500),
        "description": sanitize_text(job.problem_description, settings.max_problem_chars),
        "input_format": sanitize_text(job.input_description, 8000),
        "output_format": sanitize_text(job.output_description, 8000),
        "public_samples": [
            {
                "stdin": sanitize_text(job.sample_input, 8000),
                "stdout": sanitize_text(job.sample_output, 8000),
            }
        ],
    }
    format_mismatch = job.submission_status == "Wrong Answer"
    if job.submission_status == "Output Limit Exceeded":
        format_summary = "聚合结果显示 stdout 超出平台输出上限；未提供任何测试数据。"
    elif format_mismatch:
        format_summary = "聚合结果显示 stdout 与期望结果不一致；未提供任何测试数据。"
    else:
        format_summary = "聚合结果未直接表明输出格式不匹配。"
    return {
        "exercise": exercise,
        "runtime": sanitize_text(job.language_slug, 50),
        "source_code": sanitize_text(source_code, settings.max_source_chars),
        "execution_error": {
            "compiler_output": sanitize_text(
                job.compiler_output, settings.max_compiler_output_chars
            ),
            "runtime_error": sanitize_text(
                job.error_message, settings.max_failure_message_chars
            ),
        },
        "judge_summary": {
            "status": job.submission_status,
            "format_mismatch": format_mismatch,
            "format_error_summary": format_summary,
        },
    }
