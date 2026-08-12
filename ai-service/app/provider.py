import json
from time import monotonic
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.domain import AIAnalysisOutput, ProviderResult
from app.prompt import build_messages


class ProviderTransientError(RuntimeError):
    pass


class ProviderPermanentError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def analyze(self, safe_input: dict[str, Any]) -> ProviderResult:
        if not self.settings.resolved_api_key:
            raise ProviderPermanentError("AI provider is not configured")
        started = monotonic()
        owned_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self.settings.ai_provider_base_url.rstrip("/"),
            timeout=self.settings.ai_timeout_seconds,
        )
        try:
            response = await client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.resolved_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.ai_model,
                    "messages": build_messages(safe_input),
                    "max_completion_tokens": self.settings.ai_max_output_tokens,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "codearena_ai_analysis",
                            "strict": True,
                            "schema": AIAnalysisOutput.model_json_schema(),
                        },
                    },
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderTransientError("AI provider timed out or was unreachable") from exc
        finally:
            if owned_client:
                await client.aclose()

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderTransientError(f"AI provider returned {response.status_code}")
        if response.status_code >= 400:
            raise ProviderPermanentError(
                f"AI provider rejected the request ({response.status_code})"
            )
        try:
            body = response.json()
            raw_content = body["choices"][0]["message"]["content"]
            content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            output = AIAnalysisOutput.model_validate(content)
            usage = body.get("usage") or {}
            prompt_tokens = max(0, int(usage.get("prompt_tokens", 0)))
            completion_tokens = max(0, int(usage.get("completion_tokens", 0)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise ProviderPermanentError(
                "AI provider returned an invalid structured response"
            ) from exc
        return ProviderResult(
            output=output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            request_id=response.headers.get("x-request-id"),
            latency_ms=int((monotonic() - started) * 1000),
        )
