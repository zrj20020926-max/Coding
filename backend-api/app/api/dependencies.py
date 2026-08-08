from collections.abc import AsyncGenerator
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    yield redis_client


def unauthorized(message: str = "登录状态无效或已过期") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> User:
    if credentials is None:
        raise unauthorized()

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise unauthorized()

    try:
        user_id = UUID(payload["sub"])
        jti = str(payload["jti"])
    except (KeyError, TypeError, ValueError):
        raise unauthorized() from None

    session_user_id = await cache.get(f"auth:session:{jti}")
    if session_user_id != str(user_id):
        raise unauthorized()

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise unauthorized("用户不存在或已被停用")
    return user
