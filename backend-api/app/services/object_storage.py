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

    async def get_source(self, object_key: str) -> bytes: ...

    async def get_test_data(self, object_key: str) -> bytes: ...


class MinioSourceObjectStore:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self.test_data_bucket = settings.minio_test_data_bucket

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

    def _get_source(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            content = response.read(settings.submission_source_max_bytes + 1)
            if len(content) > settings.submission_source_max_bytes:
                raise ValueError("stored source exceeds configured source limit")
            return content
        finally:
            response.close()
            response.release_conn()

    async def get_source(self, object_key: str) -> bytes:
        return await run_in_threadpool(self._get_source, object_key)

    def _get_test_data(self, object_key: str) -> bytes:
        response = self.client.get_object(self.test_data_bucket, object_key)
        try:
            content = response.read(settings.test_data_object_max_bytes + 1)
            if len(content) > settings.test_data_object_max_bytes:
                raise ValueError("stored test object exceeds configured limit")
            return content
        finally:
            response.close()
            response.release_conn()

    async def get_test_data(self, object_key: str) -> bytes:
        return await run_in_threadpool(self._get_test_data, object_key)


@lru_cache
def get_source_object_store() -> SourceObjectStore:
    return MinioSourceObjectStore()
