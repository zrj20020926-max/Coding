from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class SubmissionStatus(StrEnum):
    PENDING = "Pending"
    COMPILING = "Compiling"
    RUNNING = "Running"
    ACCEPTED = "Accepted"
    WRONG_ANSWER = "Wrong Answer"
    COMPILE_ERROR = "Compile Error"
    RUNTIME_ERROR = "Runtime Error"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
    OUTPUT_LIMIT_EXCEEDED = "Output Limit Exceeded"
    SYSTEM_ERROR = "System Error"


class SubmissionMode(StrEnum):
    SAMPLE = "sample"
    JUDGE = "judge"


class CheckerType(StrEnum):
    EXACT = "exact"
    TOKEN = "token"
    FLOAT = "float"


TERMINAL_STATUSES = frozenset(
    {
        SubmissionStatus.ACCEPTED,
        SubmissionStatus.WRONG_ANSWER,
        SubmissionStatus.COMPILE_ERROR,
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.TIME_LIMIT_EXCEEDED,
        SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
        SubmissionStatus.OUTPUT_LIMIT_EXCEEDED,
        SubmissionStatus.SYSTEM_ERROR,
    }
)


@dataclass(frozen=True)
class SubmissionJob:
    id: UUID
    problem_id: int
    language: str
    status: SubmissionStatus
    mode: SubmissionMode
    test_set_id: UUID | None
    problem_version: int
    source_object_key: str
    source_checksum: str
    time_limit_ms: int
    memory_limit_mb: int
    checker_type: CheckerType
    absolute_tolerance: Decimal | None = None
    relative_tolerance: Decimal | None = None
    attempt_id: UUID | None = None
    attempt_kind: str = "initial"


@dataclass(frozen=True)
class TestCase:
    id: UUID
    input_object_key: str | None
    output_object_key: str | None
    checksum: str
    score: Decimal
    sequence: int
    inline_input: bytes | None = None
    inline_output: bytes | None = None
    group_id: UUID | None = None
    group_name: str | None = None
    group_sequence: int | None = None
    group_score: Decimal | None = None
    group_short_circuit: bool = True
    dependency_group_id: UUID | None = None


@dataclass(frozen=True)
class CompileResult:
    succeeded: bool
    artifact: bytes | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class CaseResult:
    test_case_id: UUID
    status: SubmissionStatus
    time_used_ms: int
    memory_used_kb: int
    exit_code: int | None
    score: Decimal = Decimal("0")
    group_id: UUID | None = None


@dataclass(frozen=True)
class GroupResult:
    group_id: UUID
    status: SubmissionStatus
    score: Decimal
    passed_case_count: int
    total_case_count: int
    skipped: bool = False


@dataclass(frozen=True)
class JudgeResult:
    status: SubmissionStatus
    case_results: list[CaseResult] = field(default_factory=list)
    total_case_count: int = 0
    compiler_output: str | None = None
    error_message: str | None = None
    public_output: str | None = None
    group_results: list[GroupResult] = field(default_factory=list)

    @property
    def time_used_ms(self) -> int:
        return max((result.time_used_ms for result in self.case_results), default=0)

    @property
    def memory_used_kb(self) -> int:
        return max((result.memory_used_kb for result in self.case_results), default=0)
