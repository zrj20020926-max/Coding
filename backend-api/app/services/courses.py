from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course import (
    Chapter,
    Course,
    Exercise,
    ExercisePrerequisite,
    ExerciseProgressStatus,
    UserExerciseProgress,
)
from app.models.problem import ProblemVisibility
from app.schemas.course import (
    ChapterCard,
    ChapterDetail,
    CourseDetail,
    CourseProgressPublic,
    CourseSummary,
    ExerciseCard,
    ExerciseDetail,
    ExerciseProgressPublic,
    LearningProgressDashboard,
    RecommendedExercise,
)


def course_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _course_query_options():
    exercises = selectinload(Course.chapters).selectinload(Chapter.exercises)
    return (
        exercises.joinedload(Exercise.problem),
        exercises.selectinload(Exercise.prerequisite_links)
        .joinedload(ExercisePrerequisite.prerequisite)
        .joinedload(Exercise.problem),
    )


async def _load_catalog(db: AsyncSession) -> list[Course]:
    rows = (
        (
            await db.scalars(
                select(Course)
                .where(Course.is_public.is_(True))
                .options(*_course_query_options())
                .order_by(Course.sort_order, Course.id)
            )
        )
        .unique()
        .all()
    )
    return list(rows)


async def _load_progress(db: AsyncSession, user_id: UUID | None) -> dict[int, UserExerciseProgress]:
    if user_id is None:
        return {}
    rows = (
        await db.scalars(
            select(UserExerciseProgress).where(UserExerciseProgress.user_id == user_id)
        )
    ).all()
    return {item.exercise_id: item for item in rows}


def _visible_chapters(course: Course) -> list[Chapter]:
    return sorted(
        (item for item in course.chapters if item.is_public),
        key=lambda item: (item.sort_order, item.id),
    )


def _visible_exercises(chapter: Chapter) -> list[Exercise]:
    return sorted(
        (
            item
            for item in chapter.exercises
            if item.is_public and item.problem.visibility is ProblemVisibility.PUBLIC
        ),
        key=lambda item: (item.sort_order, item.id),
    )


def _course_exercises(course: Course) -> list[Exercise]:
    return [
        exercise
        for chapter in _visible_chapters(course)
        for exercise in _visible_exercises(chapter)
    ]


def _public_progress(
    progress: UserExerciseProgress | None,
) -> ExerciseProgressPublic:
    if progress is None:
        return ExerciseProgressPublic(
            status=ExerciseProgressStatus.NOT_STARTED,
            attempt_count=0,
            v8_attempt_count=0,
            nodejs_attempt_count=0,
            v8_completed=False,
            nodejs_completed=False,
            any_runtime_completed=False,
            both_runtimes_completed=False,
        )
    v8_completed = progress.v8_completed_at is not None
    nodejs_completed = progress.nodejs_completed_at is not None
    any_completed = v8_completed or nodejs_completed
    status = (
        ExerciseProgressStatus.COMPLETED
        if any_completed
        else ExerciseProgressStatus.ATTEMPTED
        if progress.attempt_count > 0
        else ExerciseProgressStatus.NOT_STARTED
    )
    return ExerciseProgressPublic(
        status=status,
        selected_runtime=progress.selected_runtime,
        attempt_count=progress.attempt_count,
        v8_attempt_count=progress.v8_attempt_count,
        nodejs_attempt_count=progress.nodejs_attempt_count,
        v8_completed=v8_completed,
        nodejs_completed=nodejs_completed,
        any_runtime_completed=any_completed,
        both_runtimes_completed=v8_completed and nodejs_completed,
        first_completed_at=progress.first_completed_at,
        last_attempted_at=progress.last_attempted_at,
    )


