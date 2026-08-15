import pytest

from app.diagnostics import apply_static_diagnostics
from app.domain import AIAnalysisOutput, DiagnosticFinding


def base_output() -> AIAnalysisOutput:
    finding = DiagnosticFinding(detected=False, summary="未发现明确问题。")
    return AIAnalysisOutput(
        runtime_mismatch=finding,
        input_reading_issue=finding,
        line_parsing_issue=finding,
        token_parsing_issue=finding,
        whitespace_issue=finding,
        eof_issue=finding,
        numeric_issue=finding,
        output_format_issue=finding,
        performance_issue=finding,
        suggestions=["核对公开样例。"],
        guiding_questions=["输入边界是否完整覆盖？"],
        confidence="medium",
    )


def diagnose(runtime: str, source: str, description: str = "普通整数输入") -> AIAnalysisOutput:
    return apply_static_diagnostics(
        base_output(),
        {
            "runtime": runtime,
            "source_code": source,
            "exercise": {"description": description},
        },
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("runtime", "source"),
    [
        ("javascript-v8", "const fs = require('fs'); process.stdout.write('x');"),
        ("nodejs", "const line = readline(); print(line);"),
    ],
)
def test_runtime_mismatch_is_detected(runtime: str, source: str) -> None:
    assert diagnose(runtime, source).runtime_mismatch.detected is True


@pytest.mark.unit
def test_trim_multiple_spaces_and_crlf_issues_are_detected() -> None:
    result = diagnose(
        "nodejs",
        "const raw = require('fs').readFileSync(0, 'utf8').trim();\n"
        "const lines = raw.split('\\n');\nconst tokens = lines[0].split(' ');",
        "输入可能为空并包含多个空格和空行",
    )
    assert result.input_reading_issue.detected is True
    assert result.whitespace_issue.detected is True
    assert result.token_parsing_issue.detected is True
    assert result.line_parsing_issue.detected is True


@pytest.mark.unit
def test_eof_cursor_overrun_is_detected() -> None:
    result = diagnose(
        "nodejs",
        "const raw = require('fs').readFileSync(0, 'utf8');\n"
        "const lines = raw.split(/\\r?\\n/); let i = 0; while (true) console.log(lines[i++]);",
    )
    assert result.eof_issue.detected is True


@pytest.mark.unit
def test_bigint_number_mixing_and_precision_are_detected() -> None:
    mixed = diagnose("javascript-v8", "const x = BigInt(readline()); print(x + 1);")
    assert mixed.numeric_issue.detected is True
    unsafe = diagnose(
        "nodejs",
        "const fs = require('fs'); const x = Number(fs.readFileSync(0, 'utf8')); console.log(x);",
        "输入超过 Number 安全整数范围，需要 BigInt",
    )
    assert unsafe.numeric_issue.detected is True


@pytest.mark.unit
def test_output_format_and_large_input_performance_issues_are_detected() -> None:
    result = diagnose(
        "nodejs",
        "const fs = require('fs'); const tokens = fs.readFileSync(0, 'utf8').split(/\\s+/);\n"
        "while (tokens.length) { console.log('debug', tokens.shift()); }",
    )
    assert result.output_format_issue.detected is True
    assert result.performance_issue.detected is True
