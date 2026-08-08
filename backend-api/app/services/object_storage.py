from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from typing import Protocol

from fastapi.concurrency import run_in_threadpool
from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class SourceObjectStore(Protocol):
    async def put_source(self, object_key: str, content: bytes) -> None: ...

    async def delete_source(self, object_key: str) -> None: ...


class MinioSourceObjectStore:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    def _put_source(self, object_key: str, content: bytes) -> None:
        if not self.client.bucket_exists(self.bucket):
            try:
                self.client.make_bucket(self.bucket)
            except S3Error as exc:
                if exc.code != "BucketAlreadyOwnedByYou":
                    raise
        self.client.put_object(
            self.bucket,
            object_key,
            BytesIO(content),
            length=len(content),
            content_type="text/plain; charset=utf-8",
        )

    async def put_source(self, object_key: str, content: bytes) -> None:
        await run_in_threadpool(self._put_source, object_key, content)

    async def delete_source(self, object_key: str) -> None:
        await run_in_threadpool(self.client.remove_object, self.bucket, object_key)


@lru_cache
def get_source_object_store() -> SourceObjectStore:
    return MinioSourceObjectStore()
