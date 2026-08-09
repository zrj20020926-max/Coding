import asyncio
from typing import Protocol

from minio import Minio
from minio.error import MinioException

from app.errors import InfrastructureError


class JudgeObjectStore(Protocol):
    async def get_source(self, object_key: str) -> bytes: ...

    async def get_test_input(self, object_key: str) -> bytes: ...

    async def get_test_output(self, object_key: str) -> bytes: ...


class MinioJudgeObjectStore:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        source_bucket: str,
        test_data_bucket: str,
        secure: bool,
        object_limit_bytes: int,
    ) -> None:
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.source_bucket = source_bucket
        self.test_data_bucket = test_data_bucket
        self.object_limit_bytes = object_limit_bytes

    def _read(self, bucket: str, object_key: str) -> bytes:
        response = None
        try:
            response = self.client.get_object(bucket, object_key)
            content = response.read(self.object_limit_bytes + 1)
            if len(content) > self.object_limit_bytes:
                raise InfrastructureError("MinIO object exceeds configured judge limit")
            return content
        except MinioException as exc:
            raise InfrastructureError("MinIO object read failed") from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    async def get_source(self, object_key: str) -> bytes:
        return await asyncio.to_thread(self._read, self.source_bucket, object_key)

    async def get_test_input(self, object_key: str) -> bytes:
        return await asyncio.to_thread(self._read, self.test_data_bucket, object_key)

    async def get_test_output(self, object_key: str) -> bytes:
        return await asyncio.to_thread(self._read, self.test_data_bucket, object_key)
