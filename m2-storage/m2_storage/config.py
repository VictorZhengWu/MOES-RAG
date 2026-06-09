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
class QdrantConfig:
    """Qdrant vector store connection parameters.

    Qdrant is a lightweight, Rust-based vector database. Single Docker
    container (no etcd/minio dependency unlike Milvus). Recommended for
    enterprise deployments that want simplicity.
    """
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "marine_rag"
    vector_dim: int = 1024
    api_key: str = ""  # Optional, for Qdrant Cloud

    @classmethod
    def from_dict(cls, d: dict | None = None) -> "QdrantConfig":
        if d is None:
            return cls()
        return cls(
            host=d.get("host", "localhost"),
            port=d.get("port", 6333),
            collection_name=d.get("collection_name", "marine_rag"),
            vector_dim=d.get("vector_dim", 1024),
            api_key=d.get("api_key", ""),
        )


@dataclass
class FAISSConfig:
    """FAISS vector index config. Pure library, no server."""
    index_dir: str = "./data/faiss"
    index_type: str = "IVFFlat"
    nlist: int = 100

    @classmethod
    def from_dict(cls, d: dict | None = None) -> "FAISSConfig":
        if d is None:
            return cls()
        return cls(
            index_dir=d.get("index_dir", "./data/faiss"),
            index_type=d.get("index_type", "IVFFlat"),
            nlist=d.get("nlist", 100),
        )


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
class ElasticsearchConfig:
    """Elasticsearch connection parameters for DocumentIndex.

    WHAT: Holds host/port/index_name/user/password for Elasticsearch
          connections. Supports both HTTP and HTTPS with optional auth.

    WHY: Elasticsearch is the recommended full-text engine for SaaS
         deployments where Meilisearch's single-node architecture is
         insufficient. ES provides sharding, replication, and the most
         mature full-text search ecosystem.
    """

    host: str = "http://localhost:9200"
    index_name: str = "marine_rag_docs"
    user: str = ""         # Basic auth user (blank = no auth)
    password: str = ""     # Basic auth password (blank = no auth)
    num_shards: int = 1    # Primary shards per index
    num_replicas: int = 0  # Replica shards (0=no HA, 1+=HA)
    request_timeout: int = 30  # Seconds for search/index operations

    @classmethod
    def from_dict(cls, d: dict | None = None) -> "ElasticsearchConfig":
        if d is None:
            return cls()
        return cls(
            host=d.get("host", "http://localhost:9200"),
            index_name=d.get("index_name", "marine_rag_docs"),
            user=d.get("user", ""),
            password=d.get("password", ""),
            num_shards=d.get("num_shards", 1),
            num_replicas=d.get("num_replicas", 0),
            request_timeout=d.get("request_timeout", 30),
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
class PostgreSQLConfig:
    """PostgreSQL connection parameters for RelationalDB.

    WHAT: Holds host/port/database/user/password/pool settings and SSL
          mode for PostgreSQL connections via asyncpg driver.

    WHY: PostgreSQL is the recommended relational database for Enterprise
         and SaaS deployments where concurrent write performance and
         connection pooling are needed. Each field maps to a SQLAlchemy
         engine parameter or connection string component.
    """

    host: str = "localhost"
    port: int = 5432
    database: str = "marine_rag"
    user: str = "postgres"
    password: str = ""  # Use env var ${PG_PASSWORD} in production
    pool_size: int = 10  # Base pool connections, range 1-50
    max_overflow: int = 20  # Extra connections beyond pool_size, range 0-100
    ssl_mode: str = "prefer"  # "disable" | "allow" | "prefer" | "require"

    @classmethod
    def from_dict(cls, d: dict | None = None) -> "PostgreSQLConfig":
        if d is None:
            return cls()
        return cls(
            host=d.get("host", "localhost"),
            port=d.get("port", 5432),
            database=d.get("database", "marine_rag"),
            user=d.get("user", "postgres"),
            password=d.get("password", ""),
            pool_size=d.get("pool_size", 10),
            max_overflow=d.get("max_overflow", 20),
            ssl_mode=d.get("ssl_mode", "prefer"),
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


@dataclass
class MinioS3Config:
    """MinIO / AWS S3 object storage configuration.

    WHAT: Connection parameters for S3-compatible object storage.
          Works with both MinIO (self-hosted) and AWS S3 (cloud).
          MinIO uses endpoint; S3 uses region.

    WHY: MinIO/S3 is the recommended file store for SaaS deployments
         where files must be shared across multiple application instances
         and backed up independently of the application server.
    """

    endpoint: str = "localhost:9000"   # MinIO server (blank for AWS S3)
    access_key: str = "minioadmin"     # MinIO access key or AWS_ACCESS_KEY_ID
    secret_key: str = "minioadmin"     # MinIO secret key or AWS_SECRET_ACCESS_KEY
    bucket: str = "marine-rag"         # Bucket name
    region: str = ""                   # AWS region (empty for MinIO)
    secure: bool = False               # Use HTTPS (True for AWS S3)
    presigned_expiry: int = 3600       # Presigned URL TTL in seconds

    @classmethod
    def from_dict(cls, d: dict | None = None) -> "MinioS3Config":
        if d is None:
            return cls()
        return cls(
            endpoint=d.get("endpoint", "localhost:9000"),
            access_key=d.get("access_key", "minioadmin"),
            secret_key=d.get("secret_key", "minioadmin"),
            bucket=d.get("bucket", "marine-rag"),
            region=d.get("region", ""),
            secure=bool(d.get("secure", False)),
            presigned_expiry=d.get("presigned_expiry", 3600),
        )


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
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    milvus: MilvusConfig = field(default_factory=MilvusConfig)
    faiss: FAISSConfig = field(default_factory=FAISSConfig)

    @classmethod
    def from_dict(cls, d: dict) -> VectorStoreConfig:
        backend = d.get("backend", "chromadb")
        if backend == "chromadb":
            return cls(backend=backend, chromadb=ChromaDBConfig.from_dict(d.get("chromadb", {})))
        if backend == "qdrant":
            return cls(backend=backend, qdrant=QdrantConfig.from_dict(d.get("qdrant", {})))
        if backend == "milvus":
            return cls(backend=backend, milvus=MilvusConfig.from_dict(d.get("milvus", {})))
        if backend == "faiss":
            return cls(backend=backend, faiss=FAISSConfig.from_dict(d.get("faiss", {})))
        raise ValueError(
            f"Unsupported vector store backend: {backend}. "
            f"Supported: chromadb, qdrant, milvus, faiss"
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
    elasticsearch: ElasticsearchConfig = field(default_factory=ElasticsearchConfig)

    @classmethod
    def from_dict(cls, d: dict) -> DocumentIndexConfig:
        backend = d.get("backend", "meilisearch")
        if backend == "meilisearch":
            return cls(
                backend=backend,
                meilisearch=MeilisearchConfig.from_dict(d.get("meilisearch")),
            )
        if backend == "elasticsearch":
            return cls(
                backend=backend,
                elasticsearch=ElasticsearchConfig.from_dict(d.get("elasticsearch")),
            )
        raise ValueError(
            f"Unsupported document index backend: {backend}. "
            f"Supported: meilisearch, elasticsearch"
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
    postgresql: PostgreSQLConfig = field(default_factory=PostgreSQLConfig)

    @classmethod
    def from_dict(cls, d: dict) -> RelationalDBConfig:
        backend = d.get("backend", "sqlite")
        if backend == "sqlite":
            return cls(
                backend=backend,
                sqlite=SQLiteConfig.from_dict(d.get("sqlite")),
            )
        if backend == "postgresql":
            return cls(
                backend=backend,
                postgresql=PostgreSQLConfig.from_dict(d.get("postgresql")),
            )
        raise ValueError(
            f"Unsupported relational DB backend: {backend}. "
            f"Supported: sqlite, postgresql"
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
    minio: MinioS3Config = field(default_factory=MinioS3Config)

    @classmethod
    def from_dict(cls, d: dict) -> FileStoreConfig:
        backend = d.get("backend", "local_fs")
        if backend == "local_fs":
            return cls(
                backend=backend,
                local_fs=LocalFSConfig.from_dict(d.get("local_fs")),
            )
        if backend == "minio":
            return cls(
                backend=backend,
                minio=MinioS3Config.from_dict(d.get("minio")),
            )
        if backend == "s3":
            return cls(
                backend=backend,
                minio=MinioS3Config.from_dict(d.get("s3")),
            )
        raise ValueError(
            f"Unsupported file store backend: {backend}. "
            f"Supported: local_fs, minio, s3"
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
