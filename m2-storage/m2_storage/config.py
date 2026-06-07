"""
Configuration models and YAML parser for M2 storage backends.

WHY: deploy.yaml is the single source of truth for backend selection.
These dataclasses provide type-safe access to every configuration value
so that factory functions can instantiate backends without string-key
dictionary lookups that would fail silently on typos.

Design: stdlib dataclasses (not Pydantic) to keep M2 dependency-light.
Each sub-config has a from_dict() factory that fills defaults for
missing keys, so the YAML file can be minimal in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ===========================================================================
# Per-backend configuration dataclasses
# ===========================================================================


@dataclass
@dataclass
class MilvusConfig:
    """Milvus vector store connection parameters.

    WHAT: Holds host/port/collection/dimension for Milvus gRPC connection.
    Milvus runs as a separate service (not embedded like ChromaDB).
    """
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "marine_rag"
    vector_dim: int = 1024

    @classmethod
    def from_dict(cls, d: dict) -> "MilvusConfig":
        return cls(
            host=d.get("host", "localhost"),
            port=d.get("port", 19530),
            collection_name=d.get("collection_name", "marine_rag"),
            vector_dim=d.get("vector_dim", 1024),
        )


@dataclass
class ChromaDBConfig:
    """Configuration for the ChromaDB vector store backend."""

    persist_dir: str = "./data/chromadb"
    collection_name: str = "marine_rag"

    @classmethod
    def from_dict(cls, d: dict | None = None) -> "ChromaDBConfig":
        if d is None:
            return cls()
        return cls(
            persist_dir=d.get("persist_dir", "./data/chromadb"),
            collection_name=d.get("collection_name", "marine_rag"),
        )


@dataclass
class MeilisearchConfig:
    """Configuration for the Meilisearch document index backend.

    WHY separate from DocumentIndexConfig: when we add Elasticsearch in
    Phase 3, each backend will have its own config dataclass with
    different fields. This keeps backend-specific parameters namespaced.
    """

    host: str = "http://127.0.0.1:7700"
    api_key: str = ""
    index_name: str = "marine_rag_docs"

    @classmethod
    def from_dict(cls, d: dict | None) -> MeilisearchConfig:
        if d is None:
            return cls()
        return cls(
            host=d.get("host", "http://127.0.0.1:7700"),
            api_key=d.get("api_key", ""),
            index_name=d.get("index_name", "marine_rag_docs"),
        )


@dataclass
class SQLiteConfig:
    """Configuration for the SQLite relational database backend.

    WHY separate from RelationalDBConfig: when we add PostgreSQL in
    Phase 3, each backend will have its own config dataclass with
    different fields (e.g., connection URLs vs file paths). This keeps
    backend-specific parameters namespaced.
    """

    path: str = "./data/marine_rag.db"

    @classmethod
    def from_dict(cls, d: dict | None) -> SQLiteConfig:
        if d is None:
            return cls()
        return cls(path=d.get("path", "./data/marine_rag.db"))


@dataclass
class LocalFSConfig:
    """Configuration for the local filesystem storage backend.

    WHY separate from FileStoreConfig: when we add S3/MinIO in
    Phase 3, each backend will have its own config dataclass with
    different fields (e.g., bucket names vs local directories). This
    keeps backend-specific parameters namespaced.
    """

    root_dir: str = "./data/files"

    @classmethod
    def from_dict(cls, d: dict | None) -> LocalFSConfig:
        if d is None:
            return cls()
        return cls(root_dir=d.get("root_dir", "./data/files"))


# ===========================================================================
# Storage-type wrapper configs (backend selector + backend-specific section)
# ===========================================================================


@dataclass
class VectorStoreConfig:
    """Vector store configuration: which backend and its parameters.

    WHY the wrapper pattern: decouples backend selection from backend-specific
    parameters. The factory reads the ``backend`` field to pick the concrete
    class, then passes the matching sub-config to its constructor. Adding a new
    backend means adding one field here and one from_dict() branch -- nothing
    else in the codebase changes.
    """

    backend: str = "chromadb"
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)
    milvus: MilvusConfig = field(default_factory=MilvusConfig)

    @classmethod
    def from_dict(cls, d: dict) -> VectorStoreConfig:
        backend = d.get("backend", "chromadb")
        if backend == "chromadb":
            return cls(backend=backend, chromadb=ChromaDBConfig.from_dict(d.get("chromadb", {})))
        if backend == "milvus":
            return cls(backend=backend, milvus=MilvusConfig.from_dict(d.get("milvus", {})))
        raise ValueError(
            f"Unsupported vector store backend: {backend}. "
            f"Supported: chromadb, milvus"
        )
        return cls(
            backend=backend,
            chromadb=ChromaDBConfig.from_dict(d.get("chromadb")),
        )


@dataclass
class DocumentIndexConfig:
    """Document index configuration: which backend and its parameters.

    WHY the wrapper pattern: decouples backend selection from backend-specific
    parameters. The factory reads the ``backend`` field to pick the concrete
    class, then passes the matching sub-config to its constructor. Adding a new
    backend means adding one field here and one from_dict() branch -- nothing
    else in the codebase changes.
    """

    backend: str = "meilisearch"
    meilisearch: MeilisearchConfig = field(default_factory=MeilisearchConfig)

    @classmethod
    def from_dict(cls, d: dict) -> DocumentIndexConfig:
        backend = d.get("backend", "meilisearch")
        if backend != "meilisearch":
            raise ValueError(
                f"Unsupported document index backend: {backend}. "
                f"Supported: meilisearch"
            )
        return cls(
            backend=backend,
            meilisearch=MeilisearchConfig.from_dict(d.get("meilisearch")),
        )


@dataclass
class RelationalDBConfig:
    """Relational database configuration: which backend and its parameters.

    WHY the wrapper pattern: decouples backend selection from backend-specific
    parameters. The factory reads the ``backend`` field to pick the concrete
    class, then passes the matching sub-config to its constructor. Adding a new
    backend means adding one field here and one from_dict() branch -- nothing
    else in the codebase changes.
    """

    backend: str = "sqlite"
    sqlite: SQLiteConfig = field(default_factory=SQLiteConfig)

    @classmethod
    def from_dict(cls, d: dict) -> RelationalDBConfig:
        backend = d.get("backend", "sqlite")
        if backend != "sqlite":
            raise ValueError(
                f"Unsupported relational DB backend: {backend}. "
                f"Supported: sqlite"
            )
        return cls(
            backend=backend,
            sqlite=SQLiteConfig.from_dict(d.get("sqlite")),
        )


@dataclass
class FileStoreConfig:
    """File store configuration: which backend and its parameters.

    WHY the wrapper pattern: decouples backend selection from backend-specific
    parameters. The factory reads the ``backend`` field to pick the concrete
    class, then passes the matching sub-config to its constructor. Adding a new
    backend means adding one field here and one from_dict() branch -- nothing
    else in the codebase changes.
    """

    backend: str = "local_fs"
    local_fs: LocalFSConfig = field(default_factory=LocalFSConfig)

    @classmethod
    def from_dict(cls, d: dict) -> FileStoreConfig:
        backend = d.get("backend", "local_fs")
        if backend != "local_fs":
            raise ValueError(
                f"Unsupported file store backend: {backend}. "
                f"Supported: local_fs"
            )
        return cls(
            backend=backend,
            local_fs=LocalFSConfig.from_dict(d.get("local_fs")),
        )


# ===========================================================================
# Top-level config
# ===========================================================================


@dataclass
class StorageConfig:
    """Root configuration object parsed from deploy.yaml.

    Holds the deployment mode and all four storage backend configs.

    WHY a single root object: factory.py and manager.py receive exactly one
    config argument rather than four separate objects. This guarantees they
    always operate on a consistent snapshot from the same deploy.yaml parse --
    no risk of mixing configs from different files or different points in time.
    """

    deployment_mode: str = "personal"
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    document_index: DocumentIndexConfig = field(
        default_factory=DocumentIndexConfig
    )
    relational_db: RelationalDBConfig = field(
        default_factory=RelationalDBConfig
    )
    file_store: FileStoreConfig = field(default_factory=FileStoreConfig)

    @classmethod
    def from_dict(cls, d: dict) -> StorageConfig:
        storage = d.get("storage", {})
        mode = d.get("deployment_mode", "personal")
        if mode not in ("personal", "enterprise", "saas"):
            raise ValueError(
                f"Invalid deployment_mode: {mode!r}. "
                f"Supported: personal, enterprise, saas"
            )
        return cls(
            deployment_mode=mode,
            vector_store=VectorStoreConfig.from_dict(
                storage.get("vector_store", {})
            ),
            document_index=DocumentIndexConfig.from_dict(
                storage.get("document_index", {})
            ),
            relational_db=RelationalDBConfig.from_dict(
                storage.get("relational_db", {})
            ),
            file_store=FileStoreConfig.from_dict(
                storage.get("file_store", {})
            ),
        )


# ===========================================================================
# Public API
# ===========================================================================


def load_config(path: str = "deploy.yaml") -> StorageConfig:
    """Parse a deploy.yaml file into a typed StorageConfig object.

    WHY: Centralized loading function ensures consistent error handling
    and allows callers to pass either a string path or rely on the default.
    The function validates file existence early (fail-fast) rather than
    letting yaml.safe_load produce an opaque error.

    Args:
        path: Filesystem path to the deploy.yaml file.

    Returns:
        StorageConfig with all fields populated from the YAML.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If any backend name is not supported.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}

    return StorageConfig.from_dict(raw)
