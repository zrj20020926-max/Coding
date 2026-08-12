from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from minio import Minio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.bootstrap.content import run_content_bootstrap
from app.db.migration_bootstrap import make_alembic_config
from app.services.object_storage import MinioSourceObjectStore

CONTENT_ROOT = Path(__file__).resolve().parents[3] / "content"


async def _create_database(admin_url: str, database_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        await engine.dispose()


async def _drop_database(admin_url: str, database_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fresh_postgres_and_minio_initialize_and_remain_idempotent(
    postgres_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = os.getenv("TEST_CONTENT_MINIO_ENDPOINT")
    access_key = os.getenv("TEST_CONTENT_MINIO_ACCESS_KEY")
    secret_key = os.getenv("TEST_CONTENT_MINIO_SECRET_KEY")
    bucket = os.getenv("TEST_CONTENT_MINIO_BUCKET")
    if not all((endpoint, access_key, secret_key, bucket)):
        pytest.skip("real content MinIO integration configuration is not set")

    database_name = f"content_{uuid4().hex[:8]}_test"
    database_url = make_url(postgres_database_url).set(database=database_name)
    rendered_url = database_url.render_as_string(hide_password=False)
    minio = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    if not minio.bucket_exists(bucket):
        minio.make_bucket(bucket)
    existing_objects = [item.object_name for item in minio.list_objects(bucket, recursive=True)]
    for object_name in existing_objects:
        minio.remove_object(bucket, object_name)

    await _create_database(postgres_database_url, database_name)
    engine = create_async_engine(rendered_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        await asyncio.to_thread(
            command.upgrade, make_alembic_config(rendered_url), "head"
        )
        monkeypatch.setattr("app.core.config.settings.minio_endpoint", endpoint)
        monkeypatch.setattr("app.core.config.settings.minio_access_key", access_key)
        monkeypatch.setattr("app.core.config.settings.minio_secret_key", secret_key)
        monkeypatch.setattr("app.core.config.settings.minio_test_data_bucket", bucket)
        store = MinioSourceObjectStore()
        async with session_factory() as session:
            first = await run_content_bootstrap(
                CONTENT_ROOT / "manifest.yaml", db=session, store=store
            )
            second = await run_content_bootstrap(
                CONTENT_ROOT / "manifest.yaml", db=session, store=store
            )
        assert first.problems.created == 3
        assert first.test_sets.created == 3
        assert second.problems.skipped == 3
        assert second.test_sets.skipped == 3
        async with engine.connect() as connection:
            counts = (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM problems WHERE visibility = 'public') "
                        "AS problems, "
                        "(SELECT count(*) FROM test_sets WHERE status = 'active') "
                        "AS active_sets, "
                        "(SELECT count(*) FROM collections WHERE is_public) "
                        "AS collections, "
                        "(SELECT count(*) FROM collection_problems) AS collection_items, "
                        "(SELECT count(*) FROM daily_challenges WHERE challenge_date = :today) "
                        "AS daily"
                    ),
                    {"today": datetime.now(ZoneInfo("Asia/Shanghai")).date()},
                )
            ).mappings().one()
        assert counts == {
            "problems": 3,
            "active_sets": 3,
            "collections": 1,
            "collection_items": 3,
            "daily": 1,
        }
        objects = [item.object_name for item in minio.list_objects(bucket, recursive=True)]
        assert len(objects) == 12
    finally:
        await engine.dispose()
        await _drop_database(postgres_database_url, database_name)
        for item in minio.list_objects(bucket, recursive=True):
            minio.remove_object(bucket, item.object_name)
