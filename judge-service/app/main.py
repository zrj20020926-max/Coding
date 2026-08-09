import asyncio
import logging

from redis.asyncio import Redis

from app.core.config import settings
from app.infrastructure.database import JudgeRepository
from app.infrastructure.object_storage import MinioJudgeObjectStore
from app.infrastructure.sandbox import DockerSandbox
from app.judge import JudgeEngine
from app.worker import JudgeWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    cache = Redis.from_url(settings.redis_url, decode_responses=True)
    repository = JudgeRepository(settings.database_url)
    object_store = MinioJudgeObjectStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        source_bucket=settings.minio_source_bucket,
        test_data_bucket=settings.minio_test_data_bucket,
        secure=settings.minio_secure,
        object_limit_bytes=settings.sandbox_object_limit_bytes,
    )
    sandbox = DockerSandbox(settings)
    worker = JudgeWorker(
        settings,
        cache,
        repository,
        JudgeEngine(object_store, sandbox),
    )
    try:
        await sandbox.ping()
        logger.info(
            "judge worker starting stream=%s group=%s consumer=%s",
            settings.submission_stream_name,
            settings.judge_consumer_group,
            settings.judge_consumer_name,
        )
        await worker.run()
    finally:
        await cache.aclose()
        await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
