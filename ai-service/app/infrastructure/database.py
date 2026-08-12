from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings
from app.domain import AnalysisJob, ProviderResult


class AnalysisRepository:
    def __init__(self, settings: Settings, engine: AsyncEngine | None = None) -> None:
        self.settings = settings
        self.engine = engine or create_async_engine(settings.database_url, pool_pre_ping=True)

    async def close(self) -> None:
        await self.engine.dispose()

    async def get_status(self, analysis_id: UUID) -> str | None:
        async with self.engine.connect() as connection:
            return await connection.scalar(
                text("SELECT status::text FROM ai_analyses WHERE id = :id"),
                {"id": analysis_id},
            )

    async def claim(self, analysis_id: UUID) -> bool:
        stale_before = datetime.now(UTC) - timedelta(
            seconds=self.settings.ai_running_stale_seconds
        )
        async with self.engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE ai_analyses
                    SET status = 'running', started_at = now(), updated_at = now(),
                        error_code = NULL, error_message = NULL
                    WHERE id = :id
                      AND (
                          status = 'pending'
                          OR (status = 'running' AND started_at < :stale_before)
                      )
                    """
                ),
                {"id": analysis_id, "stale_before": stale_before},
            )
            return result.rowcount == 1

    async def load_job(self, analysis_id: UUID) -> AnalysisJob | None:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT a.id AS analysis_id, a.submission_id, a.user_id, a.status::text,
                               s.source_object_key, s.status::text AS submission_status,
                               s.compiler_output, s.error_message, s.time_used_ms,
                               s.memory_used_kb, s.passed_case_count, s.total_case_count,
                               l.slug AS language_slug,
                               p.title AS problem_title, p.description AS problem_description,
                               p.input_description, p.output_description,
                               p.sample_input, p.sample_output, p.time_limit_ms, p.memory_limit_mb
                        FROM ai_analyses a
                        JOIN submissions s ON s.id = a.submission_id AND s.user_id = a.user_id
                        JOIN users u ON u.id = a.user_id AND u.is_active
                        JOIN problems p ON p.id = s.problem_id AND p.visibility = 'public'
                        JOIN languages l ON l.id = s.language_id
                        WHERE a.id = :id
                          AND s.status IN ('Wrong Answer', 'Compile Error', 'Runtime Error',
                                           'Time Limit Exceeded', 'Memory Limit Exceeded')
                        """
                    ),
                    {"id": analysis_id},
                )
            ).mappings().one_or_none()
        return AnalysisJob(**row) if row is not None else None

    async def reject_ineligible(self, analysis_id: UUID) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE ai_analyses
                    SET status = 'failed', error_code = 'ANALYSIS_NOT_ELIGIBLE',
                        error_message = 'The submission is no longer eligible for AI analysis',
                        completed_at = now(), updated_at = now()
                    WHERE id = :id AND status = 'running'
                    """
                ),
                {"id": analysis_id},
            )

    async def record_retry(self, analysis_id: UUID) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE ai_analyses SET retry_count = retry_count + 1, updated_at = now() "
                    "WHERE id = :id AND status = 'running'"
                ),
                {"id": analysis_id},
            )

    async def complete(
        self,
        job: AnalysisJob,
        result: ProviderResult,
        provider: str,
        model_name: str,
        input_cost: int,
        output_cost: int,
    ) -> bool:
        total_cost = input_cost + output_cost
        async with self.engine.begin() as connection:
            updated = await connection.execute(
                text(
                    """
                    UPDATE ai_analyses
                    SET status = 'completed', failure_reason = :failure_reason,
                        time_complexity = :time_complexity, space_complexity = :space_complexity,
                        suggestions = CAST(:suggestions AS jsonb),
                        guiding_questions = CAST(:guiding_questions AS jsonb),
                        confidence = :confidence, provider = :provider, model_name = :model_name,
                        prompt_tokens = :prompt_tokens, completion_tokens = :completion_tokens,
                        total_cost_microusd = :total_cost, latency_ms = :latency_ms,
                        provider_request_id = :provider_request_id, completed_at = now(),
                        error_code = NULL, error_message = NULL, updated_at = now()
                    WHERE id = :id AND status = 'running'
                    """
                ),
                {
                    "id": job.analysis_id,
                    "failure_reason": result.output.failure_reason,
                    "time_complexity": result.output.time_complexity,
                    "space_complexity": result.output.space_complexity,
                    "suggestions": json.dumps(result.output.suggestions, ensure_ascii=False),
                    "guiding_questions": json.dumps(
                        result.output.guiding_questions, ensure_ascii=False
                    ),
                    "confidence": result.output.confidence,
                    "provider": provider,
                    "model_name": model_name,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_cost": total_cost,
                    "latency_ms": result.latency_ms,
                    "provider_request_id": result.request_id,
                },
            )
            if updated.rowcount != 1:
                return False
            await connection.execute(
                text(
                    """
                    INSERT INTO ai_usage_records (
                        analysis_id, user_id, provider, model_name, prompt_tokens,
                        completion_tokens, input_cost_microusd, output_cost_microusd,
                        total_cost_microusd, cache_hit
                    ) VALUES (
                        :analysis_id, :user_id, :provider, :model_name, :prompt_tokens,
                        :completion_tokens, :input_cost, :output_cost, :total_cost, FALSE
                    ) ON CONFLICT (analysis_id) DO UPDATE SET
                        provider = EXCLUDED.provider, model_name = EXCLUDED.model_name,
                        prompt_tokens = EXCLUDED.prompt_tokens,
                        completion_tokens = EXCLUDED.completion_tokens,
                        input_cost_microusd = EXCLUDED.input_cost_microusd,
                        output_cost_microusd = EXCLUDED.output_cost_microusd,
                        total_cost_microusd = EXCLUDED.total_cost_microusd,
                        cache_hit = FALSE
                    """
                ),
                {
                    "analysis_id": job.analysis_id,
                    "user_id": job.user_id,
                    "provider": provider,
                    "model_name": model_name,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "input_cost": input_cost,
                    "output_cost": output_cost,
                    "total_cost": total_cost,
                },
            )
            await self._audit(
                connection,
                job.user_id,
                "ai.analysis.completed",
                job.analysis_id,
                {
                    "tokens": result.prompt_tokens + result.completion_tokens,
                    "cost_microusd": total_cost,
                },
            )
            return True

    async def fail(self, job: AnalysisJob, code: str, message: str) -> bool:
        async with self.engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE ai_analyses SET status = 'failed', error_code = :code,
                        error_message = :message, completed_at = now(), updated_at = now()
                    WHERE id = :id AND status = 'running'
                    """
                ),
                {"id": job.analysis_id, "code": code[:50], "message": message[:1000]},
            )
            if result.rowcount == 1:
                await self._audit(
                    connection,
                    job.user_id,
                    "ai.analysis.failed",
                    job.analysis_id,
                    {"error_code": code[:50]},
                )
                return True
            return False

    @staticmethod
    async def _audit(
        connection,
        user_id: UUID,
        action: str,
        analysis_id: UUID,
        metadata: dict,
    ) -> None:
        await connection.execute(
            text(
                "INSERT INTO audit_logs (actor_user_id, action, target_type, target_id, metadata) "
                "VALUES (:user_id, :action, 'ai_analysis', :target_id, CAST(:metadata AS jsonb))"
            ),
            {
                "user_id": user_id,
                "action": action,
                "target_id": str(analysis_id),
                "metadata": json.dumps(metadata, separators=(",", ":")),
            },
        )
