# ruff: noqa: UP045
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.problem import enum_values


class AIAnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


ai_analysis_status_type = Enum(
    AIAnalysisStatus,
    name="ai_analysis_status",
    values_callable=enum_values,
    validate_strings=True,
)
json_type = JSON().with_variant(JSONB(), "postgresql")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AIAnalysisStatus] = mapped_column(
        ai_analysis_status_type, nullable=False, default=AIAnalysisStatus.PENDING
    )
    request_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    diagnostic_report: Mapped[Optional[dict[str, Any]]] = mapped_column(json_type)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    failure_summary: Mapped[Optional[str]] = mapped_column(Text)
    time_complexity: Mapped[Optional[str]] = mapped_column(String(100))
    space_complexity: Mapped[Optional[str]] = mapped_column(String(100))
    suggestions: Mapped[Optional[list[str]]] = mapped_column(json_type)
    guiding_questions: Mapped[Optional[list[str]]] = mapped_column(json_type)
    confidence: Mapped[Optional[str]] = mapped_column(String(10))
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    total_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(200))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_from_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ai_analyses.id", ondelete="SET NULL")
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    submission: Mapped[Any] = relationship("Submission", lazy="joined")


Index(
    "idx_ai_analyses_retryable",
    AIAnalysis.created_at,
    postgresql_where=AIAnalysis.status.in_([AIAnalysisStatus.PENDING, AIAnalysisStatus.RUNNING]),
)
Index(
    "idx_ai_analyses_completed_fingerprint",
    AIAnalysis.request_fingerprint,
    AIAnalysis.completed_at,
    postgresql_where=AIAnalysis.status == AIAnalysisStatus.COMPLETED,
)
Index("idx_ai_analyses_user_created", AIAnalysis.user_id, AIAnalysis.created_at)


class AIUsageRecord(Base):
    __tablename__ = "ai_usage_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model_name: Mapped[Optional[str]] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index("idx_ai_usage_user_created", AIUsageRecord.user_id, AIUsageRecord.created_at)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(100))
    request_id: Mapped[Optional[str]] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index("idx_audit_logs_actor_created", AuditLog.actor_user_id, AuditLog.created_at)
Index(
    "idx_audit_logs_target_created",
    AuditLog.target_type,
    AuditLog.target_id,
    AuditLog.created_at,
)
