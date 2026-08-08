from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ACM Training Platform API"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://acm:acm_local_password@localhost:5432/acm_platform"
    redis_url: str = "redis://:redis_local_password@localhost:6379/0"

    jwt_secret_key: str = "local-only-secret-key-change-before-deploy"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "acm-training-platform"
    jwt_audience: str = "acm-platform-web"
    access_token_expire_minutes: int = Field(default=120, ge=5, le=1440)
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
