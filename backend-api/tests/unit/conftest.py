from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_redis_client
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.object_storage import get_source_object_store


class FakeSourceObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_put = False

    async def put_source(self, object_key: str, content: bytes) -> None:
        if self.fail_put:
            raise OSError("MinIO unavailable")
        self.objects[object_key] = content

    async def delete_source(self, object_key: str) -> None:
        self.objects.pop(object_key, None)

    async def get_source(self, object_key: str) -> bytes:
        return self.objects[object_key]


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def fake_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield cache
    await cache.aclose()


@pytest.fixture
def fake_object_store() -> FakeSourceObjectStore:
    return FakeSourceObjectStore()


@pytest.fixture
async def client(
    db_session: AsyncSession,
    fake_redis: fakeredis.aioredis.FakeRedis,
    fake_object_store: FakeSourceObjectStore,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
        yield fake_redis

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[get_source_object_store] = lambda: fake_object_store
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
