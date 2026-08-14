import hashlib
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.models import (
    CheckerType,
    CompileResult,
    SubmissionJob,
    SubmissionMode,
    SubmissionStatus,
)
from app.domain.models import TestCase as JudgeTestCase
from app.errors import JudgeConfigurationError
from app.infrastructure.sandbox import SandboxRunResult
from app.judge import JudgeEngine


class FakeObjectStore:
    def __init__(self, source: bytes, stdin: bytes, expected: bytes) -> None:
        self.source = source
        self.stdin = stdin
        self.expected = expected

    async def get_source(self, _key: str) -> bytes:
        return self.source

    async def get_test_input(self, _key: str) -> bytes:
        return self.stdin

    async def get_test_output(self, _key: str) -> bytes:
        return self.expected


class FakeSandbox:
    def __init__(self, actual: bytes, status: SubmissionStatus = SubmissionStatus.ACCEPTED) -> None:
        self.actual = actual
        self.status = status
        self.compiled_language: str | None = None
        self.executed_language: str | None = None

    async def compile(self, language: str, _source: bytes) -> CompileResult:
        self.compiled_language = language
        return CompileResult(True)

    async def run_case(self, language: str, *_args) -> SandboxRunResult:
        self.executed_language = language
        return SandboxRunResult(self.status, self.actual, 10, 100, 0)


def fixture(
    actual: bytes, expected: bytes
) -> tuple[JudgeEngine, SubmissionJob, list[JudgeTestCase]]:
    source = b"console.log('answer')"
    stdin = b"hidden input"
    store = FakeObjectStore(source, stdin, expected)
    job = SubmissionJob(
        id=uuid4(),
        problem_id=1,
        language="nodejs",
        status=SubmissionStatus.COMPILING,
        mode=SubmissionMode.JUDGE,
        test_set_id=uuid4(),
        problem_version=1,
        source_object_key="private/source",
        source_checksum=hashlib.sha256(source).hexdigest(),
        time_limit_ms=1000,
        memory_limit_mb=64,
        checker_type=CheckerType.EXACT,
    )
    test_case = JudgeTestCase(
        id=uuid4(),
        input_object_key="private/input",
        output_object_key="private/output",
        checksum=hashlib.sha256(stdin + b"\0" + expected).hexdigest(),
        score=Decimal("100"),
        sequence=1,
    )
    return JudgeEngine(store, FakeSandbox(actual)), job, [test_case]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_judge_accepts_normalized_output_without_persisting_content() -> None:
    engine, job, cases = fixture(b"answer  \r\n", b"answer\n")
    result = await engine.judge(job, cases)

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.case_results[0].status is SubmissionStatus.ACCEPTED
    assert not hasattr(result.case_results[0], "stdout")
    assert not hasattr(result.case_results[0], "expected")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_judge_stops_after_wrong_answer_without_exposing_hidden_data() -> None:
    engine, job, cases = fixture(b"wrong", b"secret expected")
    result = await engine.judge(job, cases)

    assert result.status is SubmissionStatus.WRONG_ANSWER
    assert result.error_message is None
    assert "secret" not in repr(result)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sample_run_uses_inline_public_case_without_hidden_object_reads() -> None:
    engine, job, _cases = fixture(b"answer\n", b"answer\n")
    stdin = b"public input\n"
    expected = b"answer\n"
    sample = JudgeTestCase(
        id=uuid4(),
        input_object_key=None,
        output_object_key=None,
        checksum=hashlib.sha256(stdin + b"\0" + expected).hexdigest(),
        score=Decimal("100"),
        sequence=0,
        inline_input=stdin,
        inline_output=expected,
    )

    result = await engine.judge(
        replace(job, mode=SubmissionMode.SAMPLE),
        [sample],
    )

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.total_case_count == 1
    assert result.public_output == "answer\n"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_token_and_float_checkers_use_submission_snapshot() -> None:
    engine, job, cases = fixture(b"1   2\n", b"1 2\n")
    token_result = await engine.judge(
        replace(job, checker_type=CheckerType.TOKEN),
        cases,
    )
    assert token_result.status is SubmissionStatus.ACCEPTED

    float_engine, float_job, float_cases = fixture(b"1.0009\n", b"1.0\n")
    float_result = await float_engine.judge(
        replace(
            float_job,
            checker_type=CheckerType.FLOAT,
            absolute_tolerance=Decimal("0.001"),
            relative_tolerance=Decimal("0"),
        ),
        float_cases,
    )
    assert float_result.status is SubmissionStatus.ACCEPTED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_group_dependency_short_circuits_and_aggregates_score() -> None:
    engine, job, cases = fixture(b"wrong", b"expected")
    first_group = uuid4()
    second_group = uuid4()
    first = replace(
        cases[0],
        score=Decimal("0"),
        group_id=first_group,
        group_sequence=1,
        group_score=Decimal("40"),
        group_short_circuit=True,
    )
    second = replace(
        cases[0],
        id=uuid4(),
        sequence=2,
        group_id=second_group,
        group_sequence=2,
        group_score=Decimal("60"),
        dependency_group_id=first_group,
    )
    result = await engine.judge(job, [first, second])

    assert result.status is SubmissionStatus.WRONG_ANSWER
    assert len(result.case_results) == 1
    assert result.group_results[0].score == 0
    assert result.group_results[1].skipped is True
    assert result.total_case_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_output_limit_has_dedicated_status() -> None:
    engine, job, cases = fixture(b"", b"expected")
    engine.sandbox.status = SubmissionStatus.OUTPUT_LIMIT_EXCEEDED
    result = await engine.judge(job, cases)
    assert result.status is SubmissionStatus.OUTPUT_LIMIT_EXCEEDED


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["javascript-v8", "nodejs"])
async def test_judge_accepts_both_javascript_modes(language: str) -> None:
    engine, job, cases = fixture(b"answer\n", b"answer\n")

    result = await engine.judge(replace(job, language=language), cases)

    assert result.status is SubmissionStatus.ACCEPTED
    assert engine.sandbox.compiled_language == language
    assert engine.sandbox.executed_language == language


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extra_debug_output_is_wrong_answer() -> None:
    engine, job, cases = fixture(b"answer\ndebug\n", b"answer\n")

    result = await engine.judge(job, cases)

    assert result.status is SubmissionStatus.WRONG_ANSWER


@pytest.mark.unit
@pytest.mark.asyncio
async def test_judge_rejects_disabled_legacy_language() -> None:
    engine, job, cases = fixture(b"answer\n", b"answer\n")

    with pytest.raises(JudgeConfigurationError, match="unsupported language"):
        await engine.judge(replace(job, language="python"), cases)
