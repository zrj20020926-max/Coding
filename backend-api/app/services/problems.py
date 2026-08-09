from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import Select, case, cast, desc, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.sqltypes import Float

from app.core.config import settings
from app.models.problem import (
    Language,
    Problem,
    ProblemDifficulty,
    ProblemTag,
    ProblemVisibility,
    Tag,
    UserProblemProgress,
)
from app.schemas.problem import (
    AdminProblem,
    LanguagePublic,
    ProblemDetail,
    ProblemPage,
    ProblemProgressStatus,
    ProblemSort,
    ProblemSummary,
    TagPublic,
)


def problem_tags(problem: Problem) -> list[TagPublic]:
    return [TagPublic.model_validate(link.tag) for link in problem.tag_links]


def progress_fields(
    progress: UserProblemProgress | None, *, authenticated: bool
) -> dict[str, object]:
    if not authenticated:
        return {"solved": None, "attempted": None, "attempt_count": None}
    attempt_count = progress.attempt_count if progress is not None else 0
    return {
        "solved": bool(progress and progress.accepted),
        "attempted": attempt_count > 0,
        "attempt_count": attempt_count,
    }


def to_problem_summary(
    problem: Problem,
    progress: UserProblemProgress | None,
    *,
    authenticated: bool,
) -> ProblemSummary:
    return ProblemSummary(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        source=problem.source,
        accepted_count=problem.accepted_count,
        submission_count=problem.submission_count,
        tags=problem_tags(problem),
        **progress_fields(progress, authenticated=authenticated),
    )


def to_problem_detail(
    problem: Problem,
    progress: UserProblemProgress | None,
    *,
    authenticated: bool,
) -> ProblemDetail:
    summary = to_problem_summary(problem, progress, authenticated=authenticated)
    return ProblemDetail(
        **summary.model_dump(exclude={"acceptance_rate"}),
        description=problem.description,
        input_description=problem.input_description,
        output_description=problem.output_description,
        sample_input=problem.sample_input,
        sample_output=problem.sample_output,
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
    )


def to_admin_problem(problem: Problem) -> AdminProblem:
    detail = to_problem_detail(problem, None, authenticated=False)
    return AdminProblem(
        **detail.model_dump(exclude={"acceptance_rate"}),
        visibility=problem.visibility,
        created_by=str(problem.created_by) if problem.created_by else None,
    )


def apply_problem_filters(
    statement: Select[tuple[object, ...]],
    *,
    q: str | None,
    difficulty: ProblemDifficulty | None,
    tag: str | None,
    progress_status: ProblemProgressStatus | None,
    user_id: UUID | None,
) -> Select[tuple[object, ...]]:
    statement = statement.where(Problem.visibility == ProblemVisibility.PUBLIC)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Problem.title.ilike(pattern), Problem.slug.ilike(pattern)))
    if difficulty:
        statement = statement.where(Problem.difficulty == difficulty)
    if tag:
        statement = statement.where(
            exists(
                select(literal(1))
                .select_from(ProblemTag)
                .join(Tag, Tag.id == ProblemTag.tag_id)
                .where(ProblemTag.problem_id == Problem.id, Tag.slug == tag)
            )
        )
    if progress_status:
        if user_id is None:
            raise ValueError("authentication is required for a progress status filter")
        if progress_status == ProblemProgressStatus.SOLVED:
            statement = statement.where(UserProblemProgress.accepted.is_(True))
        elif progress_status == ProblemProgressStatus.ATTEMPTED:
            statement = statement.where(
                UserProblemProgress.attempt_count > 0,
                UserProblemProgress.accepted.is_(False),
            )
        else:
            statement = statement.where(
                or_(
                    UserProblemProgress.user_id.is_(None),
                    UserProblemProgress.attempt_count == 0,
                )
            )
    return statement


def apply_problem_sort(
    statement: Select[tuple[object, ...]], sort: ProblemSort
) -> Select[tuple[object, ...]]:
    if sort == ProblemSort.OLDEST:
        return statement.order_by(Problem.created_at.asc(), Problem.id.asc())
    if sort == ProblemSort.TITLE:
        return statement.order_by(Problem.title.asc(), Problem.id.asc())
    if sort == ProblemSort.DIFFICULTY:
        difficulty_order = case(
            (Problem.difficulty == ProblemDifficulty.EASY, 1),
            (Problem.difficulty == ProblemDifficulty.MEDIUM, 2),
            else_=3,
        )
        return statement.order_by(difficulty_order.asc(), Problem.id.asc())
    if sort == ProblemSort.ACCEPTANCE:
        acceptance_rate = case(
            (Problem.submission_count == 0, 0.0),
            else_=cast(Problem.accepted_count, Float) / Problem.submission_count,
        )
        return statement.order_by(desc(acceptance_rate), Problem.id.asc())
    return statement.order_by(Problem.created_at.desc(), Problem.id.desc())


async def list_public_problems(
    db: AsyncSession,
    *,
    user_id: UUID | None,
    q: str | None,
    difficulty: ProblemDifficulty | None,
    tag: str | None,
    progress_status: ProblemProgressStatus | None,
    page: int,
    page_size: int,
    sort: ProblemSort,
) -> ProblemPage:
    authenticated = user_id is not None
    if authenticated:
        base = select(Problem, UserProblemProgress).outerjoin(
            UserProblemProgress,
            (UserProblemProgress.problem_id == Problem.id)
            & (UserProblemProgress.user_id == user_id),
        )
    else:
        base = select(Problem, literal(None))

    filtered = apply_problem_filters(
        base,
        q=q,
        difficulty=difficulty,
        tag=tag,
        progress_status=progress_status,
        user_id=user_id,
    )
    count_statement = select(func.count()).select_from(filtered.order_by(None).subquery())
    total = int(await db.scalar(count_statement) or 0)

    statement = (
        apply_problem_sort(filtered, sort)
        .options(selectinload(Problem.tag_links).selectinload(ProblemTag.tag))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(statement)).all()
    items = [
        to_problem_summary(problem, progress, authenticated=authenticated)
        for problem, progress in rows
    ]
    return ProblemPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def get_problem_with_tags(
    db: AsyncSession,
    problem_id: int,
    *,
    public_only: bool,
) -> Problem | None:
    statement = (
        select(Problem)
        .where(Problem.id == problem_id)
        .options(selectinload(Problem.tag_links).selectinload(ProblemTag.tag))
    )
    if public_only:
        statement = statement.where(Problem.visibility == ProblemVisibility.PUBLIC)
    return await db.scalar(statement)


async def get_user_progress(
    db: AsyncSession, problem_id: int, user_id: UUID | None
) -> UserProblemProgress | None:
    if user_id is None:
        return None
    return await db.scalar(
        select(UserProblemProgress).where(
            UserProblemProgress.problem_id == problem_id,
            UserProblemProgress.user_id == user_id,
        )
    )


async def list_tags(db: AsyncSession) -> list[TagPublic]:
    tags = (await db.scalars(select(Tag).order_by(Tag.name.asc(), Tag.id.asc()))).all()
    return [TagPublic.model_validate(tag) for tag in tags]


async def list_public_languages(db: AsyncSession) -> list[LanguagePublic]:
    languages = (
        await db.scalars(
            select(Language)
            .where(
                Language.enabled.is_(True),
                Language.slug.in_(settings.judge_supported_language_list),
            )
            .order_by(Language.sort_order.asc(), Language.id.asc())
        )
    ).all()
    return [LanguagePublic.model_validate(language) for language in languages]
