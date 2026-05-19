"""
Tests for LocalFSStore -- the Personal-mode file storage backend.

WHY: LocalFS is the primary file store for Personal deployments. It
must correctly handle file CRUD operations, metadata sidecards, and
path traversal attacks. File storage is the most security-sensitive
backend because it interacts directly with the host filesystem.
"""

import json
import os

import pytest
import pytest_asyncio

from contracts.storage import FileStoreProtocol

from m2_storage.config import LocalFSConfig
from m2_storage.file_store.local_fs import LocalFSStore, _is_safe_key


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fs_config(tmp_path):
    """Create a LocalFSConfig pointing at a temp directory."""
    root = tmp_path / "files"
    root.mkdir()
    return LocalFSConfig(root_dir=str(root))


@pytest_asyncio.fixture
async def fs_store(fs_config):
    """Return an initialized LocalFSStore, cleaned up after test."""
    store = LocalFSStore(fs_config)
    await store.initialize()
    yield store
    await store.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_protocol_compliance(fs_store):
    """LocalFSStore must satisfy FileStoreProtocol."""
    assert isinstance(fs_store, FileStoreProtocol)


# ---------------------------------------------------------------------------
# Test 2: put and get round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_put_and_get(fs_store):
    """Data written with put() must be readable with get()."""
    data = b"DNV Rules for Classification of Ships"
    key = "regulations/dnv_rules.pdf"
    stored_key = await fs_store.put(key, data)
    assert stored_key == key
    result = await fs_store.get(key)
    assert result == data


# ---------------------------------------------------------------------------
# Test 3: put with metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_put_with_metadata(fs_store, fs_config):
    """Metadata must be written as a .meta.json sidecar file."""
    data = b"test content"
    meta = {"author": "DNV", "year": "2024"}
    key = "docs/test.pdf"
    await fs_store.put(key, data, metadata=meta)
    meta_path = os.path.join(fs_config.root_dir, key + ".meta.json")
    assert os.path.exists(meta_path)
    with open(meta_path, "r") as f:
        saved_meta = json.load(f)
    assert saved_meta == meta


# ---------------------------------------------------------------------------
# Test 4: delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete(fs_store):
    """Deleting a file must make get() return None."""
    key = "temp/to_delete.txt"
    await fs_store.put(key, b"delete me")
    deleted = await fs_store.delete(key)
    assert deleted is True
    assert await fs_store.get(key) is None


# ---------------------------------------------------------------------------
# Test 5: list by prefix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list(fs_store):
    """list() must return all keys under a prefix, excluding .meta.json sidecars."""
    await fs_store.put("docs/a.txt", b"a")
    await fs_store.put("docs/b.txt", b"b")
    await fs_store.put("other/c.txt", b"c")
    docs = await fs_store.list("docs/")
    assert len(docs) == 2
    assert "docs/a.txt" in docs
    assert "docs/b.txt" in docs
    assert "other/c.txt" not in docs


# ---------------------------------------------------------------------------
# Test 6: get non-existent key returns None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_nonexistent(fs_store):
    """Getting a key that was never written must return None, not raise."""
    result = await fs_store.get("nonexistent/file.pdf")
    assert result is None


# ---------------------------------------------------------------------------
# Test 7: path traversal is rejected
# ---------------------------------------------------------------------------

def test_path_traversal_rejected():
    """Keys containing '..' must be rejected for security.

    WHY path traversal protection is non-negotiable: user-provided
    keys are used to construct filesystem paths. Without validation,
    a malicious key like '../../../etc/passwd' could read or overwrite
    arbitrary files outside the storage root.
    """
    # Unix-style traversal
    assert not _is_safe_key("../etc/passwd")
    assert not _is_safe_key("docs/../../../etc/shadow")
    # Windows-style traversal (backslash)
    assert not _is_safe_key("foo/..\\bar")
    # Absolute paths
    assert not _is_safe_key("/etc/hosts")
    # Windows drive letters
    assert not _is_safe_key("C:\\Windows\\System32")
    # Safe keys
    assert _is_safe_key("docs/regulations.pdf")
    assert _is_safe_key("subdir/nested/file.txt")


@pytest.mark.asyncio
async def test_put_rejects_traversal(fs_store):
    """put() with a traversal key must raise ValueError."""
    with pytest.raises(ValueError, match="path traversal"):
        await fs_store.put("../etc/hosts", b"malicious")


# ---------------------------------------------------------------------------
# Test 8: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(fs_store):
    """Initialized store must report healthy."""
    assert await fs_store.health_check() is True
