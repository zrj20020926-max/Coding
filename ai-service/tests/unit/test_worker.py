from uuid import uuid4

import pytest

from app.core.config import Settings
from app.domain import AIAnalysisOutput, ProviderResult
from app.provider import ProviderPermanentError, ProviderTransientError
from app.worker import AIWorker, MessageDisposition
from tests.unit.test_security import make_job


class FakeRepository:
    def __init__(self) -> None:
        self.job = make_job()
        self.status = "pending"
        self.retries = 0
        self.completed = False
        self.failed: tuple[str, str] | None = None

    async def get_status(self, _analysis_id):
        return self.status

    async def claim(self, _analysis_id):
        self.status = "running"
        return True

    async def load_job(self, _analysis_id):
        return self.job

    async def reject_ineligible(self, _analysis_id):
        self.failed = ("ANALYSIS_NOT_ELIGIBLE", "rejected")
        self.status = "failed"

    async def record_retry(self, _analysis_id):
        self.retries += 1

    async def complete(self, _job, _result, _provider, _model, _input_cost, _output_cost):
        self.completed = True
        self.status = "completed"
        return True

    async def fail(self, _job, code, message):
        self.failed = (code, message)
        self.status = "failed"
        return True


class FakeSourceStore:
    async def get_source(self, _object_key):
        return "print(1)"


class RetryProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, _safe_input):
        self.calls += 1
        if self.calls == 1:
            raise ProviderTransientError("timeout")
        return ProviderResult(
            output=AIAnalysisOutput(
                failure_reason="Likely off-by-one error",
                time_complexity="O(n)",
                space_complexity="O(1)",
                suggestions=["Check loop boundaries"],
                guiding_questions=["What happens for n=1?"],
                confidence="medium",
            ),
            prompt_tokens=100,
            completion_tokens=50,
            request_id="provider-request",
            latency_ms=10,
        )


class InvalidProvider:
    async def analyze(self, _safe_input):
        raise ProviderPermanentError("invalid response containing provider internals")


def settings() -> Settings:
    return Settings(
        ai_provider_api_key="test-key",
        ai_retry_base_seconds=0,
        ai_max_retries=2,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_retries_transient_provider_failure_then_completes() -> None:
    repository = FakeRepository()
    provider = RetryProvider()
    worker = AIWorker(settings(), None, repository, FakeSourceStore(), provider)

    disposition = await worker.process_analysis(repository.job.analysis_id)

    assert disposition is MessageDisposition.ACK
    assert provider.calls == 2
    assert repository.retries == 1
    assert repository.completed is True
    assert repository.failed is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_degrades_safely_without_changing_submission_state() -> None:
    repository = FakeRepository()
    original_submission_status = repository.job.submission_status
    worker = AIWorker(settings(), None, repository, FakeSourceStore(), InvalidProvider())

    disposition = await worker.process_analysis(repository.job.analysis_id)

    assert disposition is MessageDisposition.ACK
    assert repository.failed == (
        "AI_RESPONSE_INVALID",
        "AI analysis could not produce a safe structured response",
    )
    assert repository.job.submission_status == original_submission_status


@pytest.mark.unit
@pytest.mark.asyncio
async def test_completed_or_unknown_duplicate_message_is_idempotently_acked() -> None:
    repository = FakeRepository()
    worker = AIWorker(settings(), None, repository, FakeSourceStore(), RetryProvider())
    repository.status = "completed"
    assert await worker.process_analysis(uuid4()) is MessageDisposition.ACK
    repository.status = None
    assert await worker.process_analysis(uuid4()) is MessageDisposition.ACK
