from __future__ import annotations

import asyncio
import json
import logging
from enum import StrEnum
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import Settings
from app.core.observability import (
    ANALYSES,
    COST_MICROUSD,
    PROVIDER_LATENCY,
    PROVIDER_RETRIES,
    QUEUE_LAG,
    QUEUE_PENDING,
    TOKENS,
)
from app.infrastructure.database import AnalysisRepository
from app.infrastructure.object_storage import SourceStore
from app.provider import (
    OpenAICompatibleProvider,
    ProviderPermanentError,
    ProviderTransientError,
)
from app.sanitizer import build_safe_input

logger = logging.getLogger(__name__)


class MessageDisposition(StrEnum):
    ACK = "ack"
    RETRY = "retry"


class AIWorker:
    def __init__(
        self,
        settings: Settings,
        cache: Redis,
        repository: AnalysisRepository,
        source_store: SourceStore,
        provider: OpenAICompatibleProvider,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.repository = repository
        self.source_store = source_store
        self.provider = provider

    async def ensure_consumer_group(self) -> None:
        try:
            await self.cache.xgroup_create(
                self.settings.ai_analysis_stream_name,
                self.settings.ai_consumer_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    @staticmethod
    def _analysis_id(fields: dict[str, Any]) -> UUID | None:
        try:
            raw = fields.get("payload")
            payload = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
            return UUID(str(payload["analysis_id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    async def process_analysis(self, analysis_id: UUID) -> MessageDisposition:
        status = await self.repository.get_status(analysis_id)
        if status is None or status in {"completed", "failed"}:
            return MessageDisposition.ACK
        if not await self.repository.claim(analysis_id):
            return MessageDisposition.RETRY
        job = await self.repository.load_job(analysis_id)
        if job is None:
            # The DB query itself enforces the public-problem/failed-submission boundary.
            # A malformed or no-longer-eligible job is permanently rejected.
            await self.repository.reject_ineligible(analysis_id)
            logger.warning(
                "analysis job is not eligible",
                extra={
                    "analysis_id": str(analysis_id),
                    "status": "failed",
                    "event": "rejected",
                },
            )
            ANALYSES.labels("failed_ineligible").inc()
            return MessageDisposition.ACK

        try:
            source = await self.source_store.get_source(job.source_object_key)
            safe_input = build_safe_input(job, source, self.settings)
        except (UnicodeError, ValueError) as exc:
            await self.repository.fail(job, "INVALID_ANALYSIS_INPUT", str(exc))
            ANALYSES.labels("failed_input").inc()
            return MessageDisposition.ACK
        except Exception:
            # Storage exceptions may contain bucket/object details. Do not log exception text.
            logger.warning(
                "source storage unavailable",
                extra={"analysis_id": str(analysis_id), "event": "storage_unavailable"},
            )
            return MessageDisposition.RETRY

        result = None
        for attempt in range(self.settings.ai_max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.provider.analyze(safe_input),
                    timeout=self.settings.ai_timeout_seconds,
                )
                break
            except (ProviderTransientError, TimeoutError):
                if attempt >= self.settings.ai_max_retries:
                    await self.repository.fail(
                        job,
                        "AI_PROVIDER_UNAVAILABLE",
                        "AI analysis is temporarily unavailable; please retry later",
                    )
                    ANALYSES.labels("failed_provider").inc()
                    return MessageDisposition.ACK
                await self.repository.record_retry(analysis_id)
                PROVIDER_RETRIES.inc()
                await asyncio.sleep(self.settings.ai_retry_base_seconds * (2**attempt))
            except ProviderPermanentError:
                await self.repository.fail(
                    job,
                    "AI_RESPONSE_INVALID",
                    "AI analysis could not produce a safe structured response",
                )
                ANALYSES.labels("failed_response").inc()
                return MessageDisposition.ACK

        if result is None:  # defensive; all provider branches above return or set a result
            return MessageDisposition.RETRY
        input_cost = round(
            result.prompt_tokens * self.settings.ai_input_price_usd_per_million
        )
        output_cost = round(
            result.completion_tokens * self.settings.ai_output_price_usd_per_million
        )
        completed = await self.repository.complete(
            job,
            result,
            self.settings.ai_provider,
            self.settings.ai_model,
            input_cost,
            output_cost,
        )
        if not completed:
            return MessageDisposition.RETRY
        ANALYSES.labels("completed").inc()
        PROVIDER_LATENCY.observe(result.latency_ms / 1000)
        TOKENS.labels("prompt").inc(result.prompt_tokens)
        TOKENS.labels("completion").inc(result.completion_tokens)
        COST_MICROUSD.inc(input_cost + output_cost)
        logger.info(
            "AI analysis completed",
            extra={
                "analysis_id": str(analysis_id),
                "event": "completed",
                "status": "completed",
                "latency_ms": result.latency_ms,
            },
        )
        return MessageDisposition.ACK

    async def handle_message(self, message_id: str, fields: dict[str, Any]) -> None:
        analysis_id = self._analysis_id(fields)
        if analysis_id is None:
            logger.error("acknowledging malformed AI analysis event")
            await self._ack(message_id)
            return
        try:
            disposition = await self.process_analysis(analysis_id)
        except Exception:
            logger.exception(
                "AI analysis infrastructure failure",
                extra={"analysis_id": str(analysis_id), "event": "infrastructure_failure"},
            )
            return
        if disposition is MessageDisposition.ACK:
            await self._ack(message_id)

    async def _ack(self, message_id: str) -> None:
        await self.cache.xack(
            self.settings.ai_analysis_stream_name,
            self.settings.ai_consumer_group,
            message_id,
        )

    async def _read_new(self) -> list[tuple[str, dict[str, Any]]]:
        response = await self.cache.xreadgroup(
            self.settings.ai_consumer_group,
            self.settings.ai_consumer_name,
            {self.settings.ai_analysis_stream_name: ">"},
            count=1,
            block=self.settings.ai_block_ms,
        )
        return response[0][1] if response else []

    async def _claim_stale(self) -> list[tuple[str, dict[str, Any]]]:
        response = await self.cache.xautoclaim(
            self.settings.ai_analysis_stream_name,
            self.settings.ai_consumer_group,
            self.settings.ai_consumer_name,
            self.settings.ai_claim_idle_ms,
            "0-0",
            count=1,
        )
        return response[1] if response and len(response) > 1 else []

    async def _update_queue_metrics(self) -> None:
        try:
            pending = await self.cache.xpending(
                self.settings.ai_analysis_stream_name,
                self.settings.ai_consumer_group,
            )
            count = pending.get("pending", 0) if isinstance(pending, dict) else pending[0]
            QUEUE_PENDING.set(int(count))
            groups = await self.cache.xinfo_groups(self.settings.ai_analysis_stream_name)
            group = next(
                (
                    item
                    for item in groups
                    if item.get("name") == self.settings.ai_consumer_group
                ),
                None,
            )
            QUEUE_LAG.set(int((group or {}).get("lag") or 0))
        except Exception:
            logger.warning("failed to update AI queue metrics", exc_info=True)

    async def run(self) -> None:
        await self.ensure_consumer_group()
        while True:
            try:
                await self._update_queue_metrics()
                messages = await self._claim_stale()
                if not messages:
                    messages = await self._read_new()
                for message_id, fields in messages:
                    await self.handle_message(message_id, fields)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AI consumer loop failed")
                await asyncio.sleep(1)
