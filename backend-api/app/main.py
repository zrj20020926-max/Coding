from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import redis_client
from app.api.routes import (
    admin_content,
    admin_discussions,
    admin_problems,
    ai_analyses,
    auth,
    collections,
    discussions,
    health,
    metrics,
    problems,
    submissions,
    training,
    users,
)
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description=(
        "CodeArena 后端 API。题库公开响应使用字段白名单，不包含隐藏测试数据、"
        "对象存储键、编译命令或运行镜像。提交控制平面只负责可靠接收、存储、排队和查询，"
        "不会在 API 容器中执行用户代码。"
    ),
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(problems.router, prefix=settings.api_prefix)
app.include_router(admin_problems.router, prefix=settings.api_prefix)
app.include_router(submissions.router, prefix=settings.api_prefix)
app.include_router(ai_analyses.router, prefix=settings.api_prefix)
app.include_router(training.router, prefix=settings.api_prefix)
app.include_router(collections.router, prefix=settings.api_prefix)
app.include_router(discussions.router, prefix=settings.api_prefix)
app.include_router(admin_content.router, prefix=settings.api_prefix)
app.include_router(admin_discussions.router, prefix=settings.api_prefix)
