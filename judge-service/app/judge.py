import hashlib
from collections import OrderedDict
from decimal import Decimal
from uuid import UUID

from app.domain.comparison import float_outputs_equal, outputs_equal, token_outputs_equal
from app.domain.models import (
    CaseResult,
    CheckerType,
    GroupResult,
    JudgeResult,
    SubmissionJob,
    SubmissionMode,
    SubmissionStatus,
    TestCase,
)
from app.errors import InfrastructureError, JudgeConfigurationError
from app.infrastructure.object_storage import JudgeObjectStore
from app.infrastructure.sandbox import DockerSandbox, SandboxRunResult


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
        group_results: list[GroupResult] = []
        terminal_status = SubmissionStatus.ACCEPTED
        error_message = None
        public_output = None
        grouped: OrderedDict[UUID, list[TestCase]] = OrderedDict()
        for test_case in sorted(
            test_cases,
            key=lambda item: (
                item.group_sequence if item.group_sequence is not None else item.sequence,
                item.sequence,
            ),
        ):
            grouped.setdefault(test_case.group_id or test_case.id, []).append(test_case)

        completed_groups: dict[UUID, SubmissionStatus] = {}
        stop_all = False
        for group_id, group_cases in grouped.items():
            first = group_cases[0]
            dependency = first.dependency_group_id
            if (
                dependency is not None
                and completed_groups.get(dependency) is not SubmissionStatus.ACCEPTED
            ):
                group_results.append(
                    GroupResult(
                        group_id=group_id,
                        status=SubmissionStatus.WRONG_ANSWER,
                        score=Decimal("0"),
                        passed_case_count=0,
                        total_case_count=len(group_cases),
                        skipped=True,
                    )
                )
                completed_groups[group_id] = SubmissionStatus.WRONG_ANSWER
                if terminal_status is SubmissionStatus.ACCEPTED:
                    terminal_status = SubmissionStatus.WRONG_ANSWER
                continue

            group_status = SubmissionStatus.ACCEPTED
            group_passed = 0
            for test_case in group_cases:
                if stop_all:
                    break
                case_status, run, case_public_output = await self._judge_case(
                    job, test_case, source, compilation.artifact
                )
                if case_public_output is not None:
                    public_output = case_public_output
                results.append(
                    CaseResult(
                        test_case_id=test_case.id,
                        status=case_status,
                        time_used_ms=run.time_used_ms,
                        memory_used_kb=run.memory_used_kb,
                        exit_code=run.exit_code,
                        score=test_case.score,
                        group_id=group_id,
                    )
                )
                if case_status is SubmissionStatus.ACCEPTED:
                    group_passed += 1
                else:
                    group_status = case_status
                    if terminal_status is SubmissionStatus.ACCEPTED:
                        terminal_status = case_status
                        error_message = run.diagnostic
                    if first.group_short_circuit:
                        break
                    if case_status is SubmissionStatus.SYSTEM_ERROR:
                        stop_all = True
                        break

            group_score = (
                first.group_score if first.group_score is not None else sum(
                    (case.score for case in group_cases), Decimal("0")
                )
            )
            group_results.append(
                GroupResult(
                    group_id=group_id,
                    status=group_status,
                    score=(
                        group_score
                        if group_status is SubmissionStatus.ACCEPTED
                        else Decimal("0")
                    ),
                    passed_case_count=group_passed,
                    total_case_count=len(group_cases),
                )
            )
            completed_groups[group_id] = group_status

        return JudgeResult(
            status=terminal_status,
            case_results=results,
            group_results=group_results,
            total_case_count=len(test_cases),
            error_message=error_message,
            public_output=public_output,
        )

    async def _judge_case(
        self,
        job: SubmissionJob,
        test_case: TestCase,
        source: bytes,
        artifact: bytes | None,
    ) -> tuple[SubmissionStatus, SandboxRunResult, str | None]:
        if test_case.inline_input is not None and test_case.inline_output is not None:
            stdin = test_case.inline_input
            expected = test_case.inline_output
        elif test_case.input_object_key and test_case.output_object_key:
            stdin = await self.object_store.get_test_input(test_case.input_object_key)
            expected = await self.object_store.get_test_output(test_case.output_object_key)
        else:
            raise JudgeConfigurationError(
                f"test case {test_case.sequence} has no readable data source"
            )
        checksum = hashlib.sha256(stdin + b"\0" + expected).hexdigest()
        if checksum != test_case.checksum:
            raise InfrastructureError(
                f"test data checksum verification failed for sequence {test_case.sequence}"
            )

        run = await self.sandbox.run_case(
            job.language,
            source,
            artifact,
            stdin,
            job.time_limit_ms,
            job.memory_limit_mb,
        )
        case_status = run.status
        public_output = None
        if job.mode is SubmissionMode.SAMPLE:
            public_output = run.stdout.decode("utf-8", errors="replace")
        matches = self._matches(job, run.stdout, expected)
        if case_status is SubmissionStatus.ACCEPTED and not matches:
            case_status = SubmissionStatus.WRONG_ANSWER
        return case_status, run, public_output

    @staticmethod
    def _matches(job: SubmissionJob, actual: bytes, expected: bytes) -> bool:
        if job.mode is SubmissionMode.SAMPLE or job.checker_type is CheckerType.EXACT:
            return outputs_equal(actual, expected)
        if job.checker_type is CheckerType.TOKEN:
            return token_outputs_equal(actual, expected)
        if (
            job.checker_type is CheckerType.FLOAT
            and job.absolute_tolerance is not None
            and job.relative_tolerance is not None
        ):
            return float_outputs_equal(
                actual,
                expected,
                job.absolute_tolerance,
                job.relative_tolerance,
            )
        raise JudgeConfigurationError("invalid checker configuration")
