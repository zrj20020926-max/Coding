from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.course import CourseType, ExerciseProgressStatus
from app.models.problem import ProblemDifficulty, TrainingCategory


class ExerciseProgressPublic(BaseModel):
    status: ExerciseProgressStatus
    selected_runtime: Optional[str] = None
    attempt_count: int
    v8_attempt_count: int
    nodejs_attempt_count: int
    v8_completed: bool
    nodejs_completed: bool
    any_runtime_completed: bool
    both_runtimes_completed: bool
    first_completed_at: Optional[datetime] = None
    last_attempted_at: Optional[datetime] = None


class CourseProgressPublic(BaseModel):
    authenticated: bool
    completed_count: int
    both_runtimes_completed_count: int
    v8_completed_count: int
    nodejs_completed_count: int
    attempted_count: int
    total_count: int
    completion_ratio: float
    both_runtimes_completion_ratio: float


class ExerciseCard(BaseModel):
    id: int
    problem_id: int
    slug: str
    title: str
    difficulty: ProblemDifficulty
    training_category: TrainingCategory
    chapter_slug: str
    sort_order: int
    estimated_minutes: int
    prerequisite_slugs: list[str]
    progress: Optional[ExerciseProgressPublic] = None


class ChapterCard(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    sort_order: int
    estimated_minutes: int
    exercise_count: int
    exercises: list[ExerciseCard]


class CourseSummary(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    type: CourseType
    sort_order: int
    chapter_count: int
    exercise_count: int
    progress: CourseProgressPublic


class CourseDetail(CourseSummary):
    chapters: list[ChapterCard]
    next_exercise: Optional[ExerciseCard] = None


class ChapterDetail(ChapterCard):
    course: CourseSummary
    progress: CourseProgressPublic
    next_exercise: Optional[ExerciseCard] = None


class ExerciseDetail(ExerciseCard):
    course_slug: str
    course_title: str
    chapter_title: str
    learning_objectives: str
    v8_notes: str
    nodejs_notes: str
    common_mistakes: list[str]
    starter_code_v8: str
    starter_code_nodejs: str
    description: str
    input_description: str
    output_description: str
    data_constraints: str
    sample_input: str
    sample_output: str
    sample_explanation: str
    time_limit_ms: int
    memory_limit_mb: int


class LearningProgressDashboard(BaseModel):
    progress: CourseProgressPublic
    courses: list[CourseSummary]
    next_exercise: Optional[ExerciseCard] = None


class RecommendedExercise(BaseModel):
    exercise: Optional[ExerciseCard] = None
    reason: str
