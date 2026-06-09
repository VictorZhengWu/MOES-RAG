"""
Unit tests for factory.py -- backend instantiation from config.

WHY: The factory is the single point where config becomes concrete instances.
If the factory mis-maps backends, the entire system silently uses wrong storage.
"""

import pytest

from m2_storage.config import (
    DocumentIndexConfig,
    FileStoreConfig,
    RelationalDBConfig,
    StorageConfig,
    VectorStoreConfig,
)
from m2_storage.factory import (
    _create_document_index,
    _create_file_store,
    _create_relational_db,
    _create_vector_store,
    create_storage_manager,
)


# ---------------------------------------------------------------------------
# Test 1: Factory produces correct types from valid config
# ---------------------------------------------------------------------------


def test_create_backends_correct_types():
    """
    Each _create_* function must return the correct backend class.

    WHY: Upper modules depend on the factory dispatching to the right
    concrete implementation. A type mismatch here cascades into runtime
    errors throughout the entire storage layer.
    """
    from m2_storage.vector_store.chromadb_store import ChromaDBStore
    from m2_storage.document_index.meilisearch_index import MeilisearchIndex
    from m2_storage.relational_db.sqlite_db import SQLiteDB
    from m2_storage.file_store.local_fs import LocalFSStore

    vs = _create_vector_store(VectorStoreConfig(backend="chromadb"))
    di = _create_document_index(DocumentIndexConfig(backend="meilisearch"))
    rdb = _create_relational_db(RelationalDBConfig(backend="sqlite"))
    fs = _create_file_store(FileStoreConfig(backend="local_fs"))

    assert isinstance(vs, ChromaDBStore)
    assert isinstance(di, MeilisearchIndex)
    assert isinstance(rdb, SQLiteDB)
    assert isinstance(fs, LocalFSStore)


def test_create_postgresql_backend():
    """_create_relational_db must return PostgreSQLDB for postgresql backend.

    WHY: The factory dispatch was just added. This test verifies the new
         branch works end-to-end: config → factory → correct backend type.
    """
    from m2_storage.relational_db.postgresql_db import PostgreSQLDB

    rdb = _create_relational_db(RelationalDBConfig(backend="postgresql"))
    assert isinstance(rdb, PostgreSQLDB), (
        "Factory must return PostgreSQLDB when backend='postgresql'"
    )


def test_create_elasticsearch_backend():
    """_create_document_index must return ElasticsearchIndex for elasticsearch backend.

    WHY: Verifies the new factory dispatch branch works end-to-end.
    """
    from m2_storage.document_index.elasticsearch_index import ElasticsearchIndex

    idx = _create_document_index(DocumentIndexConfig(backend="elasticsearch"))
    assert isinstance(idx, ElasticsearchIndex), (
        "Factory must return ElasticsearchIndex when backend='elasticsearch'"
    )


def test_create_minio_backend():
    """_create_file_store must return MinioS3Store for minio/s3 backends.

    WHY: Verifies both "minio" and "s3" backend strings dispatch correctly.
    """
    from m2_storage.file_store.minio_store import MinioS3Store

    for backend in ("minio", "s3"):
        fs = _create_file_store(FileStoreConfig(backend=backend))
        assert isinstance(fs, MinioS3Store), (
            f"Factory must return MinioS3Store when backend='{backend}'"
        )


# ---------------------------------------------------------------------------
# Test 2: Invalid backend raises ValueError (parameterized across all 4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("factory_fn, config_cls, bad_backend", [
    (_create_vector_store, VectorStoreConfig, "weaviate"),
    (_create_document_index, DocumentIndexConfig, "solr"),
    (_create_relational_db, RelationalDBConfig, "mariadb"),
    (_create_file_store, FileStoreConfig, "ftp"),
])
def test_unsupported_backend(factory_fn, config_cls, bad_backend):
    """
    All 4 _create_* functions must reject unsupported backends.

    WHY parameterized: each backend type has its own dispatch function
    and its own set of supported backends. A single test would only
    cover one code path. Parameterization ensures every dispatch
    function's error branch is exercised, catching copy-paste bugs
    where a function fails to raise ValueError.
    """
    cfg = config_cls(backend=bad_backend)
    with pytest.raises(ValueError, match=bad_backend):
        factory_fn(cfg)


# ---------------------------------------------------------------------------
# Test 3: Missing config file raises FileNotFoundError
# ---------------------------------------------------------------------------


def test_create_storage_manager_file_not_found():
    """
    create_storage_manager must propagate FileNotFoundError for missing config.

    WHY: callers need a clearly typed exception (not a generic OSError
    or NoneType AttributeError) so they can surface a meaningful error
    to the operator and suggest checking the deploy.yaml path.
    """
    with pytest.raises(FileNotFoundError):
        create_storage_manager("./nonexistent.yaml")


# ---------------------------------------------------------------------------
# Test 4: create_storage_manager returns correct type
# ---------------------------------------------------------------------------


def test_create_storage_manager_returns_storage_manager(tmp_path):
    """
    create_storage_manager() must return a StorageManager instance.

    WHY: This is the primary entry point. It must parse a deploy.yaml
    and assemble a full StorageManager with all 4 backends attached.
    """
    from m2_storage.manager import StorageManager

    # Write a minimal deploy.yaml to a temp file
    config_path = tmp_path / "deploy.yaml"
    config_path.write_text("""
deployment_mode: personal
storage:
  vector_store:
    backend: chromadb
    chromadb:
      persist_dir: ./data/chromadb
  document_index:
    backend: meilisearch
    meilisearch:
      host: http://127.0.0.1:7700
  relational_db:
    backend: sqlite
    sqlite:
      path: ./data/test.db
  file_store:
    backend: local_fs
    local_fs:
      root_dir: ./data/files
""")

    manager = create_storage_manager(str(config_path))
    assert isinstance(manager, StorageManager)
    assert manager.vector_store is not None
    assert manager.doc_index is not None
    assert manager.relational_db is not None
    assert manager.file_store is not None
