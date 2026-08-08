from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import bearer_scheme, get_redis_client
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["认证"])


def conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "ACCOUNT_CONFLICT", "message": message},
    )


def invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_CREDENTIALS", "message": "账号或密码错误"},
    )


async def issue_token(user: User, cache: Redis) -> TokenResponse:
    token, jti, expires_in = create_access_token(user.id)
    await cache.set(f"auth:session:{jti}", str(user.id), ex=expires_in)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> TokenResponse:
    existing = await db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == str(payload.email)))
    )
    if existing is not None:
        if existing.username == payload.username:
            raise conflict("用户名已被使用")
        raise conflict("邮箱已被注册")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict("用户名或邮箱已被使用") from None
    await db.refresh(user)
    return await issue_token(user, cache)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> TokenResponse:
    account = payload.account.lower()
    user = await db.scalar(select(User).where(or_(User.username == account, User.email == account)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise invalid_credentials()
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "账号已被停用"},
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return await issue_token(user, cache)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> Response:
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        if payload is not None and payload.get("jti"):
            await cache.delete(f"auth:session:{payload['jti']}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
