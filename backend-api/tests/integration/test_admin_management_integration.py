from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.ai import AuditLog
from app.models.user import User
from app.services.admin_accounts import AdminCreateInput, create_admin, promote_admin


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_bootstrap_persists_argon2_and_audit_in_postgres(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    suffix = uuid4().hex[:10]
    username = f"bootstrap_{suffix}"
    email = f"bootstrap-{suffix}@example.com"
    password = f"Aa7!{uuid4().hex}"
    async with sessions() as db:
        created = await create_admin(
            db,
            AdminCreateInput(
                username=username,
                email=email,
                nickname="bootstrap integration",
                password=password,
            ),
            production=True,
        )
        repeated = await create_admin(
            db,
            AdminCreateInput(
                username=username,
                email=email,
                nickname="bootstrap integration",
                password=password,
            ),
            production=True,
        )
        assert created.changed is True and repeated.changed is False
        user = await db.get(User, created.user_id)
        assert user is not None and user.is_admin is True
        assert user.password_hash.startswith("$argon2id$")
        logs = (
            await db.scalars(
                select(AuditLog).where(
                    AuditLog.target_type == "user",
                    AuditLog.target_id == str(created.user_id),
                )
            )
        ).all()
        assert [log.action for log in logs] == ["admin.create"]
        await db.delete(user)
        await db.commit()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_promote_is_idempotent_and_invalidates_sessions_in_postgres(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    suffix = uuid4().hex[:10]
    async with sessions() as db:
        user = User(
            username=f"promote_{suffix}",
            email=f"promote-{suffix}@example.com",
            password_hash="test-only-hash",
            nickname="promote integration",
        )
        db.add(user)
        await db.commit()
        first = await promote_admin(db, user.username)
        second = await promote_admin(db, user.username)
        assert first.changed is True and second.changed is False
        await db.refresh(user)
        assert user.is_admin is True and user.auth_version == 2
        logs = (
            await db.scalars(
                select(AuditLog).where(
                    AuditLog.target_type == "user",
                    AuditLog.target_id == str(user.id),
                )
            )
        ).all()
        assert [log.action for log in logs] == ["admin.promote"]
        await db.delete(user)
        await db.commit()
    await engine.dispose()
