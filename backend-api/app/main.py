from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import redis_client
from app.api.routes import auth, health, users
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
