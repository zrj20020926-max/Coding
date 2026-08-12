from __future__ import annotations

# ruff: noqa: UP045
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class AuditLogPublic(BaseModel):
    id: UUID
    actor_user_id: Optional[UUID]
    action: str
    target_type: str
    target_id: Optional[str]
    request_id: Optional[str]
    metadata: dict[str, Any]
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogPublic]
    total: int
    page: int
    page_size: int
    pages: int
