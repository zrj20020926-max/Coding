from dataclasses import replace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.domain.models import (
    JudgeResult,
    SubmissionJob,
    SubmissionMode,
    SubmissionStatus,
)
from app.errors import InfrastructureError
from app.worker import JudgeWorker, MessageDisposition


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, nx=False, px=None, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, _script: str, _keys: int, key: str, token: str, *args):
        if self.values.get(key) != token:
            return 0
        if args:
            return 1
        self.values.pop(key, None)
        return 1


class FakeRepository:
    def __init__(self, job: SubmissionJob) -> None:
        self.job = job
        self.finalize_calls = 0

    async def load_submission(self, _submission_id):
        return self.job

    async def load_test_cases(self, _job):
        return [object()]

    async def transition(self, _submission_id, expected, next_status):
        if self.job.status is not expected:
            return False
        self.job = replace(self.job, status=next_status)
        return True

    async def finalize(self, _submission_id, expected, result):
        self.finalize_calls += 1
        if self.job.status is not expected:
            return False
        self.job = replace(self.job, status=result.status)
        return True


class FakeEngine:
    def __init__(self, fail=False) -> None:
        self.calls = 0
        self.fail = fail

    async def judge(self, _job, _cases):
        self.calls += 1
        if self.fail:
            raise InfrastructureError("Docker temporarily unavailable")
        return JudgeResult(SubmissionStatus.ACCEPTED, total_case_count=1)


def pending_job():
    return SubmissionJob(
        id=uuid4(),
        problem_id=1,
        language="python",
        status=SubmissionStatus.PENDING,
        mode=SubmissionMode.JUDGE,
        source_object_key="internal",
        source_checksum="0" * 64,
        time_limit_ms=1000,
        memory_limit_mb=64,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_duplicate_submission_message_executes_only_once() -> None:
    job = pending_job()
    repository = FakeRepository(job)
    engine = FakeEngine()
    worker = JudgeWorker(Settings(_env_file=None), FakeRedis(), repository, engine)

    assert await worker.process_submission(job.id) is MessageDisposition.ACK
    assert await worker.process_submission(job.id) is MessageDisposition.ACK
    assert engine.calls == 1
    assert repository.finalize_calls == 1
    assert repository.job.status is SubmissionStatus.ACCEPTED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_infrastructure_failure_is_retryable_and_not_finalized() -> None:
    job = pending_job()
    repository = FakeRepository(job)
    engine = FakeEngine(fail=True)
    worker = JudgeWorker(Settings(_env_file=None), FakeRedis(), repository, engine)

    assert await worker.process_submission(job.id) is MessageDisposition.RETRY
    assert repository.job.status is SubmissionStatus.COMPILING
    assert repository.finalize_calls == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_old_worker_cannot_overwrite_a_new_terminal_status() -> None:
    job = replace(pending_job(), status=SubmissionStatus.RUNNING)
    repository = FakeRepository(job)
    engine = FakeEngine()
    worker = JudgeWorker(Settings(_env_file=None), FakeRedis(), repository, engine)

    async def reject_stale(_submission_id, _expected, _result):
        repository.job = replace(repository.job, status=SubmissionStatus.WRONG_ANSWER)
        return False

    repository.finalize = reject_stale
    assert await worker.process_submission(job.id) is MessageDisposition.ACK
    assert repository.job.status is SubmissionStatus.WRONG_ANSWER
