from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, get_optional_current_user
from app.models.user import User
from app.schemas.course import (
    ChapterDetail,
    CourseDetail,
    CourseSummary,
    ExerciseDetail,
    LearningProgressDashboard,
    RecommendedExercise,
)
from app.services.courses import (
    get_learning_progress,
    get_public_chapter,
    get_public_course,
    get_public_exercise,
    get_recommended_exercise,
    list_public_courses,
)

router = APIRouter(tags=["learning-courses"])


@router.get(
    "/courses",
    response_model=list[CourseSummary],
    response_model_exclude_none=True,
    summary="按学习顺序获取公开课程",
)
async def get_courses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
) -> list[CourseSummary]:
    return await list_public_courses(db, current_user.id if current_user else None)


@router.get(
    "/courses/{slug}",
    response_model=CourseDetail,
    response_model_exclude_none=True,
    summary="获取课程、章节、练习顺序与完成进度",
)
async def get_course(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
) -> CourseDetail:
    return await get_public_course(db, slug, current_user.id if current_user else None)


@router.get(
    "/chapters/{slug}",
    response_model=ChapterDetail,
    response_model_exclude_none=True,
    summary="获取公开课程章节",
)
async def get_chapter(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
) -> ChapterDetail:
    return await get_public_chapter(db, slug, current_user.id if current_user else None)


@router.get(
    "/exercises/{slug}",
    response_model=ExerciseDetail,
    response_model_exclude_none=True,
    summary="获取公开输入输出练习及双运行时指导",
)
async def get_exercise(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
) -> ExerciseDetail:
    return await get_public_exercise(db, slug, current_user.id if current_user else None)


@router.get(
    "/users/me/learning-progress",
    response_model=LearningProgressDashboard,
    summary="获取当前用户任一运行时与双运行时学习进度",
)
async def get_my_learning_progress(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LearningProgressDashboard:
    return await get_learning_progress(db, current_user.id)


@router.get(
    "/users/me/recommended-exercise",
    response_model=RecommendedExercise,
    response_model_exclude_none=True,
    summary="推荐下一道前置条件已满足的练习",
)
async def get_my_recommended_exercise(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendedExercise:
    return await get_recommended_exercise(db, current_user.id)
