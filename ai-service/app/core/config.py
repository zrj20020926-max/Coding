from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql+asyncpg://acm:acm_local_password@localhost:5432/acm_platform"
    redis_url: str = "redis://:redis_local_password@localhost:6379/0"
    ai_analysis_stream_name: str = "codearena:ai:analyses"
    ai_consumer_group: str = "codearena-ai"
    ai_consumer_name: str = "ai-worker-1"
    ai_block_ms: int = Field(default=5000, ge=100, le=60_000)
    ai_claim_idle_ms: int = Field(default=120_000, ge=10_000, le=3_600_000)
    ai_running_stale_seconds: int = Field(default=180, ge=30, le=3600)

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minio_local_password"
    minio_source_bucket: str = "codearena-submissions"
    minio_secure: bool = False
    minio_region: str = "us-east-1"
    source_max_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)

    ai_provider: Literal["openai-compatible"] = "openai-compatible"
    ai_provider_base_url: str = "https://api.openai.com/v1"
    ai_provider_api_key: str = ""
    ai_provider_api_key_file: str = ""
    ai_model: str = "gpt-5-mini"
    ai_timeout_seconds: float = Field(default=30, ge=1, le=120)
    ai_max_retries: int = Field(default=3, ge=0, le=5)
    ai_retry_base_seconds: float = Field(default=1, ge=0, le=30)
    ai_max_output_tokens: int = Field(default=1200, ge=200, le=4000)
    ai_input_price_usd_per_million: float = Field(default=0, ge=0)
    ai_output_price_usd_per_million: float = Field(default=0, ge=0)

    max_problem_chars: int = Field(default=24_000, ge=1000, le=100_000)
    max_source_chars: int = Field(default=50_000, ge=1000, le=200_000)
    max_compiler_output_chars: int = Field(default=12_000, ge=100, le=50_000)
    max_failure_message_chars: int = Field(default=2_000, ge=100, le=10_000)
    metrics_port: int = Field(default=9102, ge=1024, le=65535)
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @cached_property
    def resolved_api_key(self) -> str:
        if self.ai_provider_api_key_file:
            return Path(self.ai_provider_api_key_file).read_text(encoding="utf-8").strip()
        return self.ai_provider_api_key

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.app_env.lower() == "production":
            if not self.ai_provider_api_key_file:
                raise ValueError("production requires AI_PROVIDER_API_KEY_FILE from Secret Manager")
            if not Path(self.ai_provider_api_key_file).is_file():
                raise ValueError("AI_PROVIDER_API_KEY_FILE must reference a readable secret file")
            if not self.minio_secure:
                raise ValueError("production requires TLS for MinIO")
            if self.minio_access_key == "minioadmin" or self.minio_secret_key in {
                "minioadmin",
                "minio_local_password",
                "ai_local_password_change_me",
            }:
                raise ValueError("production requires dedicated non-default MinIO credentials")
        return self
