from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserProfileUpdate, UserPublic

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.patch("/me", response_model=UserPublic)
async def update_me(
    payload: UserProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(current_user, field_name, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user
