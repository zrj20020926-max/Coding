from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import Settings
from app.domain.models import TERMINAL_STATUSES, JudgeResult, SubmissionStatus
from app.errors import InfrastructureError, JudgeConfigurationError
from app.infrastructure.database import JudgeRepository
from app.judge import JudgeEngine

logger = logging.getLogger(__name__)

RENEW_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""

RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


class MessageDisposition(StrEnum):
    ACK = "ack"
    RETRY = "retry"


@dataclass
class SubmissionLease:
    key: str
    token: str
    acquired: bool
    lost: bool = False


class JudgeWorker:
    def __init__(
        self,
        settings: Settings,
        cache: Redis,
        repository: JudgeRepository,
        engine: JudgeEngine,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.repository = repository
        self.engine = engine

    async def ensure_consumer_group(self) -> None:
        try:
            await self.cache.xgroup_create(
                self.settings.submission_stream_name,
                self.settings.judge_consumer_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise InfrastructureError("failed to create Redis consumer group") from exc
        logger.info(
            "Redis consumer group ready stream=%s group=%s",
            self.settings.submission_stream_name,
            self.settings.judge_consumer_group,
        )

    async def _renew_lease(self, lease: SubmissionLease) -> None:
        interval = self.settings.judge_lock_ttl_ms / 3000
        try:
            while True:
                await asyncio.sleep(interval)
                renewed = await self.cache.eval(
                    RENEW_LOCK_SCRIPT,
                    1,
                    lease.key,
                    lease.token,
                    str(self.settings.judge_lock_ttl_ms),
                )
                if not renewed:
                    lease.lost = True
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            lease.lost = True
            logger.exception("submission lease renewal failed")

    @asynccontextmanager
    async def submission_lease(self, submission_id: UUID) -> AsyncIterator[SubmissionLease]:
        key = f"judge:submission:{submission_id}:lock"
        token = secrets.token_hex(16)
        try:
            acquired = bool(
                await self.cache.set(
                    key,
                    token,
                    nx=True,
                    px=self.settings.judge_lock_ttl_ms,
                )
            )
        except Exception as exc:
            raise InfrastructureError("failed to acquire Redis submission lease") from exc
        lease = SubmissionLease(key, token, acquired)
        renewal = asyncio.create_task(self._renew_lease(lease)) if acquired else None
        try:
            yield lease
        finally:
            if renewal is not None:
                renewal.cancel()
                await asyncio.gather(renewal, return_exceptions=True)
                try:
                    await self.cache.eval(RELEASE_LOCK_SCRIPT, 1, key, token)
                except Exception:
                    logger.exception("submission lease release failed")

    async def _reload_status(self, submission_id: UUID) -> SubmissionStatus | None:
        current = await self.repository.load_submission(submission_id)
        return current.status if current else None

    async def _finalize_configuration_error(
        self, submission_id: UUID, current_status: SubmissionStatus, message: str
    ) -> MessageDisposition:
        expected = current_status
        if current_status is SubmissionStatus.PENDING:
            moved = await self.repository.transition(
                submission_id, SubmissionStatus.PENDING, SubmissionStatus.COMPILING
            )
            if not moved:
                status = await self._reload_status(submission_id)
                return (
                    MessageDisposition.ACK
                    if status in TERMINAL_STATUSES
                    else MessageDisposition.RETRY
                )
            expected = SubmissionStatus.COMPILING
        result = JudgeResult(
            status=SubmissionStatus.SYSTEM_ERROR,
            error_message=message,
        )
        finalized = await self.repository.finalize(submission_id, expected, result)
        if finalized:
            return MessageDisposition.ACK
        status = await self._reload_status(submission_id)
        return MessageDisposition.ACK if status in TERMINAL_STATUSES else MessageDisposition.RETRY

    async def process_submission(self, submission_id: UUID) -> MessageDisposition:
        async with self.submission_lease(submission_id) as lease:
            if not lease.acquired:
                return MessageDisposition.RETRY
            job = await self.repository.load_submission(submission_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return MessageDisposition.ACK

            current_status = job.status
            if current_status is SubmissionStatus.PENDING:
                moved = await self.repository.transition(
                    submission_id,
                    SubmissionStatus.PENDING,
                    SubmissionStatus.COMPILING,
                )
                if not moved:
                    status = await self._reload_status(submission_id)
                    return (
                        MessageDisposition.ACK
                        if status in TERMINAL_STATUSES
                        else MessageDisposition.RETRY
                    )
                current_status = SubmissionStatus.COMPILING

            try:
                test_cases = await self.repository.load_test_cases(job.problem_id)
                result = await self.engine.judge(job, test_cases)
            except JudgeConfigurationError as exc:
                return await self._finalize_configuration_error(
                    submission_id, current_status, str(exc)
                )
            except InfrastructureError:
                return MessageDisposition.RETRY

            if lease.lost:
                return MessageDisposition.RETRY

            if result.status is SubmissionStatus.COMPILE_ERROR:
                if current_status is not SubmissionStatus.COMPILING:
                    result = JudgeResult(
                        status=SubmissionStatus.SYSTEM_ERROR,
                        total_case_count=result.total_case_count,
                        error_message="compile result arrived after Running state",
                    )
                    expected = SubmissionStatus.RUNNING
                else:
                    expected = SubmissionStatus.COMPILING
            else:
                if current_status is SubmissionStatus.COMPILING:
                    moved = await self.repository.transition(
                        submission_id,
                        SubmissionStatus.COMPILING,
                        SubmissionStatus.RUNNING,
                    )
                    if not moved:
                        status = await self._reload_status(submission_id)
                        return (
                            MessageDisposition.ACK
                            if status in TERMINAL_STATUSES
                            else MessageDisposition.RETRY
                        )
                expected = SubmissionStatus.RUNNING

            finalized = await self.repository.finalize(submission_id, expected, result)
            if not finalized:
                status = await self._reload_status(submission_id)
                if status not in TERMINAL_STATUSES:
                    return MessageDisposition.RETRY
            try:
                await self.cache.set(
                    f"judge:submission:{submission_id}:done",
                    "1",
                    ex=self.settings.judge_done_ttl_seconds,
                )
            except Exception:
                # PostgreSQL terminal state is authoritative; a missing cache hint is harmless.
                logger.warning("failed to write judge done hint", exc_info=True)
            return MessageDisposition.ACK

    @staticmethod
    def _submission_id(fields: dict[str, Any]) -> UUID | None:
        try:
            payload_raw = fields.get("payload")
            payload = json.loads(payload_raw) if isinstance(payload_raw, (str, bytes)) else {}
            return UUID(str(payload["submission_id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    async def handle_message(self, message_id: str, fields: dict[str, Any]) -> None:
        submission_id = self._submission_id(fields)
        if submission_id is None:
            logger.error("acknowledging malformed judge event %s", message_id)
            await self.cache.xack(
                self.settings.submission_stream_name,
                self.settings.judge_consumer_group,
                message_id,
            )
            return
        try:
            disposition = await self.process_submission(submission_id)
        except InfrastructureError:
            logger.exception("judge infrastructure failure for %s", submission_id)
            return
        if disposition is MessageDisposition.ACK:
            await self.cache.xack(
                self.settings.submission_stream_name,
                self.settings.judge_consumer_group,
                message_id,
            )

    async def _read_new(self) -> list[tuple[str, dict[str, Any]]]:
        response = await self.cache.xreadgroup(
            self.settings.judge_consumer_group,
            self.settings.judge_consumer_name,
            {self.settings.submission_stream_name: ">"},
            count=1,
            block=self.settings.judge_block_ms,
        )
        if not response:
            return []
        return response[0][1]

    async def _claim_stale(self) -> list[tuple[str, dict[str, Any]]]:
        response = await self.cache.xautoclaim(
            self.settings.submission_stream_name,
            self.settings.judge_consumer_group,
            self.settings.judge_consumer_name,
            self.settings.judge_claim_idle_ms,
            "0-0",
            count=1,
        )
        return response[1] if response and len(response) > 1 else []

    async def run(self) -> None:
        await self.ensure_consumer_group()
        while True:
            try:
                messages = await self._claim_stale()
                if not messages:
                    messages = await self._read_new()
                for message_id, fields in messages:
                    await self.handle_message(message_id, fields)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("judge consumer loop failed")
                await asyncio.sleep(1)
