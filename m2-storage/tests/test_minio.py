"""
Tests for MinioS3Store -- the Enterprise/SaaS object storage backend.

WHAT: Verifies MinioS3Store satisfies FileStoreProtocol, provides working
      put/get/delete/list operations, generates presigned URLs, and
      handles connection failures gracefully.

REQUIREMENTS:
    - MinIO server (local, Docker, or remote)
    - Defaults: localhost:9000, minioadmin/minioadmin
    - Override via: MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY env vars

    # Docker (quickest):
    docker run -d --name minio-test -p 9000:9000 -p 9001:9001 \
      -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
      minio/minio server /data --console-address :9001

    # No MinIO available: tests auto-skip
"""

import asyncio
import os

import pytest
import pytest_asyncio

from contracts.storage import FileStoreProtocol

from m2_storage.config import MinioS3Config
from m2_storage.file_store.minio_store import MinioS3Store


# ---------------------------------------------------------------------------
# Auto-detect MinIO availability
# ---------------------------------------------------------------------------

def _minio_is_available() -> bool:
    """Fast TCP check to see if MinIO is reachable."""
    import socket
    host = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    h, _, p = host.partition(":")
    try:
        sock = socket.create_connection((h, int(p) if p else 9000), timeout=1.5)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


MINIO_AVAILABLE = _minio_is_available()

requires_minio = pytest.mark.skipif(
    not MINIO_AVAILABLE,
    reason="MinIO not available. Start with: "
           "docker run -d --name minio-test -p 9000:9000 -p 9001:9001 "
           "-e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin "
           "minio/minio server /data --console-address :9001"
)


def _minio_config() -> MinioS3Config:
    return MinioS3Config(
        endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        bucket="test-marine-rag",
        secure=False,
        presigned_expiry=60,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def minio_store():
    """Return an initialized MinioS3Store, cleaned up after test."""
    if not MINIO_AVAILABLE:
        pytest.skip("MinIO not available")
    config = _minio_config()
    store = MinioS3Store(config)
    await store.initialize()
    yield store
    # Cleanup: remove test objects + bucket
    try:
        objects = await store.list("")
        for obj in objects:
            await store.delete(obj)
        if store._client:
            import asyncio as _asyncio
            await _asyncio.to_thread(store._client.remove_bucket, config.bucket)
    except Exception:
        pass
    await store.close()


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

@requires_minio
def test_protocol_compliance(minio_store):
    assert isinstance(minio_store, FileStoreProtocol)


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

@requires_minio
@pytest.mark.asyncio
async def test_put_and_get(minio_store):
    data = b"DNV Rules for Classification of Ships 2025"
    key = "regulations/dnv_rules.pdf"
    stored = await minio_store.put(key, data)
    assert stored == key
    result = await minio_store.get(key)
    assert result == data


@requires_minio
@pytest.mark.asyncio
async def test_get_nonexistent(minio_store):
    result = await minio_store.get("nonexistent/file.pdf")
    assert result is None


@requires_minio
@pytest.mark.asyncio
async def test_delete(minio_store):
    key = "temp/delete_me.txt"
    await minio_store.put(key, b"delete me")
    deleted = await minio_store.delete(key)
    assert deleted is True
    assert await minio_store.get(key) is None


@requires_minio
@pytest.mark.asyncio
async def test_delete_nonexistent(minio_store):
    deleted = await minio_store.delete("never/existed.txt")
    assert deleted is False


@requires_minio
@pytest.mark.asyncio
async def test_list(minio_store):
    await minio_store.put("docs/a.txt", b"a")
    await minio_store.put("docs/b.txt", b"b")
    await minio_store.put("other/c.txt", b"c")
    docs = await minio_store.list("docs/")
    assert len(docs) == 2
    assert "docs/a.txt" in docs
    assert "docs/b.txt" in docs


@requires_minio
@pytest.mark.asyncio
async def test_presigned_url(minio_store):
    await minio_store.put("shared/file.pdf", b"test")
    url = await minio_store.get_url("shared/file.pdf")
    assert url is not None
    assert "http" in url


@requires_minio
@pytest.mark.asyncio
async def test_health_check(minio_store):
    assert await minio_store.health_check() is True


@requires_minio
@pytest.mark.asyncio
async def test_path_traversal_rejected(minio_store):
    with pytest.raises(ValueError):
        await minio_store.put("../../etc/hosts", b"malicious")


# ---------------------------------------------------------------------------
# Connection failure (no MinIO needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_failure_graceful():
    """Connecting to an unreachable host must raise during initialize()."""
    config = MinioS3Config(
        endpoint="255.255.255.255:9000",
        access_key="test",
        secret_key="test",
        bucket="test",
    )
    store = MinioS3Store(config)
    with pytest.raises(Exception):
        async with asyncio.timeout(8):
            await store.initialize()
