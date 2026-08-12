import asyncio

from prometheus_client import start_http_server
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.observability import configure_logging
from app.infrastructure.database import AnalysisRepository
from app.infrastructure.object_storage import SourceStore
from app.provider import OpenAICompatibleProvider
from app.worker import AIWorker


async def run() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    start_http_server(settings.metrics_port)
    cache = Redis.from_url(settings.redis_url, decode_responses=True)
    repository = AnalysisRepository(settings)
    worker = AIWorker(
        settings,
        cache,
        repository,
        SourceStore(settings),
        OpenAICompatibleProvider(settings),
    )
    try:
        await worker.run()
    finally:
        await cache.aclose()
        await repository.close()


if __name__ == "__main__":
    asyncio.run(run())
