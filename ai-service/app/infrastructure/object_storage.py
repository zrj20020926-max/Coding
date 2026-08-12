from functools import partial

from minio import Minio

from app.core.config import Settings


class SourceStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def _read(self, object_key: str) -> str:
        response = self.client.get_object(self.settings.minio_source_bucket, object_key)
        try:
            content = response.read(self.settings.source_max_bytes + 1)
            if len(content) > self.settings.source_max_bytes:
                raise ValueError("stored source exceeds the configured limit")
            return content.decode("utf-8")
        finally:
            response.close()
            response.release_conn()

    async def get_source(self, object_key: str) -> str:
        import asyncio

        return await asyncio.to_thread(partial(self._read, object_key))
