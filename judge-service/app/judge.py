import hashlib

from app.domain.comparison import outputs_equal
from app.domain.models import (
    CaseResult,
    JudgeResult,
    SubmissionJob,
    SubmissionStatus,
    TestCase,
)
from app.errors import InfrastructureError, JudgeConfigurationError
from app.infrastructure.object_storage import JudgeObjectStore
from app.infrastructure.sandbox import DockerSandbox


class JudgeEngine:
    def __init__(self, object_store: JudgeObjectStore, sandbox: DockerSandbox) -> None:
        self.object_store = object_store
        self.sandbox = sandbox

    async def judge(
        self, job: SubmissionJob, test_cases: list[TestCase]
    ) -> JudgeResult:
        if job.language not in {"python", "cpp"}:
            raise JudgeConfigurationError(f"unsupported language: {job.language}")
        if not test_cases:
            raise JudgeConfigurationError("problem has no hidden test cases")

        source = await self.object_store.get_source(job.source_object_key)
        if hashlib.sha256(source).hexdigest() != job.source_checksum:
            raise InfrastructureError("source checksum verification failed")

        compilation = await self.sandbox.compile(job.language, source)
        if not compilation.succeeded:
            return JudgeResult(
                status=SubmissionStatus.COMPILE_ERROR,
                total_case_count=len(test_cases),
                compiler_output=compilation.diagnostic,
            )

        results: list[CaseResult] = []
        terminal_status = SubmissionStatus.ACCEPTED
        error_message = None
        for test_case in test_cases:
            stdin = await self.object_store.get_test_input(test_case.input_object_key)
            expected = await self.object_store.get_test_output(test_case.output_object_key)
            checksum = hashlib.sha256(stdin + b"\0" + expected).hexdigest()
            if checksum != test_case.checksum:
                raise InfrastructureError(
                    f"test data checksum verification failed for sequence {test_case.sequence}"
                )

            run = await self.sandbox.run_case(
                job.language,
                source,
                compilation.artifact,
                stdin,
                job.time_limit_ms,
                job.memory_limit_mb,
            )
            case_status = run.status
            if case_status is SubmissionStatus.ACCEPTED and not outputs_equal(
                run.stdout, expected
            ):
                case_status = SubmissionStatus.WRONG_ANSWER
            results.append(
                CaseResult(
                    test_case_id=test_case.id,
                    status=case_status,
                    time_used_ms=run.time_used_ms,
                    memory_used_kb=run.memory_used_kb,
                    exit_code=run.exit_code,
                    score=test_case.score,
                )
            )
            if case_status is not SubmissionStatus.ACCEPTED:
                terminal_status = case_status
                error_message = run.diagnostic
                break

        return JudgeResult(
            status=terminal_status,
            case_results=results,
            total_case_count=len(test_cases),
            error_message=error_message,
        )
