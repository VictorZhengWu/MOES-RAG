"""
Shared pytest fixtures for all M2 tests.

WHY: Each backend test needs an initialized instance with temp directories.
Centralizing fixture creation here avoids duplicating setup logic across
8 test files and ensures consistent cleanup after tests.
"""

import os
import uuid

import pytest
import pytest_asyncio
import yaml


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a clean data directory for a test run.

    WHAT: Creates a 'data' subdirectory inside pytest's tmp_path.
    Returns the Path object for use by other fixtures.

    WHY: Each test run gets a fresh, isolated directory. Using
    pytest's built-in tmp_path ensures automatic cleanup after
    the test session ends -- no leaked files or databases.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def tmp_config_path(tmp_path, tmp_data_dir):
    """Generate a temporary deploy.yaml for integration tests.

    WHAT: Writes a complete deploy.yaml to a temp file with all
    4 backends configured to use temp directories. Returns the
    path to the generated config file.

    WHY: Integration tests need a real StorageManager assembled by
    create_storage_manager(). This fixture generates a valid config
    pointing all backends at temp directories so tests are isolated
    and don't interfere with each other or with any real data.

    Each backend's collection/index/database name includes a random
    suffix so parallel test runs (via pytest-xdist) don't collide.
    """
    config = {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {
                "backend": "chromadb",
                "chromadb": {
                    "persist_dir": str(tmp_data_dir / "chromadb"),
                    "collection_name": f"test_{uuid.uuid4().hex[:8]}",
                },
            },
            "document_index": {
                "backend": "meilisearch",
                "meilisearch": {
                    "host": os.environ.get(
                        "MEILISEARCH_URL", "http://127.0.0.1:7700"
                    ),
                    "api_key": "",
                    "index_name": f"test_{uuid.uuid4().hex[:8]}",
                },
            },
            "relational_db": {
                "backend": "sqlite",
                "sqlite": {
                    "path": str(tmp_data_dir / "test.db"),
                },
            },
            "file_store": {
                "backend": "local_fs",
                "local_fs": {
                    "root_dir": str(tmp_data_dir / "files"),
                },
            },
        },
    }
    config_path = tmp_path / "deploy_test.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f)
    return config_path


@pytest_asyncio.fixture
async def storage_manager(tmp_config_path):
    """Create a fully assembled and initialized StorageManager from temp config.

    WHAT:
    1. Calls create_storage_manager() to parse config and instantiate all
       4 backends
    2. Calls manager.initialize() to start all backends
    3. Yields the ready-to-use manager to the test
    4. After the test completes, calls manager.close() for cleanup

    This fixture is used by integration tests that need all 4 backends
    running with real implementations (ChromaDB, SQLite, LocalFS).
    Meilisearch may fail to initialize if not running, but ChromaDB,
    SQLite, and LocalFS are embedded and always succeed.

    WHY async fixture: StorageManager.initialize() is async and must
    complete before tests use the manager. Using pytest_asyncio.fixture
    ensures the event loop is properly set up for the async lifecycle.
    """
    from m2_storage.factory import create_storage_manager

    mgr = create_storage_manager(str(tmp_config_path))
    await mgr.initialize()
    yield mgr
    await mgr.close()
