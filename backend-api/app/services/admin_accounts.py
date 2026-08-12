from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.services.audit import record_audit

COMMON_PASSWORD_FRAGMENTS = {
    "password",
    "admin123",
    "12345678",
    "qwerty",
    "example",
    "changeme",
    "codearena",
}


class AdminCreateInput(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    nickname: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.casefold()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).casefold()


class AdminAccountError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdminAccountResult:
    user_id: UUID
    username: str
    action: str
    changed: bool


def validate_admin_password(password: str, *, production: bool) -> None:
    normalized = password.casefold()
    if len(password) < 12:
        raise AdminAccountError("管理员密码至少需要 12 个字符")
    required = (
        re.search(r"[a-z]", password),
        re.search(r"[A-Z]", password),
        re.search(r"\d", password),
        re.search(r"[^A-Za-z0-9]", password),
    )
    if not all(required):
        raise AdminAccountError("管理员密码必须包含大小写字母、数字和特殊字符")
    if any(fragment in normalized for fragment in COMMON_PASSWORD_FRAGMENTS):
        raise AdminAccountError("拒绝常见、示例或平台相关密码")
    if production and len(set(password)) < 8:
        raise AdminAccountError("生产环境管理员密码复杂度不足")


async def create_admin(
    db: AsyncSession,
    payload: AdminCreateInput,
    *,
    production: bool,
) -> AdminAccountResult:
    validate_admin_password(payload.password, production=production)
    matches = (
        await db.scalars(
            select(User).where(
                or_(User.username == payload.username, User.email == str(payload.email))
            )
        )
    ).all()
    if matches:
        exact = next(
            (
                user
                for user in matches
                if user.username == payload.username and user.email == str(payload.email)
            ),
            None,
        )
        if exact is not None and exact.is_admin:
            return AdminAccountResult(exact.id, exact.username, "create", False)
        if exact is not None:
            raise AdminAccountError("账号已存在；请使用 promote 命令提升权限")
        raise AdminAccountError("用户名或邮箱已被其他账号占用")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        is_admin=True,
    )
    db.add(user)
    try:
        await db.flush()
        record_audit(
            db,
            action="admin.create",
            target_type="user",
            target_id=user.id,
            actor_user_id=None,
            metadata={"source": "admin_cli", "username": user.username},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AdminAccountError("用户名或邮箱已被其他账号占用") from None
    return AdminAccountResult(user.id, user.username, "create", True)


async def promote_admin(db: AsyncSession, username: str) -> AdminAccountResult:
    normalized = username.casefold()
    user = await db.scalar(select(User).where(User.username == normalized).with_for_update())
    if user is None:
        raise AdminAccountError("指定用户不存在")
    if user.is_admin:
        return AdminAccountResult(user.id, user.username, "promote", False)
    user.is_admin = True
    user.auth_version += 1
    record_audit(
        db,
        action="admin.promote",
        target_type="user",
        target_id=user.id,
        actor_user_id=None,
        metadata={"source": "admin_cli", "username": user.username},
    )
    await db.commit()
    return AdminAccountResult(user.id, user.username, "promote", True)
