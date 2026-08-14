# ruff: noqa: UP045
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.problem import Problem, enum_values, problem_id_type

course_id_type = BigInteger().with_variant(Integer, "sqlite")
course_json_type = JSON().with_variant(JSONB(), "postgresql")


class CourseType(str, enum.Enum):
    INPUT = "input"
    OUTPUT = "output"
    MIXED = "mixed"
    PERFORMANCE = "performance"


class ExerciseProgressStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"


course_type = Enum(
    CourseType,
    name="course_type",
    values_callable=enum_values,
    validate_strings=True,
)
exercise_progress_status_type = Enum(
    ExerciseProgressStatus,
    name="exercise_progress_status",
    values_callable=enum_values,
    validate_strings=True,
)


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (CheckConstraint("sort_order >= 0", name="ck_courses_sort_order"),)

    id: Mapped[int] = mapped_column(course_id_type, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[CourseType] = mapped_column(course_type, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Chapter.sort_order",
        lazy="selectin",
    )


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("course_id", "sort_order", name="uq_chapters_course_sort"),
        CheckConstraint("sort_order >= 0", name="ck_chapters_sort_order"),
        CheckConstraint("estimated_minutes > 0", name="ck_chapters_estimated_minutes"),
    )

    id: Mapped[int] = mapped_column(course_id_type, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        course_id_type,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    course: Mapped[Course] = relationship(back_populates="chapters")
    exercises: Mapped[list[Exercise]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Exercise.sort_order",
        lazy="selectin",
    )


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint("chapter_id", "sort_order", name="uq_exercises_chapter_sort"),
        CheckConstraint("sort_order >= 0", name="ck_exercises_sort_order"),
        CheckConstraint("estimated_minutes > 0", name="ck_exercises_estimated_minutes"),
    )

    id: Mapped[int] = mapped_column(course_id_type, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    chapter_id: Mapped[int] = mapped_column(
        course_id_type,
        ForeignKey("chapters.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    learning_objectives: Mapped[str] = mapped_column(Text, nullable=False)
    v8_notes: Mapped[str] = mapped_column(Text, nullable=False)
    nodejs_notes: Mapped[str] = mapped_column(Text, nullable=False)
    common_mistakes: Mapped[list[str]] = mapped_column(
        course_json_type, nullable=False, default=list
    )
    starter_code_v8: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code_nodejs: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    chapter: Mapped[Chapter] = relationship(back_populates="exercises")
    problem: Mapped[Problem] = relationship(lazy="joined")
    prerequisite_links: Mapped[list[ExercisePrerequisite]] = relationship(
        foreign_keys="ExercisePrerequisite.exercise_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ExercisePrerequisite(Base):
    __tablename__ = "exercise_prerequisites"
    __table_args__ = (
        CheckConstraint(
            "exercise_id <> prerequisite_id",
            name="ck_exercise_prerequisites_not_self",
        ),
    )

    exercise_id: Mapped[int] = mapped_column(
        course_id_type,
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    prerequisite_id: Mapped[int] = mapped_column(
        course_id_type,
        ForeignKey("exercises.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    prerequisite: Mapped[Exercise] = relationship(foreign_keys=[prerequisite_id], lazy="joined")


class UserExerciseProgress(Base):
    __tablename__ = "user_exercise_progress"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_exercise_progress_attempt_count"),
        CheckConstraint(
            "v8_attempt_count >= 0 AND nodejs_attempt_count >= 0",
            name="ck_exercise_progress_runtime_attempt_counts",
        ),
        CheckConstraint(
            "selected_runtime IS NULL OR selected_runtime IN ('javascript-v8', 'nodejs')",
            name="ck_exercise_progress_selected_runtime",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[int] = mapped_column(
        course_id_type,
        ForeignKey("exercises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[ExerciseProgressStatus] = mapped_column(
        exercise_progress_status_type,
        nullable=False,
        default=ExerciseProgressStatus.NOT_STARTED,
    )
    selected_runtime: Mapped[Optional[str]] = mapped_column(
        String(30), ForeignKey("languages.slug", onupdate="CASCADE", ondelete="SET NULL")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    v8_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nodejs_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    v8_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    nodejs_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    first_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_attempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    exercise: Mapped[Exercise] = relationship(lazy="joined")


Index("idx_courses_public_sort", Course.sort_order, Course.id, postgresql_where=Course.is_public)
Index(
    "idx_chapters_public_course_sort",
    Chapter.course_id,
    Chapter.sort_order,
    Chapter.id,
    postgresql_where=Chapter.is_public,
)
Index(
    "idx_exercises_public_chapter_sort",
    Exercise.chapter_id,
    Exercise.sort_order,
    Exercise.id,
    postgresql_where=Exercise.is_public,
)
Index("idx_exercise_prerequisites_prerequisite", ExercisePrerequisite.prerequisite_id)
Index(
    "idx_user_exercise_progress_user_status",
    UserExerciseProgress.user_id,
    UserExerciseProgress.status,
    UserExerciseProgress.exercise_id,
)
