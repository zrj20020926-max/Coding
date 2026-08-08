import asyncio
import logging

from redis.asyncio import Redis

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.services.outbox import publish_outbox_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run() -> None:
    cache = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        while True:
            try:
                async with SessionLocal() as session:
                    published = await publish_outbox_batch(session, cache)
                if published:
                    logger.info("published %d outbox event(s)", published)
            except Exception:
                logger.exception("outbox publisher iteration failed")
            await asyncio.sleep(settings.outbox_poll_interval_ms / 1000)
    finally:
        await cache.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
