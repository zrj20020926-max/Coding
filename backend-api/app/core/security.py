from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("codearena-dummy-password-never-used")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(
    user_id: UUID,
    session_id: str,
    auth_version: int,
    *,
    expires_in_seconds: Optional[int] = None,
) -> tuple[str, str, int]:
    now = datetime.now(timezone.utc)
    expires_in = expires_in_seconds or settings.access_token_expire_minutes * 60
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "sid": session_id,
        "ver": auth_version,
        "type": "access",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_in),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_in


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "jti", "sid", "ver", "type", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "access" else None
