import json
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.submission import Outbox, Submission

PUBLISH_EVENT_SCRIPT = """
local existing = redis.call('GET', KEYS[1])
if existing then
    return existing
end
local message_id = redis.call(
    'XADD', KEYS[2], '*',
    'event_id', ARGV[2],
    'event_type', ARGV[3],
    'aggregate_type', ARGV[4],
    'aggregate_id', ARGV[5],
    'payload', ARGV[6]
)
redis.call('SET', KEYS[1], message_id, 'EX', ARGV[1])
return message_id
"""


def _retry_delay(attempts: int) -> int:
    return min(settings.outbox_retry_max_seconds, 2 ** min(attempts, 10))


async def publish_outbox_batch(db: AsyncSession, cache: Redis) -> int:
    now = datetime.now(timezone.utc)
    events = (
        await db.scalars(
            select(Outbox)
            .where(Outbox.published_at.is_(None), Outbox.next_attempt_at <= now)
            .order_by(Outbox.created_at, Outbox.id)
            .limit(settings.outbox_batch_size)
            .with_for_update(skip_locked=True)
        )
    ).all()
    published = 0
    for event in events:
        try:
            message_id = await cache.eval(
                PUBLISH_EVENT_SCRIPT,
                2,
                f"outbox:published:{event.id}",
                settings.submission_stream_name,
                str(settings.outbox_dedup_ttl_seconds),
                str(event.id),
                event.event_type,
                event.aggregate_type,
                str(event.aggregate_id),
                json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
            )
            event.published_at = now
            event.stream_message_id = (
                message_id.decode() if isinstance(message_id, bytes) else str(message_id)
            )
            event.last_error = None
            submission = await db.get(Submission, event.aggregate_id)
            if submission is not None:
                submission.queue_message_id = event.stream_message_id
            published += 1
        except Exception as exc:
            event.attempts += 1
            event.last_error = str(exc)[:2000]
            event.next_attempt_at = now + timedelta(seconds=_retry_delay(event.attempts))
    await db.commit()
    return published
