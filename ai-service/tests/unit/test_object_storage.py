import pytest

from app.core.config import Settings
from app.infrastructure.object_storage import SourceStore


@pytest.mark.unit
def test_source_store_uses_configured_region_without_bucket_location_permission() -> None:
    store = SourceStore(Settings(minio_region="us-east-1"))

    assert store.client._base_url._region == "us-east-1"
