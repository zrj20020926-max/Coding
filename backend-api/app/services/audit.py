from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AuditLog

_FORBIDDEN_METADATA_PARTS = {
    "password",
    "token",
    "secret",
    "hash",
    "object_key",
    "checksum",
    "source_code",
    "hidden_input",
    "hidden_output",
}


def _validate_metadata_value(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(part in str(key).casefold() for part in _FORBIDDEN_METADATA_PARTS):
                raise ValueError("audit metadata contains a forbidden field")
            _validate_metadata_value(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _validate_metadata_value(nested)


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    _validate_metadata_value(metadata)
    return metadata


def record_audit(
    db: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: str | int | UUID | None,
    actor_user_id: UUID | None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> None:
    """Stage an allow-listed audit event in the caller's database transaction."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            request_id=request_id,
            metadata_json=_safe_metadata(metadata),
        )
    )