def _aggregate_progress(
    exercises: Sequence[Exercise],
    progress_map: dict[int, UserExerciseProgress],
    *,
    authenticated: bool,
) -> CourseProgressPublic:
    items = [_public_progress(progress_map.get(item.id)) for item in exercises]
    total = len(items)
    completed = sum(item.any_runtime_completed for item in items)
    both = sum(item.both_runtimes_completed for item in items)
    return CourseProgressPublic(
        authenticated=authenticated,
        completed_count=completed,
        both_runtimes_completed_count=both,
        v8_completed_count=sum(item.v8_completed for item in items),
        nodejs_completed_count=sum(item.nodejs_completed for item in items),
        attempted_count=sum(item.attempt_count > 0 for item in items),
        total_count=total,
        completion_ratio=round(completed / total, 4) if total else 0.0,
        both_runtimes_completion_ratio=round(both / total, 4) if total else 0.0,
    )


def _exercise_card(
    exercise: Exercise,
    progress_map: dict[int, UserExerciseProgress],
    *,
    authenticated: bool,
) -> ExerciseCard:
    prerequisite_slugs = sorted(
        link.prerequisite.problem.slug for link in exercise.prerequisite_links
    )
    return ExerciseCard(
        id=exercise.id,
        problem_id=exercise.problem_id,
        slug=exercise.problem.slug,
        title=exercise.problem.title,
        difficulty=exercise.problem.difficulty,
        training_category=exercise.problem.training_category,
        chapter_slug=exercise.chapter.slug,
        sort_order=exercise.sort_order,
        estimated_minutes=exercise.estimated_minutes,
        prerequisite_slugs=prerequisite_slugs,
        progress=(_public_progress(progress_map.get(exercise.id)) if authenticated else None),
    )


def _next_exercise(
    exercises: Sequence[Exercise], progress_map: dict[int, UserExerciseProgress]
) -> Exercise | None:
    completed = {
        exercise_id
        for exercise_id, progress in progress_map.items()
        if progress.v8_completed_at is not None or progress.nodejs_completed_at is not None
    }
    for exercise in exercises:
        if exercise.id in completed:
            continue
        prerequisites = {item.prerequisite_id for item in exercise.prerequisite_links}
        if prerequisites <= completed:
            return exercise
    return None


def _course_summary(
    course: Course,
    progress_map: dict[int, UserExerciseProgress],
    *,
    authenticated: bool,
) -> CourseSummary:
    chapters = _visible_chapters(course)
    exercises = _course_exercises(course)
    return CourseSummary(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description,
        type=course.type,
        sort_order=course.sort_order,
        chapter_count=len(chapters),
        exercise_count=len(exercises),
        progress=_aggregate_progress(exercises, progress_map, authenticated=authenticated),
    )


def _chapter_card(
    chapter: Chapter,
    progress_map: dict[int, UserExerciseProgress],
    *,
    authenticated: bool,
) -> ChapterCard:
    exercises = _visible_exercises(chapter)
    return ChapterCard(
        id=chapter.id,
        slug=chapter.slug,
        title=chapter.title,
        description=chapter.description,
        sort_order=chapter.sort_order,
        estimated_minutes=chapter.estimated_minutes,
        exercise_count=len(exercises),
        exercises=[
            _exercise_card(item, progress_map, authenticated=authenticated) for item in exercises
        ],
    )


async def list_public_courses(db: AsyncSession, user_id: UUID | None) -> list[CourseSummary]:
    courses = await _load_catalog(db)
    progress = await _load_progress(db, user_id)
    return [_course_summary(item, progress, authenticated=user_id is not None) for item in courses]


async def get_public_course(db: AsyncSession, slug: str, user_id: UUID | None) -> CourseDetail:
    courses = await _load_catalog(db)
    course = next((item for item in courses if item.slug == slug), None)
    if course is None:
        raise course_error(404, "COURSE_NOT_FOUND", "课程不存在")
    progress = await _load_progress(db, user_id)
    exercises = _course_exercises(course)
    next_item = _next_exercise(exercises, progress)
    summary = _course_summary(course, progress, authenticated=user_id is not None)
    return CourseDetail(
        **summary.model_dump(),
        chapters=[
            _chapter_card(item, progress, authenticated=user_id is not None)
            for item in _visible_chapters(course)
        ],
        next_exercise=(
            _exercise_card(next_item, progress, authenticated=user_id is not None)
            if next_item is not None
            else None
        ),
    )


