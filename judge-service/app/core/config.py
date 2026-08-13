from functools import lru_cache
from socket import gethostname

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://acm:acm_local_password@localhost:5432/acm_platform"
    )
    redis_url: str = "redis://:redis_local_password@localhost:6379/0"
    submission_stream_name: str = "codearena:judge:submissions"
    judge_consumer_group: str = "codearena-judge"
    judge_consumer_name: str = Field(default_factory=lambda: f"judge-{gethostname()}")
    judge_block_ms: int = Field(default=5000, ge=100, le=60_000)
    judge_claim_idle_ms: int = Field(default=60_000, ge=1000, le=3_600_000)
    judge_lock_ttl_ms: int = Field(default=120_000, ge=10_000, le=3_600_000)
    judge_done_ttl_seconds: int = Field(default=604_800, ge=3600, le=2_592_000)
    judge_database_lease_seconds: int = Field(default=120, ge=10, le=3600)

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minio_local_password"
    minio_source_bucket: str = "codearena-submissions"
    minio_test_data_bucket: str = "codearena-test-data"
    minio_secure: bool = False

    sandbox_python_image: str = "python:3.12-alpine"
    sandbox_cpp_image: str = "gcc:14.2-bookworm"
    sandbox_node_image: str = "node:22-alpine"
    sandbox_pull_images: bool = True
    sandbox_cpus: float = Field(default=0.5, gt=0, le=4)
    sandbox_pids_limit: int = Field(default=32, ge=4, le=256)
    sandbox_disk_limit_bytes: int = Field(
        default=64 * 1024 * 1024, ge=8 * 1024 * 1024, le=512 * 1024 * 1024
    )
    sandbox_output_limit_bytes: int = Field(
        default=1024 * 1024, ge=1024, le=16 * 1024 * 1024
    )
    sandbox_object_limit_bytes: int = Field(
        default=16 * 1024 * 1024, ge=1024, le=128 * 1024 * 1024
    )
    sandbox_compile_memory_mb: int = Field(default=512, ge=64, le=2048)
    sandbox_compile_timeout_seconds: float = Field(default=20, ge=1, le=120)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def sandbox_nano_cpus(self) -> int:
        return int(self.sandbox_cpus * 1_000_000_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
