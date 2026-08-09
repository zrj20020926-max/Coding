from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.problem import ProblemPage
from app.schemas.training import FavoriteState, TrainingDashboard
from app.services.training import (
    favorite_problem,
    get_training_dashboard,
    list_favorite_problems,
    unfavorite_problem,
)

router = APIRouter(tags=["training"])


@router.post(
    "/problems/{problem_id}/favorite",
    response_model=FavoriteState,
    summary="Favorite a public problem idempotently",
)
async def add_favorite(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FavoriteState:
    return await favorite_problem(db, current_user.id, problem_id)


@router.delete(
    "/problems/{problem_id}/favorite",
    response_model=FavoriteState,
    summary="Remove the current user's problem favorite idempotently",
)
async def remove_favorite(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FavoriteState:
    return await unfavorite_problem(db, current_user.id, problem_id)


@router.get(
    "/favorites",
    response_model=ProblemPage,
    response_model_exclude_none=True,
    summary="List the current user's public favorite problems",
)
async def get_favorites(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProblemPage:
    return await list_favorite_problems(db, current_user.id, page, page_size)


@router.get(
    "/users/me/training",
    response_model=TrainingDashboard,
    summary="Get the current user's training dashboard",
)
async def get_my_training(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TrainingDashboard:
    return await get_training_dashboard(db, current_user)
