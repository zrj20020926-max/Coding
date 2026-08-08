from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import bearer_scheme, get_current_user, get_redis_client
from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserPublic
from app.services.auth_sessions import (
    InvalidRefreshTokenError,
    RefreshSession,
    RefreshTokenReusedError,
    create_refresh_session,
    revoke_all_user_sessions,
    revoke_presented_refresh_token,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.services.rate_limit import enforce_auth_rate_limit, get_client_ip

router = APIRouter(prefix="/auth", tags=["认证"])


def api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    headers: Optional[dict[str, str]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers,
    )


def conflict(message: str) -> HTTPException:
    return api_error(status.HTTP_409_CONFLICT, "ACCOUNT_CONFLICT", message)


def invalid_credentials() -> HTTPException:
    return api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "账号或密码错误")


def invalid_refresh_token(*, reused: bool = False) -> HTTPException:
    code = "REFRESH_TOKEN_REUSED" if reused else "INVALID_REFRESH_TOKEN"
    message = "刷新令牌已被重复使用，请重新登录" if reused else "刷新令牌无效或已过期"
    cookie_response = Response()
    clear_refresh_cookie(cookie_response)
    return api_error(
        status.HTTP_401_UNAUTHORIZED,
        code,
        message,
        headers={"Set-Cookie": cookie_response.headers["set-cookie"]},
    )


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        max_age=settings.refresh_token_expire_seconds,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def token_response(user: User, session: RefreshSession) -> TokenResponse:
    access_token, _, expires_in = create_access_token(
        user.id, session.session_id, user.auth_version
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


async def issue_session(user: User, cache: Redis, response: Response) -> TokenResponse:
    session = await create_refresh_session(cache, user.id, user.auth_version)
    set_refresh_cookie(response, session.raw_token)
    return token_response(user, session)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> TokenResponse:
    await enforce_auth_rate_limit(
        cache,
        action="register",
        client_ip=get_client_ip(request),
        account_identities=(payload.username, str(payload.email)),
        ip_limit=settings.register_rate_limit_ip_attempts,
        account_limit=settings.register_rate_limit_account_attempts,
    )

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
        password_hash=await run_in_threadpool(hash_password, payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict("用户名或邮箱已被使用") from None
    await db.refresh(user)
    return await issue_session(user, cache, response)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> TokenResponse:
    await enforce_auth_rate_limit(
        cache,
        action="login",
        client_ip=get_client_ip(request),
        account_identities=(payload.account,),
        ip_limit=settings.login_rate_limit_ip_attempts,
        account_limit=settings.login_rate_limit_account_attempts,
    )

    user = await db.scalar(
        select(User).where(or_(User.username == payload.account, User.email == payload.account))
    )
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_valid = await run_in_threadpool(verify_password, payload.password, stored_hash)
    if user is None or not password_valid:
        raise invalid_credentials()
    if not user.is_active:
        raise api_error(status.HTTP_403_FORBIDDEN, "ACCOUNT_DISABLED", "账号已被停用")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return await issue_session(user, cache, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> TokenResponse:
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        clear_refresh_cookie(response)
        raise invalid_refresh_token()

    try:
        session = await rotate_refresh_session(cache, raw_token)
    except RefreshTokenReusedError:
        clear_refresh_cookie(response)
        raise invalid_refresh_token(reused=True) from None
    except InvalidRefreshTokenError:
        clear_refresh_cookie(response)
        raise invalid_refresh_token() from None

    user = await db.scalar(select(User).where(User.id == session.user_id))
    if user is None or user.auth_version != session.auth_version:
        await revoke_refresh_session(cache, session.session_id, session.user_id)
        clear_refresh_cookie(response)
        raise invalid_refresh_token()
    if not user.is_active:
        await revoke_refresh_session(cache, session.session_id, session.user_id)
        clear_refresh_cookie(response)
        cookie_response = Response()
        clear_refresh_cookie(cookie_response)
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "ACCOUNT_DISABLED",
            "账号已被停用",
            headers={"Set-Cookie": cookie_response.headers["set-cookie"]},
        )

    set_refresh_cookie(response, session.raw_token)
    return token_response(user, session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> Response:
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        if payload is not None and payload.get("sid"):
            await revoke_refresh_session(cache, str(payload["sid"]))

    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if raw_token:
        await revoke_presented_refresh_token(cache, raw_token)
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> Response:
    current_user.auth_version += 1
    await db.commit()
    await revoke_all_user_sessions(cache, current_user.id)
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> Response:
    password_valid = await run_in_threadpool(
        verify_password, payload.current_password, current_user.password_hash
    )
    if not password_valid:
        raise api_error(
            status.HTTP_400_BAD_REQUEST, "INVALID_CURRENT_PASSWORD", "当前密码不正确"
        )
    if payload.current_password == payload.new_password:
        raise api_error(
            status.HTTP_400_BAD_REQUEST, "PASSWORD_UNCHANGED", "新密码不能与当前密码相同"
        )

    current_user.password_hash = await run_in_threadpool(hash_password, payload.new_password)
    current_user.auth_version += 1
    await db.commit()
    await revoke_all_user_sessions(cache, current_user.id)
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
