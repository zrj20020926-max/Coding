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
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
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
    SYSTEM_ERROR = "System Error"


submission_status_type = Enum(
    SubmissionStatus,
    name="submission_status",
    values_callable=enum_values,
    validate_strings=True,
)
case_result_id_type = BigInteger().with_variant(Integer, "sqlite")
outbox_payload_type = JSON().with_variant(JSONB(), "postgresql")


class Submission(Base):
    __tablename__ = "submissions"

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
    source_code: Mapped[Optional[str]] = mapped_column(Text)
    source_object_key: Mapped[Optional[str]] = mapped_column(Text)
    source_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))
    request_fingerprint: Mapped[Optional[str]] = mapped_column(CHAR(64))
    queue_message_id: Mapped[Optional[str]] = mapped_column(Text)
    compiler_output: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
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
    # test_cases has no API-side ORM because hidden test data belongs to the judge boundary.
    test_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
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
