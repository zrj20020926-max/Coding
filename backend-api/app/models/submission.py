# ruff: noqa: UP045
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.problem import enum_values


class SubmissionStatus(str, enum.Enum):
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


class SubmissionMode(str, enum.Enum):
    SAMPLE = "sample"
    JUDGE = "judge"


submission_status_type = Enum(
    SubmissionStatus,
    name="submission_status",
    values_callable=enum_values,
    validate_strings=True,
)
submission_mode_type = Enum(
    SubmissionMode,
    name="submission_mode",
    values_callable=enum_values,
    validate_strings=True,
)
case_result_id_type = BigInteger().with_variant(Integer, "sqlite")
outbox_payload_type = JSON().with_variant(JSONB(), "postgresql")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["test_set_id", "problem_id"],
            ["test_sets.id", "test_sets.problem_id"],
            name="fk_submissions_test_set_problem",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(mode = 'sample' AND test_set_id IS NULL) OR "
            "(mode = 'judge' AND test_set_id IS NOT NULL)",
            name="ck_submissions_test_set_mode",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    problem_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("problems.id", ondelete="RESTRICT"),
        nullable=False,
    )
    language_id: Mapped[int] = mapped_column(
        SmallInteger().with_variant(Integer, "sqlite"),
        ForeignKey("languages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        submission_status_type, nullable=False, default=SubmissionStatus.PENDING
    )
    mode: Mapped[SubmissionMode] = mapped_column(
        submission_mode_type, nullable=False, default=SubmissionMode.JUDGE
    )
    test_set_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    problem_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_limit_ms_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    memory_limit_mb_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    source_code: Mapped[Optional[str]] = mapped_column(Text)
    source_object_key: Mapped[Optional[str]] = mapped_column(Text)
    source_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))
    request_fingerprint: Mapped[Optional[str]] = mapped_column(CHAR(64))
    is_rejudge: Mapped[bool] = mapped_column(nullable=False, default=False)
    original_submission_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submissions.id", ondelete="RESTRICT")
    )
    effective_attempt_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    queue_message_id: Mapped[Optional[str]] = mapped_column(Text)
    compiler_output: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sample_output: Mapped[Optional[str]] = mapped_column(Text)
    time_used_ms: Mapped[Optional[int]] = mapped_column(Integer)
    memory_used_kb: Mapped[Optional[int]] = mapped_column(Integer)
    passed_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=0)
    judged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    problem: Mapped[Any] = relationship("Problem", lazy="joined")
    language: Mapped[Any] = relationship("Language", lazy="joined")
    case_results: Mapped[list[SubmissionCaseResult]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


Index(
    "uq_submissions_user_idempotency_key",
    Submission.user_id,
    Submission.idempotency_key,
    unique=True,
    postgresql_where=Submission.idempotency_key.is_not(None),
    sqlite_where=Submission.idempotency_key.is_not(None),
)


class SubmissionCaseResult(Base):
    __tablename__ = "submission_case_results"

    id: Mapped[int] = mapped_column(case_result_id_type, primary_key=True, autoincrement=True)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubmissionStatus] = mapped_column(submission_status_type, nullable=False)
    time_used_ms: Mapped[Optional[int]] = mapped_column(Integer)
    memory_used_kb: Mapped[Optional[int]] = mapped_column(Integer)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    stdout_excerpt: Mapped[Optional[str]] = mapped_column(Text)
    stderr_excerpt: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    submission: Mapped[Submission] = relationship(back_populates="case_results")


class SubmissionStatEvent(Base):
    __tablename__ = "submission_stat_events"

    submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    problem_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    terminal_status: Mapped[SubmissionStatus] = mapped_column(
        submission_status_type, nullable=False
    )
    accepted: Mapped[bool] = mapped_column(nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Outbox(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(outbox_payload_type, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    stream_message_id: Mapped[Optional[str]] = mapped_column(Text)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RejudgeTask(Base):
    __tablename__ = "rejudge_tasks"
    __table_args__ = (
        CheckConstraint("mode IN ('single', 'batch')", name="ck_rejudge_task_mode"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    requested_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    problem_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("problems.id", ondelete="RESTRICT"),
        nullable=False,
    )
    test_set_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("test_sets.id", ondelete="RESTRICT"), nullable=False
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RejudgeTaskItem(Base):
    __tablename__ = "rejudge_task_items"
    __table_args__ = (
        UniqueConstraint("rejudge_submission_id", name="uq_rejudge_item_submission"),
    )

    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rejudge_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    original_submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    rejudge_submission_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("submissions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    attempt_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submission_attempts.id", ondelete="RESTRICT")
    )


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"
    __table_args__ = (
        UniqueConstraint("submission_id", "sequence", name="uq_submission_attempt_sequence"),
        ForeignKeyConstraint(
            ["test_set_id", "problem_id"],
            ["test_sets.id", "test_sets.problem_id"],
            name="fk_attempt_test_set_problem",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        submission_status_type, nullable=False, default=SubmissionStatus.PENDING
    )
    problem_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("problems.id", ondelete="RESTRICT"),
        nullable=False,
    )
    test_set_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    problem_version: Mapped[int] = mapped_column(Integer, nullable=False)
    time_limit_ms_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_limit_mb_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    compiler_output: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    public_output: Mapped[Optional[str]] = mapped_column(Text)
    time_used_ms: Mapped[Optional[int]] = mapped_column(Integer)
    memory_used_kb: Mapped[Optional[int]] = mapped_column(Integer)
    passed_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False, default=0)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(128))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    judged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SubmissionAttemptCaseResult(Base):
    __tablename__ = "submission_attempt_case_results"

    id: Mapped[int] = mapped_column(case_result_id_type, primary_key=True, autoincrement=True)
    attempt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submission_attempts.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("test_cases.id", ondelete="RESTRICT"), nullable=False
    )
    group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("test_groups.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SubmissionStatus] = mapped_column(submission_status_type, nullable=False)
    time_used_ms: Mapped[Optional[int]] = mapped_column(Integer)
    memory_used_kb: Mapped[Optional[int]] = mapped_column(Integer)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SubmissionAttemptGroupResult(Base):
    __tablename__ = "submission_attempt_group_results"

    id: Mapped[int] = mapped_column(case_result_id_type, primary_key=True, autoincrement=True)
    attempt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submission_attempts.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("test_groups.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SubmissionStatus] = mapped_column(submission_status_type, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False, default=0)
    passed_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index(
    "uq_submission_initial_attempt",
    SubmissionAttempt.submission_id,
    unique=True,
    postgresql_where=SubmissionAttempt.kind == "initial",
    sqlite_where=SubmissionAttempt.kind == "initial",
)
Index("idx_submission_attempts_lease", SubmissionAttempt.status, SubmissionAttempt.lease_expires_at)
