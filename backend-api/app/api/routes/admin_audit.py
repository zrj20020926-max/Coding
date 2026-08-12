from __future__ import annotations

# ruff: noqa: UP045
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.db.session import get_db
from app.models.ai import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogPage, AuditLogPublic

router = APIRouter(prefix="/admin/audit-logs", tags=["审计日志管理"])


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
    action: Annotated[Optional[str], Query(max_length=100)] = None,
    target_type: Annotated[Optional[str], Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogPage:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    total = int(await db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0)
    rows = (
        await db.scalars(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return AuditLogPage(
        items=[
            AuditLogPublic(
                id=row.id,
                actor_user_id=row.actor_user_id,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                request_id=row.request_id,
                metadata=row.metadata_json,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
    )
