from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_optional_current_user
from app.models.problem import ProblemDifficulty
from app.models.user import User
from app.schemas.problem import (
    LanguagePublic,
    ProblemDetail,
    ProblemPage,
    ProblemProgressStatus,
    ProblemSort,
    TagPublic,
)
from app.services.problems import (
    get_public_problem_by_identifier,
    get_user_favorite,
    get_user_progress,
    list_public_languages,
    list_public_problems,
    list_tags,
    to_problem_detail,
)

router = APIRouter(tags=["题库"])


def not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "PROBLEM_NOT_FOUND", "message": "题目不存在"},
    )


@router.get(
    "/problems",
    response_model=ProblemPage,
    response_model_exclude_none=True,
    summary="分页查询公开题目",
)
async def get_problems(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
    q: Annotated[Optional[str], Query(min_length=1, max_length=200)] = None,
    difficulty: Optional[ProblemDifficulty] = None,
    tag: Annotated[Optional[str], Query(min_length=1, max_length=50)] = None,
    progress_status: Annotated[
        Optional[ProblemProgressStatus], Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: ProblemSort = ProblemSort.NEWEST,
) -> ProblemPage:
    if progress_status is not None and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "按个人进度筛选需要登录"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await list_public_problems(
        db,
        user_id=current_user.id if current_user else None,
        q=q,
        difficulty=difficulty,
        tag=tag,
        progress_status=progress_status,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get(
    "/problems/{identifier}",
    response_model=ProblemDetail,
    response_model_exclude_none=True,
    summary="获取公开题目详情",
)
async def get_problem(
    identifier: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
) -> ProblemDetail:
    problem = await get_public_problem_by_identifier(db, identifier)
    if problem is None:
        raise not_found()
    progress = await get_user_progress(
        db, problem.id, current_user.id if current_user else None
    )
    favorite = await get_user_favorite(
        db, problem.id, current_user.id if current_user else None
    )
    return to_problem_detail(
        problem,
        progress,
        authenticated=current_user is not None,
        favorited=favorite is not None,
    )


@router.get("/tags", response_model=list[TagPublic], summary="获取标签列表")
async def get_tags(db: Annotated[AsyncSession, Depends(get_db)]) -> list[TagPublic]:
    return await list_tags(db)


@router.get(
    "/languages", response_model=list[LanguagePublic], summary="获取公开可用语言"
)
async def get_languages(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LanguagePublic]:
    return await list_public_languages(db)
