import hashlib
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.models import (
    CompileResult,
    SubmissionJob,
    SubmissionStatus,
)
from app.domain.models import TestCase as JudgeTestCase
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

    async def compile(self, _language: str, _source: bytes) -> CompileResult:
        return CompileResult(True)

    async def run_case(self, *_args) -> SandboxRunResult:
        return SandboxRunResult(self.status, self.actual, 10, 100, 0)


def fixture(
    actual: bytes, expected: bytes
) -> tuple[JudgeEngine, SubmissionJob, list[JudgeTestCase]]:
    source = b"print('answer')"
    stdin = b"hidden input"
    store = FakeObjectStore(source, stdin, expected)
    job = SubmissionJob(
        id=uuid4(),
        problem_id=1,
        language="python",
        status=SubmissionStatus.COMPILING,
        source_object_key="private/source",
        source_checksum=hashlib.sha256(source).hexdigest(),
        time_limit_ms=1000,
        memory_limit_mb=64,
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
