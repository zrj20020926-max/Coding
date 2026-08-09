import math
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.problem import (
    Favorite,
    Problem,
    ProblemDifficulty,
    ProblemTag,
    ProblemVisibility,
    Tag,
    UserProblemProgress,
)
from app.models.user import User
from app.schemas.problem import ProblemPage, TagPublic
from app.schemas.training import (
    DifficultyTrainingStat,
    FavoriteState,
    SolvedProblemPublic,
    TagTrainingStat,
    TrainingCounters,
    TrainingDashboard,
)
from app.services.problems import to_problem_summary
from app.services.submissions import list_owned_submissions, submission_error


async def _public_problem_exists(db: AsyncSession, problem_id: int) -> bool:
    return (
        await db.scalar(
            select(Problem.id).where(
                Problem.id == problem_id,
                Problem.visibility == ProblemVisibility.PUBLIC,
            )
        )
        is not None
    )


async def favorite_problem(
    db: AsyncSession, user_id: UUID, problem_id: int
) -> FavoriteState:
    if not await _public_problem_exists(db, problem_id):
        raise submission_error(404, "PROBLEM_NOT_FOUND", "public problem not found")
    existing = await db.get(Favorite, (user_id, problem_id))
    if existing is None:
        db.add(Favorite(user_id=user_id, problem_id=problem_id))
        try:
            await db.commit()
        except IntegrityError:
            # A concurrent identical POST won the unique key. The desired state exists.
            await db.rollback()
    return FavoriteState(problem_id=problem_id, favorited=True)


async def unfavorite_problem(
    db: AsyncSession, user_id: UUID, problem_id: int
) -> FavoriteState:
    if not await _public_problem_exists(db, problem_id):
        raise submission_error(404, "PROBLEM_NOT_FOUND", "public problem not found")
    await db.execute(
        delete(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.problem_id == problem_id,
        )
    )
    await db.commit()
    return FavoriteState(problem_id=problem_id, favorited=False)


async def list_favorite_problems(
    db: AsyncSession,
    user_id: UUID,
    page: int,
    page_size: int,
) -> ProblemPage:
    filters = (
        Favorite.user_id == user_id,
        Problem.visibility == ProblemVisibility.PUBLIC,
    )
    total = int(
        await db.scalar(
            select(func.count(Favorite.problem_id))
            .join(Problem, Problem.id == Favorite.problem_id)
            .where(*filters)
        )
        or 0
    )
    rows = (
        await db.execute(
            select(Problem, UserProblemProgress)
            .join(Favorite, Favorite.problem_id == Problem.id)
            .outerjoin(
                UserProblemProgress,
                (UserProblemProgress.problem_id == Problem.id)
                & (UserProblemProgress.user_id == user_id),
            )
            .where(*filters)
            .options(selectinload(Problem.tag_links).selectinload(ProblemTag.tag))
            .order_by(Favorite.created_at.desc(), Problem.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return ProblemPage(
        items=[
            to_problem_summary(
                problem,
                progress,
                authenticated=True,
                favorited=True,
            )
            for problem, progress in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def _difficulty_stats(
    db: AsyncSession, user_id: UUID
) -> list[DifficultyTrainingStat]:
    stats: list[DifficultyTrainingStat] = []
    for difficulty in ProblemDifficulty:
        total = int(
            await db.scalar(
                select(func.count(Problem.id)).where(
                    Problem.visibility == ProblemVisibility.PUBLIC,
                    Problem.difficulty == difficulty,
                )
            )
            or 0
        )
        attempted = int(
            await db.scalar(
                select(func.count(UserProblemProgress.problem_id))
                .join(Problem, Problem.id == UserProblemProgress.problem_id)
                .where(
                    UserProblemProgress.user_id == user_id,
                    UserProblemProgress.attempt_count > 0,
                    Problem.visibility == ProblemVisibility.PUBLIC,
                    Problem.difficulty == difficulty,
                )
            )
            or 0
        )
        solved = int(
            await db.scalar(
                select(func.count(UserProblemProgress.problem_id))
                .join(Problem, Problem.id == UserProblemProgress.problem_id)
                .where(
                    UserProblemProgress.user_id == user_id,
                    UserProblemProgress.accepted.is_(True),
                    Problem.visibility == ProblemVisibility.PUBLIC,
                    Problem.difficulty == difficulty,
                )
            )
            or 0
        )
        stats.append(
            DifficultyTrainingStat(
                difficulty=difficulty,
                total_count=total,
                attempted_count=attempted,
                solved_count=solved,
            )
        )
    return stats


async def _tag_stats(db: AsyncSession, user_id: UUID) -> list[TagTrainingStat]:
    attempted_case = case(
        (UserProblemProgress.attempt_count > 0, 1),
        else_=0,
    )
    solved_case = case((UserProblemProgress.accepted.is_(True), 1), else_=0)
    rows = (
        await db.execute(
            select(
                Tag,
                func.count(Problem.id),
                func.sum(attempted_case),
                func.sum(solved_case),
            )
            .join(ProblemTag, ProblemTag.tag_id == Tag.id)
            .join(Problem, Problem.id == ProblemTag.problem_id)
            .outerjoin(
                UserProblemProgress,
                (UserProblemProgress.problem_id == Problem.id)
                & (UserProblemProgress.user_id == user_id),
            )
            .where(Problem.visibility == ProblemVisibility.PUBLIC)
            .group_by(Tag.id)
            .order_by(func.sum(solved_case).desc(), Tag.name.asc())
        )
    ).all()
    return [
        TagTrainingStat(
            tag=TagPublic.model_validate(tag),
            total_count=int(total or 0),
            attempted_count=int(attempted or 0),
            solved_count=int(solved or 0),
        )
        for tag, total, attempted, solved in rows
    ]


async def get_training_dashboard(
    db: AsyncSession, user: User
) -> TrainingDashboard:
    await db.refresh(
        user,
        attribute_names=["solved_count", "submission_count", "accepted_count"],
    )
    recent = await list_owned_submissions(db, user.id, 1, 8, None)
    solved_rows = (
        await db.execute(
            select(Problem, UserProblemProgress)
            .join(
                UserProblemProgress,
                UserProblemProgress.problem_id == Problem.id,
            )
            .where(
                UserProblemProgress.user_id == user.id,
                UserProblemProgress.accepted.is_(True),
                UserProblemProgress.first_accepted_at.is_not(None),
                Problem.visibility == ProblemVisibility.PUBLIC,
            )
            .order_by(UserProblemProgress.first_accepted_at.desc(), Problem.id.desc())
            .limit(30)
        )
    ).all()
    solved_problems = [
        SolvedProblemPublic(
            id=problem.id,
            slug=problem.slug,
            title=problem.title,
            difficulty=problem.difficulty,
            attempt_count=progress.attempt_count,
            first_accepted_at=progress.first_accepted_at,
        )
        for problem, progress in solved_rows
        if progress.first_accepted_at is not None
    ]
    return TrainingDashboard(
        counters=TrainingCounters(
            solved_count=user.solved_count,
            submission_count=user.submission_count,
            accepted_count=user.accepted_count,
        ),
        recent_submissions=recent.items,
        solved_problems=solved_problems,
        difficulty_stats=await _difficulty_stats(db, user.id),
        tag_stats=await _tag_stats(db, user.id),
    )
