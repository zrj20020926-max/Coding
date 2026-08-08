import os
from collections.abc import Generator

import pytest
from alembic import command
from sqlalchemy.engine import make_url

from app.db.migration_bootstrap import make_alembic_config


@pytest.fixture(scope="session")
def postgres_database_url() -> Generator[str, None, None]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    database_name = make_url(database_url).database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Integration tests require a database whose name ends with '_test'")

    command.upgrade(make_alembic_config(database_url), "head")
    yield database_url
