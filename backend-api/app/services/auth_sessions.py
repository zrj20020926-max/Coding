"""Redis-backed refresh-token rotation and session revocation."""

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from typing import Optional
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.core.config import settings

REFRESH_SESSION_PREFIX = "auth:refresh:"
REFRESH_USED_PREFIX = "auth:refresh-used:"
USER_SESSIONS_PREFIX = "auth:user-sessions:"


class InvalidRefreshTokenError(Exception):
    """The refresh token is malformed, expired, revoked, or otherwise invalid."""


class RefreshTokenReusedError(InvalidRefreshTokenError):
    """A refresh token that had already been rotated was presented again."""


@dataclass(frozen=True)
class RefreshSession:
    session_id: str
    user_id: UUID
    auth_version: int
    raw_token: str


def refresh_session_key(session_id: str) -> str:
    return f"{REFRESH_SESSION_PREFIX}{session_id}"


def refresh_used_key(session_id: str) -> str:
    return f"{REFRESH_USED_PREFIX}{session_id}"


def user_sessions_key(user_id: UUID) -> str:
    return f"{USER_SESSIONS_PREFIX}{user_id}"


def _token_hash(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def _new_raw_token(session_id: str) -> tuple[str, str]:
    secret = token_urlsafe(48)
    return f"{session_id}.{secret}", _token_hash(secret)


def parse_refresh_token(raw_token: str) -> tuple[str, str]:
    session_id, separator, secret = raw_token.partition(".")
    if not separator or not secret or len(secret) < 32:
        raise InvalidRefreshTokenError
    try:
        normalized_session_id = str(UUID(session_id))
    except ValueError:
        raise InvalidRefreshTokenError from None
    if normalized_session_id != session_id:
        raise InvalidRefreshTokenError
    return session_id, secret


async def create_refresh_session(
    cache: Redis, user_id: UUID, auth_version: int
) -> RefreshSession:
    session_id = str(uuid4())
    raw_token, token_hash = _new_raw_token(session_id)
    ttl = settings.refresh_token_expire_seconds
    async with cache.pipeline(transaction=True) as pipeline:
        pipeline.hset(
            refresh_session_key(session_id),
            mapping={
                "user_id": str(user_id),
                "auth_version": str(auth_version),
                "token_hash": token_hash,
            },
        )
        pipeline.expire(refresh_session_key(session_id), ttl)
        pipeline.sadd(user_sessions_key(user_id), session_id)
        pipeline.expire(user_sessions_key(user_id), ttl)
        await pipeline.execute()
    return RefreshSession(session_id, user_id, auth_version, raw_token)


async def rotate_refresh_session(cache: Redis, raw_token: str) -> RefreshSession:
    session_id, secret = parse_refresh_token(raw_token)
    presented_hash = _token_hash(secret)
    session_key = refresh_session_key(session_id)
    used_key = refresh_used_key(session_id)
    ttl = settings.refresh_token_expire_seconds

    for _ in range(3):
        async with cache.pipeline(transaction=True) as pipeline:
            try:
                await pipeline.watch(session_key)
                session = await pipeline.hgetall(session_key)
                if not session:
                    await pipeline.unwatch()
                    raise InvalidRefreshTokenError

                try:
                    user_id = UUID(session["user_id"])
                    auth_version = int(session["auth_version"])
                    current_hash = session["token_hash"]
                except (KeyError, TypeError, ValueError):
                    await pipeline.unwatch()
                    await revoke_refresh_session(cache, session_id)
                    raise InvalidRefreshTokenError from None

                if not compare_digest(presented_hash, current_hash):
                    await pipeline.unwatch()
                    if await cache.sismember(used_key, presented_hash):
                        await revoke_refresh_session(cache, session_id, user_id)
                        raise RefreshTokenReusedError
                    raise InvalidRefreshTokenError

                new_raw_token, new_hash = _new_raw_token(session_id)
                pipeline.multi()
                pipeline.hset(session_key, "token_hash", new_hash)
                pipeline.expire(session_key, ttl)
                pipeline.sadd(used_key, presented_hash)
                pipeline.expire(used_key, ttl)
                pipeline.expire(user_sessions_key(user_id), ttl)
                await pipeline.execute()
                return RefreshSession(session_id, user_id, auth_version, new_raw_token)
            except WatchError:
                continue
    raise InvalidRefreshTokenError


async def get_refresh_session_user(cache: Redis, session_id: str) -> Optional[tuple[str, int]]:
    session = await cache.hmget(refresh_session_key(session_id), "user_id", "auth_version")
    if not session or session[0] is None or session[1] is None:
        return None
    try:
        return str(session[0]), int(session[1])
    except (TypeError, ValueError):
        return None


async def revoke_presented_refresh_token(cache: Redis, raw_token: str) -> None:
    try:
        session_id, secret = parse_refresh_token(raw_token)
    except InvalidRefreshTokenError:
        return

    presented_hash = _token_hash(secret)
    session_key = refresh_session_key(session_id)
    current_hash = await cache.hget(session_key, "token_hash")
    is_rotated_token = await cache.sismember(refresh_used_key(session_id), presented_hash)
    if (current_hash and compare_digest(presented_hash, current_hash)) or is_rotated_token:
        await revoke_refresh_session(cache, session_id)


async def revoke_refresh_session(
    cache: Redis, session_id: str, user_id: Optional[UUID] = None
) -> None:
    if user_id is None:
        stored_user_id = await cache.hget(refresh_session_key(session_id), "user_id")
        if stored_user_id:
            try:
                user_id = UUID(stored_user_id)
            except ValueError:
                user_id = None

    async with cache.pipeline(transaction=True) as pipeline:
        pipeline.delete(refresh_session_key(session_id), refresh_used_key(session_id))
        if user_id is not None:
            pipeline.srem(user_sessions_key(user_id), session_id)
        await pipeline.execute()


async def revoke_all_user_sessions(cache: Redis, user_id: UUID) -> None:
    sessions_key = user_sessions_key(user_id)
    session_ids = await cache.smembers(sessions_key)
    keys = [sessions_key]
    for session_id in session_ids:
        keys.extend((refresh_session_key(session_id), refresh_used_key(session_id)))
    if keys:
        await cache.delete(*keys)
