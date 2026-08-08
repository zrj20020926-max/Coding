from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_redis_client
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["系统"])


@router.get("/live")
async def live() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        await cache.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DEPENDENCY_UNAVAILABLE", "message": "依赖服务尚未就绪"},
        ) from exc
    return {"status": "ready"}
