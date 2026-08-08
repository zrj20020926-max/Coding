from functools import lru_cache
from ipaddress import ip_network
from typing import Literal, Optional

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
