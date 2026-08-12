from functools import lru_cache
from ipaddress import ip_network
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "local-only-secret-key-change-before-deploy"
PLACEHOLDER_JWT_SECRET = "replace-with-at-least-32-random-characters"


class Settings(BaseSettings):
    app_name: str = "ACM Training Platform API"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://acm:acm_local_password@localhost:5432/acm_platform"
    redis_url: str = "redis://:redis_local_password@localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minio_local_password"
    minio_bucket: str = "codearena-submissions"
    minio_test_data_bucket: str = "codearena-test-data"
    minio_secure: bool = False
    test_data_object_max_bytes: int = Field(
        default=16_777_216, ge=1024, le=134_217_728
    )

    submission_source_max_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    submission_min_interval_seconds: int = Field(default=2, ge=0, le=300)
    judge_supported_languages: str = "python,cpp"
    submission_stream_name: str = "codearena:judge:submissions"
    ai_analysis_stream_name: str = "codearena:ai:analyses"
    ai_analysis_daily_quota: int = Field(default=5, ge=1, le=100)
    ai_analysis_quota_window_seconds: int = Field(default=86_400, ge=60, le=604_800)
    outbox_batch_size: int = Field(default=50, ge=1, le=500)
    outbox_poll_interval_ms: int = Field(default=500, ge=50, le=60_000)
    outbox_retry_max_seconds: int = Field(default=60, ge=1, le=3600)
    outbox_dedup_ttl_seconds: int = Field(default=604_800, ge=3600, le=2_592_000)

    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "acm-training-platform"
    jwt_audience: str = "acm-platform-web"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=14, ge=1, le=90)
    refresh_cookie_name: str = "codearena.refresh_token"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal["strict", "lax", "none"] = "lax"
    refresh_cookie_domain: Optional[str] = None
    refresh_cookie_path: str = "/api/v1/auth"

    auth_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600)
    login_rate_limit_ip_attempts: int = Field(default=20, ge=1, le=1000)
    login_rate_limit_account_attempts: int = Field(default=8, ge=1, le=1000)
    register_rate_limit_ip_attempts: int = Field(default=10, ge=1, le=1000)
    register_rate_limit_account_attempts: int = Field(default=5, ge=1, le=1000)
    trusted_proxy_cidrs: str = "127.0.0.1/32,::1/128"
    cors_origins: str = "http://localhost:5173"
    content_timezone: str = "Asia/Shanghai"
    content_sensitive_words: str = "赌博,色情,暴力,违法"
    discussion_max_reply_depth: int = Field(default=3, ge=1, le=3)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def judge_supported_language_list(self) -> list[str]:
        return [
            language.strip()
            for language in self.judge_supported_languages.split(",")
            if language.strip()
        ]

    @property
    def content_sensitive_word_list(self) -> list[str]:
        return [
            word.strip().casefold()
            for word in self.content_sensitive_words.split(",")
            if word.strip()
        ]

    @field_validator("content_timezone")
    @classmethod
    def validate_content_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("content_timezone must be a valid IANA timezone") from None
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, value: str) -> str:
        for candidate in value.split(","):
            if candidate.strip():
                ip_network(candidate.strip(), strict=False)
        return value

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.refresh_token_expire_days * 24 * 60 * 60

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("SameSite=None refresh cookies must also be Secure")

        if self.app_env.lower() == "production":
            if self.jwt_secret_key in {DEFAULT_JWT_SECRET, PLACEHOLDER_JWT_SECRET}:
                raise ValueError("production requires a non-default JWT secret")
            if len(self.jwt_secret_key) < 32:
                raise ValueError("production JWT secret must contain at least 32 characters")
            if not self.refresh_cookie_secure:
                raise ValueError("production refresh cookies must be Secure")
            if self.refresh_cookie_samesite == "none":
                raise ValueError("production refresh cookies require SameSite=Lax or Strict")
            if self.refresh_cookie_domain is not None:
                raise ValueError("production refresh cookies must be host-only")
            if "*" in self.cors_origin_list:
                raise ValueError("production CORS origins cannot contain a wildcard")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
