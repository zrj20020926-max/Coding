# ruff: noqa: UP045
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# SQLAlchemy 2.0 cannot resolve PEP 604 mapped annotations on Python 3.9.


class ProblemDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ProblemVisibility(str, enum.Enum):
    DRAFT = "draft"
    PUBLIC = "public"
    PRIVATE = "private"


class TestSetStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    READY = "ready"
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVALID = "invalid"


class CheckerType(str, enum.Enum):
    EXACT = "exact"
    TOKEN = "token"
    FLOAT = "float"


def enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [str(item.value) for item in enum_class]


problem_id_type = BigInteger().with_variant(Integer, "sqlite")
tag_id_type = Integer()
language_id_type = SmallInteger().with_variant(Integer, "sqlite")


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(problem_id_type, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[ProblemDifficulty] = mapped_column(
        Enum(
            ProblemDifficulty,
            name="problem_difficulty",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    input_description: Mapped[str] = mapped_column(Text, nullable=False)
    output_description: Mapped[str] = mapped_column(Text, nullable=False)
    data_constraints: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    sample_input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sample_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sample_explanation: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    visibility: Mapped[ProblemVisibility] = mapped_column(
        Enum(
            ProblemVisibility,
            name="problem_visibility",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ProblemVisibility.DRAFT,
    )
    source: Mapped[Optional[str]] = mapped_column(String(200))
    created_by: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submission_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tag_links: Mapped[list[ProblemTag]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", lazy="selectin"
    )
    progress_records: Mapped[list[UserProblemProgress]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    favorite_records: Mapped[list[Favorite]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    test_sets: Mapped[list[TestSet]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )


class TestSet(Base):
    __tablename__ = "test_sets"
    __table_args__ = (
        UniqueConstraint("problem_id", "version", name="uq_test_sets_problem_version"),
        UniqueConstraint("id", "problem_id", name="uq_test_sets_id_problem"),
        CheckConstraint("version > 0", name="ck_test_sets_version"),
        CheckConstraint("case_count >= 0", name="ck_test_sets_case_count"),
        CheckConstraint("total_score >= 0", name="ck_test_sets_total_score"),
        CheckConstraint(
            "(checker_type IN ('exact', 'token') AND absolute_tolerance IS NULL "
            "AND relative_tolerance IS NULL) OR (checker_type = 'float' "
            "AND absolute_tolerance IS NOT NULL AND relative_tolerance IS NOT NULL "
            "AND absolute_tolerance >= 0 AND relative_tolerance >= 0 "
            "AND (absolute_tolerance > 0 OR relative_tolerance > 0))",
            name="ck_test_sets_checker_config",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TestSetStatus] = mapped_column(
        Enum(
            TestSetStatus,
            name="test_set_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=TestSetStatus.DRAFT,
    )
    checker_type: Mapped[CheckerType] = mapped_column(
        Enum(
            CheckerType,
            name="checker_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=CheckerType.EXACT,
    )
    absolute_tolerance: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 10))
    relative_tolerance: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 10))
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False, default=0)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    problem: Mapped[Problem] = relationship(back_populates="test_sets")
    cases: Mapped[list[TestCase]] = relationship(
        back_populates="test_set",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TestCase.sequence",
    )


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("test_set_id", "sequence", name="uq_test_cases_set_sequence"),
        CheckConstraint("sequence >= 0", name="ck_test_cases_sequence"),
        CheckConstraint("score >= 0", name="test_cases_score_check"),
        CheckConstraint("input_size_bytes >= 0", name="ck_test_cases_input_size"),
        CheckConstraint("output_size_bytes >= 0", name="ck_test_cases_output_size"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    test_set_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("test_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    output_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    input_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    test_set: Mapped[TestSet] = relationship(back_populates="cases")


Index(
    "uq_test_sets_active_problem",
    TestSet.problem_id,
    unique=True,
    postgresql_where=TestSet.status == TestSetStatus.ACTIVE,
    sqlite_where=TestSet.status == TestSetStatus.ACTIVE,
)
Index("idx_test_sets_problem_version", TestSet.problem_id, TestSet.version)
Index("idx_test_cases_test_set_sequence", TestCase.test_set_id, TestCase.sequence)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(tag_id_type, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    problem_links: Mapped[list[ProblemTag]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class ProblemTag(Base):
    __tablename__ = "problem_tags"

    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        tag_id_type,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    problem: Mapped[Problem] = relationship(back_populates="tag_links")
    tag: Mapped[Tag] = relationship(back_populates="problem_links", lazy="joined")


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(language_id_type, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    monaco_language: Mapped[str] = mapped_column(String(30), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(100), nullable=False)
    compile_command: Mapped[Optional[str]] = mapped_column(Text)
    run_command: Mapped[str] = mapped_column(Text, nullable=False)
    docker_image: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserProblemProgress(Base):
    __tablename__ = "user_problem_progress"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="CASCADE"),
        primary_key=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # The physical PostgreSQL FK points to submissions. Submission ORM belongs to the judge slice.
    last_submission_id: Mapped[Optional[UUID]] = mapped_column(Uuid(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    problem: Mapped[Problem] = relationship(back_populates="progress_records")


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    problem: Mapped[Problem] = relationship(back_populates="favorite_records")


Index("idx_favorites_user_created", Favorite.user_id, Favorite.created_at, Favorite.problem_id)
Index("idx_favorites_problem", Favorite.problem_id)
