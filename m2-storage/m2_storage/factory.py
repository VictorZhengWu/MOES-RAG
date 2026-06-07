"""
Backend factory that reads StorageConfig and instantiates concrete backends.

WHY: Upper modules must never know about concrete backend classes.
The factory encapsulates the mapping from config.backend strings to
actual implementations. When we add Qdrant/PostgreSQL/etc in Phase 3,
only this file changes -- no consumer code needs updating.

Design: Each _create_* function is a simple dispatch (if/elif).
We deliberately avoid plugin registry patterns -- 4 backends, YAGNI.
Each function imports its concrete class locally so that a missing
dependency in one backend does not prevent importing this module
(useful when only a subset of backends is installed).

Public API:
    create_storage_manager(config_path) -> StorageManager
        Parse deploy.yaml and return a fully assembled StorageManager.
        This is the only function upper modules should call.

    _create_vector_store(cfg)  -- testable internal dispatch
    _create_document_index(cfg)  -- testable internal dispatch
    _create_relational_db(cfg)   -- testable internal dispatch
    _create_file_store(cfg)      -- testable internal dispatch
"""

from __future__ import annotations

from .config import (
    DocumentIndexConfig,
    FileStoreConfig,
    RelationalDBConfig,
    StorageConfig,
    VectorStoreConfig,
    load_config,
)
from .document_index.base import BaseDocumentIndex
from .file_store.base import BaseFileStore
from .manager import StorageManager
from .relational_db.base import BaseRelationalDB
from .vector_store.base import BaseVectorStore


# ===========================================================================
# Public API -- the single entry point for all M2 consumers
# ===========================================================================


def create_storage_manager(config_path: str = "deploy.yaml") -> StorageManager:
    """
    Parse deploy.yaml and assemble a StorageManager with all 4 backends.

    This is the primary entry point for M2 consumers (M1, M3, M4, M5).
    Call once at startup to get a fully configured storage layer.

    Args:
        config_path: Path to the deploy.yaml configuration file.
            Defaults to "deploy.yaml" in the current working directory
            for development convenience.

    Returns:
        StorageManager holding backend instances (not yet initialized).
        Call manager.initialize() after creation to start backends.

    Raises:
        FileNotFoundError: If config_path does not exist.
        ValueError: If any backend name in the config is unsupported.
    """
    cfg: StorageConfig = load_config(config_path)

    vector_store = _create_vector_store(cfg.vector_store)
    doc_index = _create_document_index(cfg.document_index)
    relational_db = _create_relational_db(cfg.relational_db)
    file_store = _create_file_store(cfg.file_store)

    return StorageManager(
        vector_store=vector_store,
        doc_index=doc_index,
        relational_db=relational_db,
        file_store=file_store,
    )


# ===========================================================================
# Internal factory functions -- one per storage type
#
# Each function:
#   1. Accepts a typed config object (VectorStoreConfig, etc.)
#   2. Dispatches on cfg.backend to pick the concrete class
#   3. Instantiates the class with the backend-specific sub-config
#   4. Raises ValueError with actionable error message on unknown backend
#
# WHY separate functions: each is testable in isolation without needing
# a full StorageConfig or a complete deploy.yaml file.
# ===========================================================================


def _create_vector_store(cfg: VectorStoreConfig) -> BaseVectorStore:
    """
    Instantiate the configured vector store backend.

    WHY separate function: keeps dispatch logic testable in isolation
    without needing a full StorageConfig. The function accepts the
    typed VectorStoreConfig so callers get IDE autocomplete and type
    checking on the config fields.
    """
    from .vector_store.chromadb_store import ChromaDBStore

    if cfg.backend == "chromadb":
        return ChromaDBStore(cfg.chromadb)
    if cfg.backend == "milvus":
        from .vector_store.milvus_store import MilvusStore
        return MilvusStore(
            host=cfg.milvus.host,
            port=cfg.milvus.port,
            collection_name=cfg.milvus.collection_name,
            vector_dim=cfg.milvus.vector_dim,
        )
    raise ValueError(
        f"Unsupported vector store backend: {cfg.backend}. "
        f"Supported: chromadb, milvus"
    )


def _create_document_index(cfg: DocumentIndexConfig) -> BaseDocumentIndex:
    """
    Instantiate the configured document index backend.

    WHY separate function: Meilisearch is the Personal-mode default.
    Elasticsearch will be added in Phase 3 for SaaS deployments with
    higher throughput requirements and distributed search.
    """
    from .document_index.meilisearch_index import MeilisearchIndex

    if cfg.backend == "meilisearch":
        return MeilisearchIndex(cfg.meilisearch)
    raise ValueError(
        f"Unsupported document index backend: {cfg.backend}. "
        f"Supported: meilisearch"
    )


def _create_relational_db(cfg: RelationalDBConfig) -> BaseRelationalDB:
    """
    Instantiate the configured relational database backend.

    WHY separate function: SQLite is the Personal-mode default
    (zero-config, single file, no server process). PostgreSQL will
    be added in Phase 3 for enterprise deployments that need
    concurrent writers and horizontal scaling.
    """
    from .relational_db.sqlite_db import SQLiteDB

    if cfg.backend == "sqlite":
        return SQLiteDB(cfg.sqlite)
    raise ValueError(
        f"Unsupported relational DB backend: {cfg.backend}. "
        f"Supported: sqlite"
    )


def _create_file_store(cfg: FileStoreConfig) -> BaseFileStore:
    """
    Instantiate the configured file store backend.

    WHY separate function: LocalFS is the Personal-mode default
    (direct filesystem access, no external service). MinIO/S3 will
    be added in Phase 3 for enterprise/SaaS deployments that need
    distributed object storage with presigned URLs.
    """
    from .file_store.local_fs import LocalFSStore

    if cfg.backend == "local_fs":
        return LocalFSStore(cfg.local_fs)
    raise ValueError(
        f"Unsupported file store backend: {cfg.backend}. "
        f"Supported: local_fs"
    )