async def get_public_chapter(db: AsyncSession, slug: str, user_id: UUID | None) -> ChapterDetail:
    courses = await _load_catalog(db)
    pair = next(
        (
            (course, chapter)
            for course in courses
            for chapter in _visible_chapters(course)
            if chapter.slug == slug
        ),
        None,
    )
    if pair is None:
        raise course_error(404, "CHAPTER_NOT_FOUND", "章节不存在")
    course, chapter = pair
    progress = await _load_progress(db, user_id)
    exercises = _visible_exercises(chapter)
    next_item = _next_exercise(exercises, progress)
    card = _chapter_card(chapter, progress, authenticated=user_id is not None)
    return ChapterDetail(
        **card.model_dump(),
        course=_course_summary(course, progress, authenticated=user_id is not None),
        progress=_aggregate_progress(exercises, progress, authenticated=user_id is not None),
        next_exercise=(
            _exercise_card(next_item, progress, authenticated=user_id is not None)
            if next_item is not None
            else None
        ),
    )


async def get_public_exercise(db: AsyncSession, slug: str, user_id: UUID | None) -> ExerciseDetail:
    courses = await _load_catalog(db)
    found = next(
        (
            (course, chapter, exercise)
            for course in courses
            for chapter in _visible_chapters(course)
            for exercise in _visible_exercises(chapter)
            if exercise.problem.slug == slug
        ),
        None,
    )
    if found is None:
        raise course_error(404, "EXERCISE_NOT_FOUND", "练习不存在")
    course, chapter, exercise = found
    progress = await _load_progress(db, user_id)
    card = _exercise_card(exercise, progress, authenticated=user_id is not None)
    problem = exercise.problem
    return ExerciseDetail(
        **card.model_dump(),
        course_slug=course.slug,
        course_title=course.title,
        chapter_title=chapter.title,
        learning_objectives=exercise.learning_objectives,
        v8_notes=exercise.v8_notes,
        nodejs_notes=exercise.nodejs_notes,
        common_mistakes=list(exercise.common_mistakes),
        starter_code_v8=exercise.starter_code_v8,
        starter_code_nodejs=exercise.starter_code_nodejs,
        description=problem.description,
        input_description=problem.input_description,
        output_description=problem.output_description,
        data_constraints=problem.data_constraints,
        sample_input=problem.sample_input,
        sample_output=problem.sample_output,
        sample_explanation=problem.sample_explanation,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
    )


async def get_learning_progress(db: AsyncSession, user_id: UUID) -> LearningProgressDashboard:
    courses = await _load_catalog(db)
    progress = await _load_progress(db, user_id)
    exercises = [item for course in courses for item in _course_exercises(course)]
    next_item = _next_exercise(exercises, progress)
    return LearningProgressDashboard(
        progress=_aggregate_progress(exercises, progress, authenticated=True),
        courses=[_course_summary(course, progress, authenticated=True) for course in courses],
        next_exercise=(
            _exercise_card(next_item, progress, authenticated=True)
            if next_item is not None
            else None
        ),
    )


async def get_recommended_exercise(db: AsyncSession, user_id: UUID) -> RecommendedExercise:
    courses = await _load_catalog(db)
    progress = await _load_progress(db, user_id)
    exercises = [item for course in courses for item in _course_exercises(course)]
    next_item = _next_exercise(exercises, progress)
    if next_item is None:
        return RecommendedExercise(exercise=None, reason="全部公开练习均已完成")
    return RecommendedExercise(
        exercise=_exercise_card(next_item, progress, authenticated=True),
        reason="按课程顺序推荐第一道未完成且前置练习已完成的练习",
    )
