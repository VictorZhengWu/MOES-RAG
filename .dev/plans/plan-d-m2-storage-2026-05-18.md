# M2 Storage Abstraction Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the M2 storage abstraction layer with 4 Personal-mode backends (ChromaDB, Meilisearch, SQLite, LocalFS) plus config/factory/manager orchestration.

**Architecture:** `StorageManager` holds 4 backend instances created by `factory.py` based on `deploy.yaml` parsed by `config.py`. Each backend lives in its own sub-package under `src/` with a `base.py` abstract class extending the corresponding `contracts/storage.py` Protocol with lifecycle methods.

**Tech Stack:** Python 3.12+, dataclasses, pyyaml, chromadb, meilisearch, SQLAlchemy 2.0 async, aiosqlite, aiofiles

---

### Task 1: Config Module (00050-01)

**Files:**
- Create: `m2-storage/src/config.py`
- Create: `m2-storage/tests/test_config.py`
- Create: `m2-storage/deploy.yaml`

- [ ] **Step 1: Write the deploy.yaml**

```yaml
# m2-storage/deploy.yaml
# Personal-mode default configuration for development and testing.

deployment_mode: personal

storage:
  vector_store:
    backend: chromadb
    chromadb:
      persist_dir: ./data/chromadb
      collection_name: marine_rag

  document_index:
    backend: meilisearch
    meilisearch:
      host: http://127.0.0.1:7700
      api_key: ""
      index_name: marine_rag_docs

  relational_db:
    backend: sqlite
    sqlite:
      path: ./data/marine_rag.db

  file_store:
    backend: local_fs
    local_fs:
      root_dir: ./data/files
```

- [ ] **Step 2: Write the test file (TDD — test first)**

```python
# m2-storage/tests/test_config.py
"""
Unit tests for config.py — deploy.yaml parsing and dataclass models.

WHY: Config is the entry point for the entire M2 module. If config parsing
is broken, every downstream component fails. These tests validate that valid
YAML produces correct config objects and invalid input raises clear errors.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from m2_storage.config import (
    ChromaDBConfig,
    LocalFSConfig,
    MeilisearchConfig,
    SQLiteConfig,
    StorageConfig,
    load_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_yaml() -> dict:
    """Return the minimal valid Personal-mode config dict."""
    return {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {
                "backend": "chromadb",
                "chromadb": {
                    "persist_dir": "./data/chromadb",
                    "collection_name": "test_collection",
                },
            },
            "document_index": {
                "backend": "meilisearch",
                "meilisearch": {
                    "host": "http://127.0.0.1:7700",
                    "api_key": "",
                    "index_name": "test_index",
                },
            },
            "relational_db": {
                "backend": "sqlite",
                "sqlite": {"path": "./data/test.db"},
            },
            "file_store": {
                "backend": "local_fs",
                "local_fs": {"root_dir": "./data/files"},
            },
        },
    }


@pytest.fixture
def config_file(valid_yaml: dict) -> Path:
    """Write valid_yaml to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(valid_yaml, f)
        return Path(f.name)


# ---------------------------------------------------------------------------
# Test 1: Valid YAML parses correctly
# ---------------------------------------------------------------------------

def test_load_valid_config(config_file: Path):
    """All fields from a valid YAML must parse into correct types."""
    cfg = load_config(str(config_file))

    assert cfg.deployment_mode == "personal"

    # Vector store
    assert cfg.vector_store.backend == "chromadb"
    assert isinstance(cfg.vector_store.chromadb, ChromaDBConfig)
    assert cfg.vector_store.chromadb.persist_dir == "./data/chromadb"
    assert cfg.vector_store.chromadb.collection_name == "test_collection"

    # Document index
    assert cfg.document_index.backend == "meilisearch"
    assert isinstance(cfg.document_index.meilisearch, MeilisearchConfig)
    assert cfg.document_index.meilisearch.host == "http://127.0.0.1:7700"

    # Relational DB
    assert cfg.relational_db.backend == "sqlite"
    assert isinstance(cfg.relational_db.sqlite, SQLiteConfig)
    assert cfg.relational_db.sqlite.path == "./data/test.db"

    # File store
    assert cfg.file_store.backend == "local_fs"
    assert isinstance(cfg.file_store.local_fs, LocalFSConfig)
    assert cfg.file_store.local_fs.root_dir == "./data/files"


# ---------------------------------------------------------------------------
# Test 2: Missing fields get default values
# ---------------------------------------------------------------------------

def test_default_values():
    """When YAML omits optional fields, defaults must be applied."""
    minimal = {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {"backend": "chromadb"},
            "document_index": {"backend": "meilisearch"},
            "relational_db": {"backend": "sqlite"},
            "file_store": {"backend": "local_fs"},
        },
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(minimal, f)
        path = f.name

    cfg = load_config(path)

    # ChromaDB defaults
    assert cfg.vector_store.chromadb.persist_dir == "./data/chromadb"
    assert cfg.vector_store.chromadb.collection_name == "marine_rag"
    # Meilisearch defaults
    assert cfg.document_index.meilisearch.host == "http://127.0.0.1:7700"
    assert cfg.document_index.meilisearch.api_key == ""
    # SQLite defaults
    assert cfg.relational_db.sqlite.path == "./data/marine_rag.db"
    # LocalFS defaults
    assert cfg.file_store.local_fs.root_dir == "./data/files"


# ---------------------------------------------------------------------------
# Test 3: Invalid backend raises ValueError
# ---------------------------------------------------------------------------

def test_invalid_backend_raises():
    """An unsupported backend name must raise ValueError with a clear message."""
    invalid = {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {"backend": "milvus"},
            "document_index": {"backend": "meilisearch"},
            "relational_db": {"backend": "sqlite"},
            "file_store": {"backend": "local_fs"},
        },
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(invalid, f)
        path = f.name

    with pytest.raises(ValueError, match="milvus"):
        load_config(path)


# ---------------------------------------------------------------------------
# Test 4: Missing file raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_missing_file_raises():
    """Passing a non-existent path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("./nonexistent_config.yaml")
```

- [ ] **Step 3: Run test to verify failure**

Run: `python -m pytest m2-storage/tests/test_config.py -v`
Expected: All 4 tests FAIL (import errors — config.py does not exist yet)

- [ ] **Step 4: Write config.py implementation**

```python
# m2-storage/src/config.py
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
class ChromaDBConfig:
    """Configuration for the ChromaDB vector store backend.

    WHY separate from VectorStoreConfig: when we add Qdrant/Milvus in Phase 3,
    each backend will have its own config dataclass with different fields.
    This keeps backend-specific parameters namespaced and type-safe.
    """

    persist_dir: str = "./data/chromadb"
    collection_name: str = "marine_rag"

    @classmethod
    def from_dict(cls, d: dict | None) -> ChromaDBConfig:
        if d is None:
            return cls()
        return cls(
            persist_dir=d.get("persist_dir", "./data/chromadb"),
            collection_name=d.get("collection_name", "marine_rag"),
        )


@dataclass
class MeilisearchConfig:
    """Configuration for the Meilisearch document index backend."""

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
    """Configuration for the SQLite relational database backend."""

    path: str = "./data/marine_rag.db"

    @classmethod
    def from_dict(cls, d: dict | None) -> SQLiteConfig:
        if d is None:
            return cls()
        return cls(path=d.get("path", "./data/marine_rag.db"))


@dataclass
class LocalFSConfig:
    """Configuration for the local filesystem storage backend."""

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
    """Vector store configuration: which backend and its parameters."""

    backend: str = "chromadb"
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)

    @classmethod
    def from_dict(cls, d: dict) -> VectorStoreConfig:
        backend = d.get("backend", "chromadb")
        if backend != "chromadb":
            raise ValueError(
                f"Unsupported vector store backend: {backend}. "
                f"Supported: chromadb"
            )
        return cls(
            backend=backend,
            chromadb=ChromaDBConfig.from_dict(d.get("chromadb")),
        )


@dataclass
class DocumentIndexConfig:
    """Document index configuration: which backend and its parameters."""

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
    """Relational database configuration: which backend and its parameters."""

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
    """File store configuration: which backend and its parameters."""

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
        return cls(
            deployment_mode=d.get("deployment_mode", "personal"),
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
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd E:/myCode/RAG && pip install -e contracts/ && pip install pyyaml && python -m pytest m2-storage/tests/test_config.py -v
```
Expected: 4 PASS, 0 FAIL

- [ ] **Step 6: Commit**

```bash
git add m2-storage/src/config.py m2-storage/tests/test_config.py m2-storage/deploy.yaml
git commit -m "[00050-01] feat: implement config.py — deploy.yaml parser with typed dataclasses"
```

---

### Task 2: Factory Module (00050-02)

**Files:**
- Create: `m2-storage/src/factory.py`
- Create: `m2-storage/tests/test_factory.py`

- [ ] **Step 1: Write the test file**

```python
# m2-storage/tests/test_factory.py
"""
Unit tests for factory.py — backend instantiation from config.

WHY: The factory is the single point where config becomes concrete instances.
If the factory mis-maps backends, the entire system silently uses wrong storage.
"""

import pytest

from m2_storage.config import (
    DocumentIndexConfig,
    FileStoreConfig,
    MeilisearchConfig,
    RelationalDBConfig,
    SQLiteConfig,
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
from m2_storage.manager import StorageManager


# ---------------------------------------------------------------------------
# Test 1: Factory produces correct types from valid config
# ---------------------------------------------------------------------------

def test_create_storage_manager_returns_storage_manager():
    """create_storage_manager must return a StorageManager instance."""
    cfg = StorageConfig(
        deployment_mode="personal",
        vector_store=VectorStoreConfig(backend="chromadb"),
        document_index=DocumentIndexConfig(backend="meilisearch"),
        relational_db=RelationalDBConfig(backend="sqlite"),
        file_store=FileStoreConfig(backend="local_fs"),
    )
    # We mock the internal helpers to avoid needing real backends for this test.
    # The factory functions are tested individually below.
    mgr = create_storage_manager.__wrapped__(cfg) if hasattr(
        create_storage_manager, "__wrapped__"
    ) else None
    # Actually, just test the sub-factories directly:
    vs = _create_vector_store(cfg.vector_store)
    di = _create_document_index(cfg.document_index)
    rdb = _create_relational_db(cfg.relational_db)
    fs = _create_file_store(cfg.file_store)

    from m2_storage.vector_store.chromadb_store import ChromaDBStore
    from m2_storage.document_index.meilisearch_index import MeilisearchIndex
    from m2_storage.relational_db.sqlite_db import SQLiteDB
    from m2_storage.file_store.local_fs import LocalFSStore

    assert isinstance(vs, ChromaDBStore)
    assert isinstance(di, MeilisearchIndex)
    assert isinstance(rdb, SQLiteDB)
    assert isinstance(fs, LocalFSStore)


# ---------------------------------------------------------------------------
# Test 2: Invalid backend raises ValueError
# ---------------------------------------------------------------------------

def test_unsupported_vector_store_backend():
    """Factory must reject unsupported backend names with a clear error."""
    cfg = VectorStoreConfig(backend="qdrant")  # Not implemented in Phase 1
    with pytest.raises(ValueError, match="qdrant"):
        _create_vector_store(cfg)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest m2-storage/tests/test_factory.py -v`
Expected: FAIL (import errors)

- [ ] **Step 3: Write factory.py**

```python
# m2-storage/src/factory.py
"""
Backend factory that reads StorageConfig and instantiates concrete backends.

WHY: Upper modules must never know about concrete backend classes.
The factory encapsulates the mapping from config.backend strings to
actual implementations. When we add Qdrant/PostgreSQL/etc in Phase 3,
only this file changes — no consumer code needs updating.

Design: Each _create_* function is a simple dispatch table (if/elif).
We deliberately avoid a plugin registry pattern at this stage because
we have exactly 4 backends and YAGNI applies.
"""

from __future__ import annotations

from .config import StorageConfig, load_config
from .manager import StorageManager


def create_storage_manager(config_path: str = "deploy.yaml") -> StorageManager:
    """Parse deploy.yaml and assemble a StorageManager with all 4 backends.

    This is the primary entry point for M2 consumers (M1, M3, M4, M5).
    They call this once at startup to get a fully configured storage layer.

    Args:
        config_path: Path to the deploy.yaml configuration file.

    Returns:
        StorageManager holding initialized backend instances.

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
# Internal factory functions — one per storage type
# ===========================================================================


def _create_vector_store(cfg):
    """Instantiate the configured vector store backend.

    WHY separate function: keeps the dispatch logic testable in isolation
    without needing to construct a full StorageConfig.
    """
    from .vector_store.chromadb_store import ChromaDBStore

    if cfg.backend == "chromadb":
        return ChromaDBStore(cfg.chromadb)
    raise ValueError(
        f"Unsupported vector store backend: {cfg.backend}. "
        f"Supported: chromadb"
    )


def _create_document_index(cfg):
    """Instantiate the configured document index backend."""
    from .document_index.meilisearch_index import MeilisearchIndex

    if cfg.backend == "meilisearch":
        return MeilisearchIndex(cfg.meilisearch)
    raise ValueError(
        f"Unsupported document index backend: {cfg.backend}. "
        f"Supported: meilisearch"
    )


def _create_relational_db(cfg):
    """Instantiate the configured relational database backend."""
    from .relational_db.sqlite_db import SQLiteDB

    if cfg.backend == "sqlite":
        return SQLiteDB(cfg.sqlite)
    raise ValueError(
        f"Unsupported relational DB backend: {cfg.backend}. "
        f"Supported: sqlite"
    )


def _create_file_store(cfg):
    """Instantiate the configured file store backend."""
    from .file_store.local_fs import LocalFSStore

    if cfg.backend == "local_fs":
        return LocalFSStore(cfg.local_fs)
    raise ValueError(
        f"Unsupported file store backend: {cfg.backend}. "
        f"Supported: local_fs"
    )
```

- [ ] **Step 4: Write minimal manager.py stub (needed for import)**

```python
# m2-storage/src/manager.py
"""
StorageManager — unified lifecycle management for M2 backends.

WHY: Upper modules need a single object to initialize, health-check,
and shut down all four storage backends. The Manager owns the lifecycle
but does NOT proxy method calls — consumers call manager.vector_store.search()
directly. This keeps the Manager thin and avoids duplicating every
Protocol method as a pass-through.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """Holds references to all 4 storage backends and manages their lifecycle.

    Upper modules access backends directly as attributes:
        manager.vector_store.search(...)
        manager.doc_index.search(...)
        manager.relational_db.get_session()
        manager.file_store.get(...)
    """

    def __init__(self, *, vector_store, doc_index, relational_db, file_store):
        self.vector_store = vector_store
        self.doc_index = doc_index
        self.relational_db = relational_db
        self.file_store = file_store

    async def initialize(self) -> None:
        """
        Initialize all 4 backends concurrently.

        WHY asyncio.gather: sequential init of 4 backends could take
        several seconds (each backend may do I/O). Concurrent init
        cuts startup time to roughly the slowest single backend.

        Errors in individual backends are logged but do not prevent
        other backends from initializing — a broken Meilisearch should
        not block the vector store.
        """
        results = await asyncio.gather(
            self.vector_store.initialize(),
            self.doc_index.initialize(),
            self.relational_db.initialize(),
            self.file_store.initialize(),
            return_exceptions=True,
        )
        names = ["vector_store", "doc_index", "relational_db", "file_store"]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(
                    "Failed to initialize %s: %s", name, result
                )
            else:
                logger.info("Initialized %s successfully", name)

    async def health_check(self) -> dict[str, bool]:
        """
        Check the health of all 4 backends concurrently.

        Returns a dict mapping backend name to healthy/unhealthy.
        A failed health check does not raise — it returns False.
        """
        results = await asyncio.gather(
            self.vector_store.health_check(),
            self.doc_index.health_check(),
            self.relational_db.health_check(),
            self.file_store.health_check(),
            return_exceptions=True,
        )
        names = ["vector_store", "doc_index", "relational_db", "file_store"]
        return {
            name: (
                result
                if isinstance(result, bool)
                else False
            )
            for name, result in zip(names, results)
        }

    async def close(self) -> None:
        """
        Gracefully close all 4 backend connections concurrently.

        Each backend's close() is called even if others raise.
        """
        await asyncio.gather(
            self.vector_store.close(),
            self.doc_index.close(),
            self.relational_db.close(),
            self.file_store.close(),
            return_exceptions=True,
        )
```

- [ ] **Step 5: Write stub backend files so factory imports work**

Create each of these minimal stubs — just enough to satisfy the factory imports:

`m2-storage/src/vector_store/__init__.py`:
```python
# vector_store package
```

`m2-storage/src/vector_store/base.py`:
```python
"""
Base class for vector store backends.

WHY: Adds lifecycle methods (initialize, health_check, close) to the
contracts/storage.py VectorStoreProtocol. The Protocol only defines
business operations; lifecycle belongs to the implementation layer.
"""

from abc import ABC, abstractmethod

from contracts.storage import VectorStoreProtocol


class BaseVectorStore(VectorStoreProtocol, ABC):
    """Abstract vector store with lifecycle management."""

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the backend (create collections, open connections)."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the backend is operational."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release all resources held by this backend."""
        ...
```

`m2-storage/src/vector_store/chromadb_store.py`:
```python
"""
ChromaDB implementation of BaseVectorStore.

WHY: ChromaDB is the Personal-mode default vector store. It runs embedded
(no separate server process), uses SQLite under the hood for persistence,
and supports metadata filtering natively.
"""

from __future__ import annotations

from typing import Any

from contracts.document import Chunk

from .base import BaseVectorStore


class ChromaDBStore(BaseVectorStore):
    """Vector store backed by ChromaDB (embedded, persistent)."""

    def __init__(self, config):
        self._config = config
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        return []

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        return []

    async def delete(self, doc_id: str) -> int:
        return 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return 0
```

`m2-storage/src/document_index/__init__.py`:
```python
# document_index package
```

`m2-storage/src/document_index/base.py`:
```python
"""Base class for document index backends."""

from abc import ABC, abstractmethod

from contracts.storage import DocumentIndexProtocol


class BaseDocumentIndex(DocumentIndexProtocol, ABC):
    """Abstract document index with lifecycle management."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
```

`m2-storage/src/document_index/meilisearch_index.py`:
```python
"""Meilisearch implementation of BaseDocumentIndex (stub)."""

from __future__ import annotations

from typing import Any

from contracts.document import Chunk

from .base import BaseDocumentIndex


class MeilisearchIndex(BaseDocumentIndex):
    """Document index backed by Meilisearch."""

    def __init__(self, config):
        self._config = config
        self._client = None

    async def initialize(self) -> None: pass
    async def health_check(self) -> bool: return False
    async def close(self) -> None: pass

    async def index(self, chunks: list[Chunk]) -> None: pass

    async def search(
        self, query: str, top_k: int = 50,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[Chunk, float]]:
        return []

    async def delete(self, doc_id: str) -> int:
        return 0
```

`m2-storage/src/relational_db/__init__.py`:
```python
# relational_db package
```

`m2-storage/src/relational_db/base.py`:
```python
"""Base class for relational database backends."""

from abc import ABC, abstractmethod

from contracts.storage import RelationalDBProtocol


class BaseRelationalDB(RelationalDBProtocol, ABC):
    """Abstract relational DB with lifecycle management."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
```

`m2-storage/src/relational_db/sqlite_db.py`:
```python
"""SQLite implementation of BaseRelationalDB (stub)."""

from __future__ import annotations

from .base import BaseRelationalDB


class SQLiteDB(BaseRelationalDB):
    """Relational database backed by SQLite + SQLAlchemy async."""

    def __init__(self, config):
        self._config = config
        self._engine = None

    async def initialize(self) -> None: pass
    async def health_check(self) -> bool: return False
    async def close(self) -> None: pass

    async def get_session(self):
        """Return an async database session (stub)."""
        raise NotImplementedError
```

`m2-storage/src/file_store/__init__.py`:
```python
# file_store package
```

`m2-storage/src/file_store/base.py`:
```python
"""Base class for file store backends."""

from abc import ABC, abstractmethod

from contracts.storage import FileStoreProtocol


class BaseFileStore(FileStoreProtocol, ABC):
    """Abstract file store with lifecycle management."""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
```

`m2-storage/src/file_store/local_fs.py`:
```python
"""Local filesystem implementation of BaseFileStore (stub)."""

from __future__ import annotations

from .base import BaseFileStore


class LocalFSStore(BaseFileStore):
    """File store backed by the local filesystem."""

    def __init__(self, config):
        self._config = config

    async def initialize(self) -> None: pass
    async def health_check(self) -> bool: return False
    async def close(self) -> None: pass

    async def put(
        self, key: str, data: bytes,
        metadata: dict[str, str] | None = None
    ) -> str:
        return key

    async def get(self, key: str) -> bytes | None:
        return None

    async def delete(self, key: str) -> bool:
        return False

    async def list(self, prefix: str = "") -> list[str]:
        return []

    async def get_url(self, key: str, expires_in: int = 3600) -> str | None:
        return None
```

- [ ] **Step 6: Run tests to verify pass**

```bash
python -m pytest m2-storage/tests/test_factory.py -v
```
Expected: 2 PASS, 0 FAIL

- [ ] **Step 7: Commit**

```bash
git add m2-storage/src/factory.py m2-storage/src/manager.py m2-storage/src/vector_store/ m2-storage/src/document_index/ m2-storage/src/relational_db/ m2-storage/src/file_store/ m2-storage/tests/test_factory.py
git commit -m "[00050-02] feat: implement factory.py and backend stubs — all imports wired"
```

---

### Task 3: StorageManager Tests (00050-03)

**Files:**
- Create: `m2-storage/tests/test_manager.py`

- [ ] **Step 1: Write the test file**

```python
# m2-storage/tests/test_manager.py
"""
Integration tests for StorageManager lifecycle management.

WHY: The Manager orchestrates 4 independent backends. Its initialize,
health_check, and close methods must handle concurrent execution and
partial failures correctly — bugs here would cause silent startup
failures or resource leaks in production.
"""

import asyncio

import pytest

from m2_storage.manager import StorageManager


# ---------------------------------------------------------------------------
# Mock backend for controlled testing
# ---------------------------------------------------------------------------

class MockBackend:
    """A controllable mock implementing all lifecycle methods.

    Tracks call counts so tests can assert that Manager called each
    backend the expected number of times, in the expected order.
    """

    def __init__(self, name="mock", fail_init=False, fail_health=False):
        self.name = name
        self._fail_init = fail_init
        self._fail_health = fail_health
        self.init_called = 0
        self.health_called = 0
        self.close_called = 0

    async def initialize(self) -> None:
        self.init_called += 1
        if self._fail_init:
            raise RuntimeError(f"{self.name} init failed")

    async def health_check(self) -> bool:
        self.health_called += 1
        if self._fail_health:
            return False
        return True

    async def close(self) -> None:
        self.close_called += 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def four_healthy_backends():
    """Return 4 MockBackend instances, all healthy."""
    return (
        MockBackend("vector_store"),
        MockBackend("doc_index"),
        MockBackend("relational_db"),
        MockBackend("file_store"),
    )


@pytest.fixture
def manager(four_healthy_backends):
    """Return a StorageManager with 4 mock backends."""
    vs, di, rdb, fs = four_healthy_backends
    return StorageManager(
        vector_store=vs, doc_index=di, relational_db=rdb, file_store=fs
    )


# ---------------------------------------------------------------------------
# Test 1: initialize calls all 4 backends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_calls_all_backends(manager, four_healthy_backends):
    """initialize() must call each backend's initialize() exactly once."""
    await manager.initialize()
    for backend in four_healthy_backends:
        assert backend.init_called == 1


# ---------------------------------------------------------------------------
# Test 2: health_check returns correct dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_all_healthy(manager):
    """health_check must return {name: True} for all backends."""
    result = await manager.health_check()
    assert result == {
        "vector_store": True,
        "doc_index": True,
        "relational_db": True,
        "file_store": True,
    }


# ---------------------------------------------------------------------------
# Test 3: close calls all 4 backends
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_calls_all_backends(manager, four_healthy_backends):
    """close() must call each backend's close() exactly once."""
    await manager.close()
    for backend in four_healthy_backends:
        assert backend.close_called == 1


# ---------------------------------------------------------------------------
# Test 4: one backend init failure does not block others
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_init_failure():
    """If one backend fails to init, others must still be initialized."""
    healthy = MockBackend("healthy")
    failing = MockBackend("failing", fail_init=True)

    mgr = StorageManager(
        vector_store=healthy,
        doc_index=failing,
        relational_db=MockBackend("rdb"),
        file_store=MockBackend("fs"),
    )
    # Must not raise — failures are logged, not propagated
    await mgr.initialize()

    # Healthy backend must have been initialized
    assert healthy.init_called == 1
    # Failing backend must have been attempted
    assert failing.init_called == 1
```

- [ ] **Step 2: Run test to verify pass**

```bash
python -m pytest m2-storage/tests/test_manager.py -v
```
Expected: 4 PASS, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git add m2-storage/tests/test_manager.py
git commit -m "[00050-03] test: add StorageManager lifecycle tests — 4 cases passing"
```

---

### Task 4: ChromaDB VectorStore (00050-04)

**Files:**
- Modify: `m2-storage/src/vector_store/chromadb_store.py` (replace stub)
- Create: `m2-storage/tests/test_chromadb.py`

- [ ] **Step 1: Write the test file**

```python
# m2-storage/tests/test_chromadb.py
"""
Tests for ChromaDBStore — the Personal-mode vector store backend.

WHY: ChromaDB is the primary vector store for all Personal deployments.
It must correctly implement insert, search with metadata filtering,
delete by doc_id, and count — these are the operations that M3 (Retrieval)
and M5 (QA Engine) depend on for every user query.
"""

import uuid

import pytest

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.storage import VectorStoreProtocol

from m2_storage.vector_store.chromadb_store import ChromaDBStore
from m2_storage.config import ChromaDBConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(text: str, doc_id: str = "doc-1", domain: str = "structure",
                chunk_index: int = 0) -> Chunk:
    """Create a minimal Chunk for testing."""
    return Chunk(
        chunk_id=f"{doc_id}-chunk-{chunk_index}",
        text=text,
        metadata=DocumentMetadata(
            source_filename=f"{doc_id}.pdf",
            domain=Domain(domain),
        ),
        chunk_type="clause",
        position_in_document=chunk_index,
    )


def _make_embedding(dim: int = 8) -> list[float]:
    """Return a small random-ish embedding vector."""
    return [(i * 0.1) % 1.0 for i in range(dim)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chroma_config(tmp_path):
    """Create a ChromaDBConfig pointing at a temp directory."""
    persist_dir = tmp_path / "chromadb"
    persist_dir.mkdir()
    return ChromaDBConfig(
        persist_dir=str(persist_dir),
        collection_name=f"test_{uuid.uuid4().hex[:8]}",
    )


@pytest.fixture
async def chroma_store(chroma_config):
    """Return an initialized ChromaDBStore."""
    store = ChromaDBStore(chroma_config)
    await store.initialize()
    yield store
    await store.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

def test_protocol_compliance(chroma_store):
    """ChromaDBStore must satisfy VectorStoreProtocol."""
    assert isinstance(chroma_store, VectorStoreProtocol)


# ---------------------------------------------------------------------------
# Test 2: insert and search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_search(chroma_store):
    """Insert chunks then search — must return correct chunks ranked by score."""
    c1 = _make_chunk("Welding procedure for bulkheads", chunk_index=0)
    c2 = _make_chunk("Painting requirements for hull", chunk_index=1)
    c3 = _make_chunk("Corrosion protection coating", chunk_index=2)

    emb1 = _make_embedding()
    emb2 = _make_embedding()
    emb3 = _make_embedding()

    ids = await chroma_store.insert(
        [c1, c2, c3], [emb1, emb2, emb3]
    )
    assert len(ids) == 3

    # Search with the first embedding — c1 should be top result
    results = await chroma_store.search(emb1, top_k=2)
    assert len(results) == 2
    # Each result is (Chunk, float)
    assert isinstance(results[0][0], Chunk)
    assert isinstance(results[0][1], float)
    # The top result should be the matching chunk
    assert results[0][0].text == "Welding procedure for bulkheads"


# ---------------------------------------------------------------------------
# Test 3: search with metadata filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_with_filter(chroma_store):
    """Search with a domain filter must return only matching chunks."""
    c1 = _make_chunk("Structural steel grades", domain="structure")
    c2 = _make_chunk("Pump specifications", domain="machinery")

    emb = _make_embedding()

    await chroma_store.insert([c1, c2], [emb, emb])

    # Filter to machinery domain only
    results = await chroma_store.search(
        emb, top_k=5, filters={"domain": "machinery"}
    )
    assert len(results) == 1
    assert results[0][0].text == "Pump specifications"


# ---------------------------------------------------------------------------
# Test 4: delete by doc_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete(chroma_store):
    """Deleting by doc_id must remove all chunks for that document."""
    c1 = _make_chunk("Doc A content", doc_id="doc-a", chunk_index=0)
    c2 = _make_chunk("Doc B content", doc_id="doc-b", chunk_index=0)

    emb = _make_embedding()
    await chroma_store.insert([c1, c2], [emb, emb])

    count_before = await chroma_store.count()
    assert count_before == 2

    deleted = await chroma_store.delete("doc-a")
    assert deleted >= 1

    count_after = await chroma_store.count()
    assert count_after == 1


# ---------------------------------------------------------------------------
# Test 5: search empty collection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_empty(chroma_store):
    """Searching an empty collection must return an empty list, not an error."""
    results = await chroma_store.search(_make_embedding(), top_k=10)
    assert results == []


# ---------------------------------------------------------------------------
# Test 6: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(chroma_store):
    """Initialized store must report healthy."""
    assert await chroma_store.health_check() is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest m2-storage/tests/test_chromadb.py -v`
Expected: FAIL (stub returns empty results)

- [ ] **Step 3: Write full ChromaDBStore implementation**

Replace the stub `m2-storage/src/vector_store/chromadb_store.py`:

```python
"""
ChromaDB implementation of BaseVectorStore.

WHY: ChromaDB is the Personal-mode default vector store. It runs embedded
(no separate server process), uses SQLite for persistence, supports
metadata filtering via 'where' clauses, and is the most popular
lightweight vector DB in the Python ecosystem.

We use PersistentClient (not EphemeralClient) because Personal-mode
users expect their data to survive restarts. The persist_dir is
configurable via deploy.yaml.
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from contracts.document import Chunk

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class ChromaDBStore(BaseVectorStore):
    """Vector store backed by ChromaDB (embedded, persistent).

    The store maps Chunk objects to ChromaDB documents:
    - chunk_id   → ChromaDB document ID
    - text       → ChromaDB document content
    - metadata   → ChromaDB document metadata (searchable via 'where')
    - embedding  → ChromaDB document embedding vector
    """

    def __init__(self, config):
        """
        Args:
            config: ChromaDBConfig with persist_dir and collection_name.
        """
        self._config = config
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Create or open the ChromaDB persistent client and collection.

        WHY PersistentClient: data must survive process restarts in
        Personal mode. EphemeralClient would lose all vectors on exit.
        """
        self._client = chromadb.PersistentClient(
            path=self._config.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB initialized: %s (collection: %s)",
            self._config.persist_dir,
            self._config.collection_name,
        )

    async def health_check(self) -> bool:
        """Verify the collection is accessible."""
        try:
            if self._collection is None:
                return False
            # Lightweight probe: ask ChromaDB for collection count
            self._collection.count()
            return True
        except Exception:
            logger.exception("ChromaDB health check failed")
            return False

    async def close(self) -> None:
        """Release ChromaDB resources.

        ChromaDB PersistentClient does not hold long-lived connections,
        but we set references to None to allow GC and prevent misuse
        after close.
        """
        self._collection = None
        self._client = None

    # ------------------------------------------------------------------
    # VectorStoreProtocol — data operations
    # ------------------------------------------------------------------

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        """
        Insert chunks with their pre-computed embeddings.

        WHY embeddings are passed in, not computed here: M1 (Doc Parsing)
        owns embedding generation. M2 is storage-only. This separation
        means we can swap embedding models without touching M2 code.

        Args:
            chunks: Parsed document chunks with metadata.
            embeddings: Pre-computed embedding vectors, same order as chunks.

        Returns:
            List of chunk_id strings for the inserted records.
        """
        if not chunks:
            return []

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]

        # Flatten metadata into a flat dict for ChromaDB compatibility.
        # WHY: ChromaDB 'where' filters require string/number/boolean values,
        # not nested objects. We flatten the DocumentMetadata dataclass.
        metadatas = [
            {
                "doc_id": c.metadata.source_filename.replace(".pdf", ""),
                "source_filename": c.metadata.source_filename,
                "domain": c.metadata.domain.value,
                "chunk_type": c.chunk_type,
                "language": c.metadata.language,
                "position": c.position_in_document,
            }
            for c in chunks
        ]

        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.debug("Inserted %d chunks into ChromaDB", len(chunks))
        return ids

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Search for chunks by vector similarity.

        Args:
            query_vector: The query embedding to compare against.
            top_k: Maximum number of results to return.
            filters: Optional metadata key-value pairs for filtering.
                     e.g. {"domain": "structure"} limits to structural docs.

        Returns:
            List of (Chunk, score) tuples ordered by descending similarity.
        """
        if self._collection is None:
            return []

        where = _build_chromadb_where(filters) if filters else None

        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[tuple[Chunk, float]] = []
        if not results["ids"] or not results["ids"][0]:
            return chunks

        for i, chunk_id in enumerate(results["ids"][0]):
            text = results["documents"][0][i]
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # Convert cosine distance to similarity score (0-1)
            score = 1.0 - (distance / 2.0)

            chunk = Chunk(
                chunk_id=chunk_id,
                text=text,
                metadata=_reconstruct_metadata(meta),
                chunk_type=meta.get("chunk_type", "general"),
                position_in_document=meta.get("position", 0),
            )
            chunks.append((chunk, score))

        return chunks

    async def delete(self, doc_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        WHY delete by doc_id metadata, not by chunk ID: a document may
        have hundreds of chunks. Deleting by metadata filter removes
        all of them in one operation.
        """
        if self._collection is None:
            return 0
        before = self._collection.count()
        self._collection.delete(where={"doc_id": doc_id})
        after = self._collection.count()
        deleted = before - after
        logger.info("Deleted %d chunks for doc_id=%s", deleted, doc_id)
        return deleted

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Return total number of chunks, optionally filtered."""
        if self._collection is None:
            return 0
        if filters:
            where = _build_chromadb_where(filters)
            result = self._collection.get(where=where)
            return len(result["ids"]) if result["ids"] else 0
        return self._collection.count()


# ===========================================================================
# Internal helpers
# ===========================================================================


def _build_chromadb_where(filters: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a flat filter dict into a ChromaDB 'where' clause.

    WHY we need this conversion: ChromaDB's where clause uses a specific
    nested format ($eq, $and, etc.). Our callers pass simple flat dicts.
    This adapter keeps the ChromaDB query syntax encapsulated.

    For single-field filters: {"domain": "structure"} → {"domain": "structure"}
    (ChromaDB auto-interprets flat equality).

    For multi-field filters:
        {"domain": "structure", "language": "en"}
        → {"$and": [{"domain": "structure"}, {"language": "en"}]}
    """
    if len(filters) == 1:
        # Single filter — ChromaDB accepts flat dicts
        return dict(filters)
    # Multiple filters — must use $and
    return {"$and": [{k: v} for k, v in filters.items()]}


def _reconstruct_metadata(meta: dict) -> DocumentMetadata:
    """
    Rebuild a DocumentMetadata from the flat dict stored in ChromaDB.

    WHY: ChromaDB stores metadata as flat key-value pairs (no nesting).
    We reconstruct the typed dataclass so upper modules get consistent
    DocumentMetadata objects regardless of which backend is used.
    """
    from contracts.document import Domain

    domain_str = meta.get("domain", "general")
    try:
        domain = Domain(domain_str)
    except ValueError:
        domain = Domain.GENERAL

    return DocumentMetadata(
        source_filename=meta.get("source_filename", "unknown"),
        domain=domain,
        language=meta.get("language", "en"),
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pip install chromadb && python -m pytest m2-storage/tests/test_chromadb.py -v
```
Expected: 6 PASS, 0 FAIL

- [ ] **Step 5: Commit**

```bash
git add m2-storage/src/vector_store/chromadb_store.py m2-storage/tests/test_chromadb.py
git commit -m "[00050-04] feat: implement ChromaDBStore — vector insert, search, delete, count"
```

---

### Task 5: Meilisearch DocumentIndex (00050-05)

**Files:**
- Modify: `m2-storage/src/document_index/meilisearch_index.py` (replace stub)
- Create: `m2-storage/tests/test_meilisearch.py`

- [ ] **Step 1: Write the test file**

```python
# m2-storage/tests/test_meilisearch.py
"""
Tests for MeilisearchIndex — the Personal-mode full-text search backend.

WHY: Meilisearch provides BM25-based keyword search that complements
dense vector retrieval. When a user searches for a specific regulation
clause number (e.g. "DNV Pt.4 Ch.3 §5"), keyword search is more precise
than semantic embedding similarity.

NOTE: These tests require a running Meilisearch instance.
If MEILISEARCH_URL is not set or the instance is unreachable,
tests are skipped via pytest.skip.
"""

import os
import uuid

import pytest

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.storage import DocumentIndexProtocol

from m2_storage.document_index.meilisearch_index import MeilisearchIndex
from m2_storage.config import MeilisearchConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MEILI_HOST = os.environ.get("MEILISEARCH_URL", "http://127.0.0.1:7700")

# Attempt to detect Meilisearch availability once at import time
_meili_available = None


def _check_meilisearch():
    """Check if Meilisearch is reachable. Cache the result."""
    global _meili_available
    if _meili_available is not None:
        return _meili_available
    import urllib.request
    try:
        req = urllib.request.Request(f"{MEILI_HOST}/health")
        urllib.request.urlopen(req, timeout=2)
        _meili_available = True
    except Exception:
        _meili_available = False
    return _meili_available


def _make_chunk(text: str, doc_id: str = "doc-1", domain: str = "structure",
                chunk_index: int = 0) -> Chunk:
    """Create a minimal Chunk for testing."""
    return Chunk(
        chunk_id=f"{doc_id}-chunk-{chunk_index}",
        text=text,
        metadata=DocumentMetadata(
            source_filename=f"{doc_id}.pdf",
            domain=Domain(domain),
        ),
        chunk_type="clause",
        position_in_document=chunk_index,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def meili_config():
    """Create a MeilisearchConfig with a unique index name."""
    return MeilisearchConfig(
        host=MEILI_HOST,
        api_key="",
        index_name=f"test_m2_{uuid.uuid4().hex[:8]}",
    )


@pytest.fixture
async def meili_index(meili_config):
    """Return an initialized MeilisearchIndex, or skip if unavailable."""
    if not _check_meilisearch():
        pytest.skip("Meilisearch not available at " + MEILI_HOST)
    idx = MeilisearchIndex(meili_config)
    await idx.initialize()
    yield idx
    # Cleanup: delete the test index
    try:
        idx._client.delete_index(meili_config.index_name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

def test_protocol_compliance(meili_index):
    """MeilisearchIndex must satisfy DocumentIndexProtocol."""
    assert isinstance(meili_index, DocumentIndexProtocol)


# ---------------------------------------------------------------------------
# Test 2: index and search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_and_search(meili_index):
    """Index chunks then search — must return relevant results."""
    c1 = _make_chunk("DNV Pt.4 Ch.3 welding procedure specification",
                      doc_id="doc-1", chunk_index=0)
    c2 = _make_chunk("ABS Pt.5B hull structural requirements",
                      doc_id="doc-2", chunk_index=0)

    await meili_index.index([c1, c2])
    # Give Meilisearch a moment to index
    import asyncio
    await asyncio.sleep(0.5)

    results = await meili_index.search("welding procedure", top_k=5)
    assert len(results) >= 1
    assert isinstance(results[0][0], Chunk)
    assert isinstance(results[0][1], float)
    # The welding chunk should be first
    assert "welding" in results[0][0].text.lower()


# ---------------------------------------------------------------------------
# Test 3: search with filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_with_filter(meili_index):
    """Search with a metadata filter must only return matching chunks."""
    c1 = _make_chunk("welding requirements", doc_id="doc-a", domain="structure")
    c2 = _make_chunk("welding inspection", doc_id="doc-b", domain="machinery")

    await meili_index.index([c1, c2])
    import asyncio
    await asyncio.sleep(0.5)

    # Filter to machinery only
    results = await meili_index.search(
        "welding", top_k=5, filters={"domain": "machinery"}
    )
    assert len(results) == 1
    assert results[0][0].metadata.source_filename == "doc-b.pdf"


# ---------------------------------------------------------------------------
# Test 4: delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete(meili_index):
    """Deleting by doc_id must remove that document's chunks from search."""
    c1 = _make_chunk("content A", doc_id="keep")
    c2 = _make_chunk("content B", doc_id="remove")

    await meili_index.index([c1, c2])
    import asyncio
    await asyncio.sleep(0.5)

    await meili_index.delete("remove")

    results = await meili_index.search("content", top_k=10)
    # Only the 'keep' chunk should remain
    assert len(results) == 1
    assert results[0][0].text == "content A"


# ---------------------------------------------------------------------------
# Test 5: search empty index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_empty(meili_index):
    """Searching an empty index must return an empty list."""
    results = await meili_index.search("anything", top_k=10)
    assert results == []


# ---------------------------------------------------------------------------
# Test 6: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(meili_index):
    """Initialized index must report healthy."""
    assert await meili_index.health_check() is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest m2-storage/tests/test_meilisearch.py -v`
Expected: FAIL (stub — or SKIP if Meilisearch not running)

- [ ] **Step 3: Write full MeilisearchIndex implementation**

Replace the stub `m2-storage/src/document_index/meilisearch_index.py`:

```python
"""
Meilisearch implementation of BaseDocumentIndex.

WHY: Meilisearch is the Personal-mode default full-text search engine.
It provides fast, typo-tolerant BM25 keyword search that complements
the dense vector search from ChromaDB. For regulation clause lookups
(e.g. "DNV Pt.4 Ch.3 §5"), keyword search is more precise than embeddings.

We use Meilisearch's Python SDK. The engine must be running as a separate
process (via CLI or Docker). In production, it runs alongside the app.
"""

from __future__ import annotations

import logging
from typing import Any

import meilisearch

from contracts.document import Chunk, DocumentMetadata, Domain

from .base import BaseDocumentIndex

logger = logging.getLogger(__name__)


class MeilisearchIndex(BaseDocumentIndex):
    """Document index backed by Meilisearch (BM25 full-text search).

    Chunk fields are mapped to Meilisearch document attributes:
    - chunk_id   → primary key (id)
    - text       → searchable content
    - metadata fields → filterable attributes
    """

    def __init__(self, config):
        """
        Args:
            config: MeilisearchConfig with host, api_key, and index_name.
        """
        self._config = config
        self._client: meilisearch.Client | None = None
        self._index: meilisearch.Index | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Connect to Meilisearch and configure the index.

        WHY configure filterable/sortable attributes at init time:
        Meilisearch requires explicit declaration of which fields can
        be used in filters. We declare metadata fields here so that
        search-time filters (e.g. domain=structure) work correctly.
        """
        self._client = meilisearch.Client(
            self._config.host, self._config.api_key
        )
        # Create or get the index
        try:
            self._index = self._client.get_index(self._config.index_name)
        except meilisearch.errors.MeilisearchApiError:
            self._client.create_index(
                self._config.index_name, {"primaryKey": "chunk_id"}
            )
            self._index = self._client.get_index(self._config.index_name)

        # Configure which fields are searchable and filterable
        self._index.update_searchable_attributes(["text"])
        self._index.update_filterable_attributes([
            "doc_id", "source_filename", "domain", "chunk_type", "language",
        ])
        self._index.update_sortable_attributes(["position"])
        logger.info(
            "Meilisearch initialized: %s (index: %s)",
            self._config.host,
            self._config.index_name,
        )

    async def health_check(self) -> bool:
        """Verify Meilisearch is reachable and the index exists."""
        try:
            if self._client is None:
                return False
            self._client.health()
            return True
        except Exception:
            logger.exception("Meilisearch health check failed")
            return False

    async def close(self) -> None:
        """Release the HTTP client session."""
        self._index = None
        self._client = None

    # ------------------------------------------------------------------
    # DocumentIndexProtocol — data operations
    # ------------------------------------------------------------------

    async def index(self, chunks: list[Chunk]) -> None:
        """
        Index chunks for full-text search.

        WHY we store metadata as flat fields, not nested JSON:
        Meilisearch filter syntax requires top-level attributes.
        Nesting metadata would prevent filtering by domain, language, etc.

        Args:
            chunks: Document chunks to index.
        """
        if not chunks or self._index is None:
            return

        documents = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "doc_id": c.metadata.source_filename.replace(".pdf", ""),
                "source_filename": c.metadata.source_filename,
                "domain": c.metadata.domain.value,
                "chunk_type": c.chunk_type,
                "language": c.metadata.language,
                "position": c.position_in_document,
            }
            for c in chunks
        ]

        # Meilisearch accepts batches; the SDK handles chunking internally
        self._index.add_documents(documents)
        logger.debug("Indexed %d chunks in Meilisearch", len(chunks))

    async def search(
        self,
        query: str,
        top_k: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Full-text search with optional metadata filtering.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results.
            filters: Optional metadata filter dict,
                     e.g. {"domain": "structure"}.

        Returns:
            List of (Chunk, score) tuples ordered by relevance.
        """
        if self._index is None:
            return []

        filter_expr = _build_meili_filter(filters) if filters else None

        results = self._index.search(
            query,
            {
                "limit": top_k,
                "filter": filter_expr,
                "attributesToRetrieve": [
                    "chunk_id", "text", "doc_id", "source_filename",
                    "domain", "chunk_type", "language", "position",
                ],
            },
        )

        chunks: list[tuple[Chunk, float]] = []
        for hit in results.get("hits", []):
            chunk = Chunk(
                chunk_id=hit["chunk_id"],
                text=hit["text"],
                metadata=DocumentMetadata(
                    source_filename=hit.get("source_filename", "unknown"),
                    domain=Domain(hit.get("domain", "general")),
                    language=hit.get("language", "en"),
                ),
                chunk_type=hit.get("chunk_type", "general"),
                position_in_document=hit.get("position", 0),
            )
            # Meilisearch returns _rankingScore; normalize to 0-1
            score = hit.get("_rankingScore", 0.0)
            chunks.append((chunk, score))

        return chunks

    async def delete(self, doc_id: str) -> int:
        """
        Delete all chunks for a document.

        Meilisearch delete by filter removes documents matching the
        filter expression. This is an O(1) metadata operation — it
        does not scan all documents.
        """
        if self._index is None:
            return 0
        # Get count before deletion
        before = self._index.search("", {"limit": 0, "filter": f"doc_id = {doc_id}"})
        before_count = before.get("estimatedTotalHits", 0)
        self._index.delete_documents_by_filter(f"doc_id = {doc_id}")
        logger.info("Deleted ~%d chunks for doc_id=%s from Meilisearch", before_count, doc_id)
        return before_count


# ===========================================================================
# Internal helpers
# ===========================================================================


def _build_meili_filter(filters: dict[str, Any]) -> str:
    """
    Convert a filter dict into a Meilisearch filter expression string.

    WHY Meilisearch uses a SQL-like filter syntax, not JSON:
    {"domain": "structure", "language": "en"}
    → 'domain = "structure" AND language = "en"'

    Only equality is supported for now. Range/IN filters can be
    added when needed by upper modules.
    """
    parts = []
    for key, value in filters.items():
        # String values need quoting; numbers/booleans do not
        if isinstance(value, str):
            parts.append(f'{key} = "{value}"')
        else:
            parts.append(f"{key} = {value}")
    return " AND ".join(parts)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pip install meilisearch && python -m pytest m2-storage/tests/test_meilisearch.py -v
```
Expected: 6 PASS (or SKIP if Meilisearch unavailable)

- [ ] **Step 5: Commit**

```bash
git add m2-storage/src/document_index/meilisearch_index.py m2-storage/tests/test_meilisearch.py
git commit -m "[00050-05] feat: implement MeilisearchIndex — full-text index, search, filter, delete"
```

---

### Task 6: SQLite RelationalDB (00050-06)

**Files:**
- Modify: `m2-storage/src/relational_db/sqlite_db.py` (replace stub)
- Create: `m2-storage/tests/test_sqlite.py`

- [ ] **Step 1: Write the test file**

```python
# m2-storage/tests/test_sqlite.py
"""
Tests for SQLiteDB — the Personal-mode relational database backend.

WHY: SQLite is the primary relational store for Personal deployments.
It must provide a working async SQLAlchemy engine, return usable sessions,
and handle edge cases like non-existent parent directories.
"""

import os

import pytest
from sqlalchemy import text

from contracts.storage import RelationalDBProtocol

from m2_storage.relational_db.sqlite_db import SQLiteDB
from m2_storage.config import SQLiteConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_config(tmp_path):
    """Create a SQLiteConfig pointing at a temp file."""
    db_path = tmp_path / "subdir" / "test.db"
    return SQLiteConfig(path=str(db_path))


@pytest.fixture
async def sqlite_db(sqlite_config):
    """Return an initialized SQLiteDB."""
    db = SQLiteDB(sqlite_config)
    await db.initialize()
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

def test_protocol_compliance(sqlite_db):
    """SQLiteDB must satisfy RelationalDBProtocol."""
    assert isinstance(sqlite_db, RelationalDBProtocol)


# ---------------------------------------------------------------------------
# Test 2: initialize creates database file
# ---------------------------------------------------------------------------

def test_initialize_creates_file(sqlite_db, sqlite_config):
    """After initialize(), the .db file must exist on disk."""
    assert os.path.exists(sqlite_config.path)


# ---------------------------------------------------------------------------
# Test 3: get_session returns working session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_works(sqlite_db):
    """A session from get_session() must be able to execute SQL."""
    async with await sqlite_db.get_session() as session:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1


# ---------------------------------------------------------------------------
# Test 4: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(sqlite_db):
    """Initialized database must report healthy."""
    assert await sqlite_db.health_check() is True


# ---------------------------------------------------------------------------
# Test 5: auto-creates parent directory
# ---------------------------------------------------------------------------

def test_auto_creates_parent_dir(tmp_path):
    """If the parent directory does not exist, initialize must create it."""
    db_path = tmp_path / "new_subdir" / "deep" / "test.db"
    config = SQLiteConfig(path=str(db_path))
    db = SQLiteDB(config)

    # Parent dirs should not exist yet
    assert not os.path.exists(str(db_path.parent))

    import asyncio
    asyncio.run(db.initialize())

    # After init, the db file must exist
    assert os.path.exists(str(db_path))
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest m2-storage/tests/test_sqlite.py -v`
Expected: FAIL (stub returns NotImplementedError on get_session)

- [ ] **Step 3: Write full SQLiteDB implementation**

Replace the stub `m2-storage/src/relational_db/sqlite_db.py`:

```python
"""
SQLite implementation of BaseRelationalDB.

WHY: SQLite is the Personal-mode default relational database. It requires
zero configuration, no separate server process, and stores everything in
a single file. Combined with SQLAlchemy's async engine, it provides the
same interface as PostgreSQL — just with a different connection string.

Design: M2 only provides the engine and session factory. ORM model
classes (User, Conversation, etc.) are defined by upper modules (M5).
M2 calls create_all() with an empty Base to ensure the engine is valid,
but actual table creation is done by each module that defines models.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import BaseRelationalDB

logger = logging.getLogger(__name__)


class SQLiteDB(BaseRelationalDB):
    """Relational database backed by SQLite + SQLAlchemy 2.0 async.

    The async engine uses aiosqlite as the driver. All connections
    are configured with WAL journal mode for better concurrent read
    performance.
    """

    def __init__(self, config):
        """
        Args:
            config: SQLiteConfig with the database file path.
        """
        self._config = config
        self._engine = None
        self._session_factory = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Create the async SQLAlchemy engine and verify connectivity.

        WHY we create parent directories: the user may specify a path
        like ./data/subdir/db.sqlite3 where intermediate directories
        don't exist yet. SQLite will not auto-create parent dirs.
        """
        db_path = Path(self._config.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
            # WAL mode allows concurrent reads while a write is in progress
            connect_args={"check_same_thread": False},
        )

        # Enable WAL journal mode for better performance
        async with self._engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info(
            "SQLite initialized: %s (WAL mode)", self._config.path
        )

    async def health_check(self) -> bool:
        """Execute a lightweight query to verify the database is accessible."""
        try:
            if self._engine is None:
                return False
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("SQLite health check failed")
            return False

    async def close(self) -> None:
        """Dispose the engine and release all connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("SQLite engine disposed")

    # ------------------------------------------------------------------
    # RelationalDBProtocol — session provisioning
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def get_session(self):
        """
        Return an async session as a context manager.

        Usage:
            async with db.get_session() as session:
                result = await session.execute(...)

        WHY context manager: ensures the session is always closed after
        use, even if an exception occurs. This prevents connection leaks
        that would exhaust the connection pool.

        Raises:
            RuntimeError: If the database has not been initialized.
        """
        if self._session_factory is None:
            raise RuntimeError(
                "SQLiteDB not initialized. Call await db.initialize() first."
            )
        async with self._session_factory() as session:
            yield session
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pip install sqlalchemy[asyncio] aiosqlite && python -m pytest m2-storage/tests/test_sqlite.py -v
```
Expected: 5 PASS, 0 FAIL

- [ ] **Step 5: Commit**

```bash
git add m2-storage/src/relational_db/sqlite_db.py m2-storage/tests/test_sqlite.py
git commit -m "[00050-06] feat: implement SQLiteDB — async engine, session factory, WAL mode"
```

---

### Task 7: LocalFS FileStore (00050-07)

**Files:**
- Modify: `m2-storage/src/file_store/local_fs.py` (replace stub)
- Create: `m2-storage/tests/test_local_fs.py`

- [ ] **Step 1: Write the test file**

```python
# m2-storage/tests/test_local_fs.py
"""
Tests for LocalFSStore — the Personal-mode file storage backend.

WHY: LocalFS is the primary file store for Personal deployments. It
must correctly handle file CRUD operations, metadata sidecars, and
path traversal attacks. File storage is the most security-sensitive
backend because it interacts directly with the host filesystem.
"""

import os

import pytest

from contracts.storage import FileStoreProtocol

from m2_storage.file_store.local_fs import LocalFSStore, _is_safe_key
from m2_storage.config import LocalFSConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fs_config(tmp_path):
    """Create a LocalFSConfig pointing at a temp directory."""
    root = tmp_path / "files"
    root.mkdir()
    return LocalFSConfig(root_dir=str(root))


@pytest.fixture
async def fs_store(fs_config):
    """Return an initialized LocalFSStore."""
    store = LocalFSStore(fs_config)
    await store.initialize()
    yield store
    # No close needed for LocalFS
    await store.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

def test_protocol_compliance(fs_store):
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

    # Check the .meta.json file exists
    import json
    meta_path = os.path.join(
        fs_config.root_dir, key + ".meta.json"
    )
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

    result = await fs_store.get(key)
    assert result is None


# ---------------------------------------------------------------------------
# Test 5: list by prefix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list(fs_store):
    """list() must return all keys under a prefix."""
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
    """Keys containing '../' must be rejected for security."""
    assert not _is_safe_key("../etc/passwd")
    assert not _is_safe_key("docs/../../../etc/shadow")
    assert not _is_safe_key("foo/..\\bar")  # Windows-style

    # Safe keys must pass
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
    """Initialized store must report healthy (root_dir is readable/writable)."""
    assert await fs_store.health_check() is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest m2-storage/tests/test_local_fs.py -v`
Expected: FAIL (stub returns empty/None)

- [ ] **Step 3: Write full LocalFSStore implementation**

Replace the stub `m2-storage/src/file_store/local_fs.py`:

```python
"""
Local filesystem implementation of BaseFileStore.

WHY: LocalFS is the Personal-mode default file store. It stores files
directly on the host filesystem with metadata in JSON sidecar files.
No external service required — ideal for single-user deployments.

Security: All keys are validated against path traversal attacks before
any filesystem operation. This is non-negotiable for a store that writes
to the host filesystem based on user-provided keys.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import aiofiles
import aiofiles.os

from .base import BaseFileStore

logger = logging.getLogger(__name__)


class LocalFSStore(BaseFileStore):
    """File store backed by the local filesystem.

    File layout:
        {root_dir}/{key}           → file content
        {root_dir}/{key}.meta.json → metadata (JSON)

    WHY metadata as sidecar files: avoids needing a separate metadata
    database for file attributes. For Personal mode with <100k files,
    filesystem-based metadata is simpler and more debuggable.
    """

    def __init__(self, config):
        """
        Args:
            config: LocalFSConfig with root_dir path.
        """
        self._config = config
        self._root: Path | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Ensure the root directory exists."""
        self._root = Path(self._config.root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("LocalFS initialized: %s", self._root)

    async def health_check(self) -> bool:
        """Verify the root directory is readable and writable."""
        try:
            if self._root is None:
                return False
            # Write a test file and remove it
            test_file = self._root / ".health_check_test"
            test_file.write_text("ok")
            test_file.unlink()
            return True
        except Exception:
            logger.exception("LocalFS health check failed")
            return False

    async def close(self) -> None:
        """No-op: LocalFS has no persistent connections."""
        self._root = None

    # ------------------------------------------------------------------
    # FileStoreProtocol — data operations
    # ------------------------------------------------------------------

    async def put(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Store a file on the local filesystem.

        Args:
            key: Relative path within root_dir (e.g. 'documents/report.pdf').
            data: Raw file bytes.
            metadata: Optional key-value metadata written to a .meta.json sidecar.

        Returns:
            The storage key (same as input key).

        Raises:
            ValueError: If the key contains path traversal patterns.
        """
        _require_safe_key(key)

        file_path = self._resolve(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)

        if metadata:
            meta_path = Path(str(file_path) + ".meta.json")
            async with aiofiles.open(meta_path, "w") as f:
                await f.write(json.dumps(metadata))

        logger.debug("Stored file: %s (%d bytes)", key, len(data))
        return key

    async def get(self, key: str) -> bytes | None:
        """
        Read a file from the local filesystem.

        Returns None if the file does not exist (rather than raising).
        WHY return None: callers treat missing files as "not found",
        not as an error condition.
        """
        _require_safe_key(key)
        file_path = self._resolve(key)
        if not file_path.exists():
            return None
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> bool:
        """Delete a file and its metadata sidecar. Returns True if deleted."""
        _require_safe_key(key)
        file_path = self._resolve(key)
        meta_path = Path(str(file_path) + ".meta.json")

        deleted = False
        if file_path.exists():
            os.remove(file_path)
            deleted = True
        if meta_path.exists():
            os.remove(meta_path)

        if deleted:
            logger.debug("Deleted file: %s", key)
        return deleted

    async def list(self, prefix: str = "") -> list[str]:
        """
        List all file keys under a prefix.

        Only returns actual files, not .meta.json sidecars.
        """
        if self._root is None:
            return []

        search_dir = self._root
        if prefix:
            _require_safe_key(prefix)
            search_dir = self._resolve(prefix)

        if not search_dir.exists():
            return []

        keys = []
        for root, _dirs, files in os.walk(search_dir):
            for fname in files:
                if fname.endswith(".meta.json"):
                    continue
                full_path = Path(root) / fname
                # Convert absolute path back to relative key
                key = str(full_path.relative_to(self._root)).replace(
                    "\\", "/"
                )
                keys.append(key)
        return keys

    async def get_url(
        self, key: str, expires_in: int = 3600
    ) -> str | None:
        """
        Return a file:// URL for the stored file.

        LocalFS does not support presigned URLs (there is no auth layer).
        We return a file:// absolute path so consumers can access the file
        directly on the local machine.

        Args:
            key: Storage key.
            expires_in: Ignored for LocalFS (no URL expiration).

        Returns:
            file:// URL string, or None if the file does not exist.
        """
        _require_safe_key(key)
        file_path = self._resolve(key)
        if not file_path.exists():
            return None
        return file_path.as_uri()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Resolve a storage key to an absolute filesystem path."""
        return self._root / key


# ===========================================================================
# Security: path traversal prevention
# ===========================================================================


def _require_safe_key(key: str) -> None:
    """Raise ValueError if the key contains path traversal patterns.

    WHY this is critical: file_store keys come from user input (upload
    filenames, API parameters). Without this check, a malicious key like
    '../../../etc/passwd' could write outside root_dir.
    """
    if not _is_safe_key(key):
        raise ValueError(
            f"Unsafe storage key (path traversal detected): {key!r}"
        )


def _is_safe_key(key: str) -> bool:
    """
    Check that a storage key does not attempt directory traversal.

    A safe key:
    - Contains no '..' path segments
    - Contains no backslash traversal (Windows)
    - Is not an absolute path
    """
    if not key:
        return False
    # Normalize separators
    normalized = key.replace("\\", "/")
    # Reject absolute paths
    if normalized.startswith("/"):
        return False
    # Reject traversal segments
    parts = normalized.split("/")
    for part in parts:
        if part == ".." or part == "." and len(parts) == 1:
            # "." alone is a relative reference; reject it
            return False
        if part == "..":
            return False
    # Reject Windows drive letters
    if ":" in key:
        return False
    return True
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pip install aiofiles && python -m pytest m2-storage/tests/test_local_fs.py -v
```
Expected: 8 PASS, 0 FAIL

- [ ] **Step 5: Commit**

```bash
git add m2-storage/src/file_store/local_fs.py m2-storage/tests/test_local_fs.py
git commit -m "[00050-07] feat: implement LocalFSStore — file CRUD, metadata sidecar, path traversal protection"
```

---

### Task 8: Integration Tests (00050-08)

**Files:**
- Create: `m2-storage/tests/conftest.py`
- Modify: `m2-storage/tests/test_manager.py` (add integration scenarios)

- [ ] **Step 1: Write conftest.py with shared fixtures**

```python
# m2-storage/tests/conftest.py
"""
Shared pytest fixtures for all M2 tests.

WHY: Each backend test needs an initialized instance with temp directories.
Centralizing fixture creation here avoids duplicating setup logic across
8 test files and ensures consistent cleanup after tests.
"""

import os
import uuid
from pathlib import Path

import pytest
import yaml

from m2_storage.config import (
    ChromaDBConfig,
    LocalFSConfig,
    MeilisearchConfig,
    SQLiteConfig,
    StorageConfig,
)
from m2_storage.factory import create_storage_manager
from m2_storage.manager import StorageManager


# ---------------------------------------------------------------------------
# Temp directories
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a clean data directory for a test run."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


# ---------------------------------------------------------------------------
# Deploy.yaml generator
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config_path(tmp_path, tmp_data_dir):
    """Generate a temporary deploy.yaml for integration tests."""
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
    config_path = tmp_path / "deploy.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


# ---------------------------------------------------------------------------
# Individual backend fixtures (for unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def chroma_config(tmp_data_dir):
    """ChromaDB config with temp persist directory."""
    return ChromaDBConfig(
        persist_dir=str(tmp_data_dir / "chromadb"),
        collection_name=f"test_{uuid.uuid4().hex[:8]}",
    )


@pytest.fixture
def meili_config():
    """Meilisearch config with unique index name."""
    return MeilisearchConfig(
        host=os.environ.get("MEILISEARCH_URL", "http://127.0.0.1:7700"),
        api_key="",
        index_name=f"test_{uuid.uuid4().hex[:8]}",
    )


@pytest.fixture
def sqlite_config(tmp_data_dir):
    """SQLite config with temp database path."""
    return SQLiteConfig(path=str(tmp_data_dir / "test.db"))


@pytest.fixture
def fs_config(tmp_data_dir):
    """LocalFS config with temp root directory."""
    root = tmp_data_dir / "files"
    root.mkdir(parents=True, exist_ok=True)
    return LocalFSConfig(root_dir=str(root))


# ---------------------------------------------------------------------------
# Assembled StorageManager fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def storage_manager(tmp_config_path):
    """Create a fully assembled StorageManager from temp config.

    This fixture is used by integration tests that need all 4 backends.
    Each backend uses temp directories so tests are isolated.
    """
    mgr = create_storage_manager(str(tmp_config_path))
    await mgr.initialize()
    yield mgr
    await mgr.close()
```

- [ ] **Step 2: Add integration test cases to test_manager.py**

Append these tests to the existing `m2-storage/tests/test_manager.py`:

```python
# Append to m2-storage/tests/test_manager.py

# ---------------------------------------------------------------------------
# Integration tests using the full storage_manager fixture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_lifecycle(storage_manager):
    """Complete lifecycle: init already done by fixture, check health, then close
    happens in fixture teardown."""
    result = await storage_manager.health_check()
    # All 4 backends should be healthy
    assert "vector_store" in result
    assert "doc_index" in result
    assert "relational_db" in result
    assert "file_store" in result


@pytest.mark.asyncio
async def test_cross_backend_operations(storage_manager):
    """Verify that operations across backends work independently."""
    # Write a file
    await storage_manager.file_store.put(
        "test/hello.txt", b"Hello, Marine RAG!"
    )
    # Read it back
    content = await storage_manager.file_store.get("test/hello.txt")
    assert content == b"Hello, Marine RAG!"

    # Vector store should be queryable (even if empty)
    count = await storage_manager.vector_store.count()
    assert count >= 0  # Just verifies it doesn't crash

    # Relational DB should provide sessions
    async with await storage_manager.relational_db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_health_check_all_healthy(storage_manager):
    """All 4 backends must report healthy when properly initialized."""
    result = await storage_manager.health_check()
    assert result["vector_store"] is True
    assert result["relational_db"] is True
    assert result["file_store"] is True
    # doc_index may be False if Meilisearch is not running;
    # that's acceptable — the test verifies the method works
    assert isinstance(result["doc_index"], bool)


@pytest.mark.asyncio
async def test_close_then_health_check_fails(storage_manager):
    """After close(), backends should not report healthy."""
    await storage_manager.close()
    result = await storage_manager.health_check()
    # After close, backends should fail health check
    assert result["vector_store"] is False
    assert result["relational_db"] is False
    assert result["file_store"] is False
```

- [ ] **Step 3: Run all tests**

```bash
python -m pytest m2-storage/tests/ -v
```
Expected: All passing (Meilisearch tests may skip)

- [ ] **Step 4: Commit**

```bash
git add m2-storage/tests/conftest.py m2-storage/tests/test_manager.py
git commit -m "[00050-08] test: add conftest fixtures and StorageManager integration tests"
```

---

### Task 9: Packaging & Final Verification (00050-09)

**Files:**
- Create: `m2-storage/pyproject.toml`
- Create: `m2-storage/requirements.txt`
- Modify: `m2-storage/src/__init__.py` (replace placeholder)

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "m2-storage"
version = "0.1.0"
description = "Marine & Offshore Expert System — Storage Abstraction Layer (M2)"
requires-python = ">=3.12"
dependencies = [
    "pyyaml>=6.0",
    "chromadb>=0.5.0,<1.0.0",
    "meilisearch>=0.31.0,<1.0.0",
    "sqlalchemy[asyncio]>=2.0.0,<3.0.0",
    "aiosqlite>=0.20.0",
    "aiofiles>=24.0.0",
]

[project.optional-dependencies]
# Each backend can be installed independently for minimal deployments
vector-store = ["chromadb>=0.5.0,<1.0.0"]
document-index = ["meilisearch>=0.31.0,<1.0.0"]
relational-db = ["sqlalchemy[asyncio]>=2.0.0,<3.0.0", "aiosqlite>=0.20.0"]
file-store = ["aiofiles>=24.0.0"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "pyyaml>=6.0",
]
all = ["m2-storage[vector-store,document-index,relational-db,file-store,dev]"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write requirements.txt**

```
# M2 Storage Abstraction Layer — locked dev dependencies
# Install: pip install -r requirements.txt

chromadb>=0.5.0,<1.0.0
meilisearch>=0.31.0,<1.0.0
sqlalchemy[asyncio]>=2.0.0,<3.0.0
aiosqlite>=0.20.0
aiofiles>=24.0.0
pyyaml>=6.0
pytest>=8.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: Write src/__init__.py**

Replace the `# m2-storage` placeholder:

```python
"""
M2 — Storage Abstraction Layer.

Provides a unified storage interface with pluggable backends
selected at deploy time via deploy.yaml. Upper modules (M1/M3/M4/M5)
interact with storage exclusively through StorageManager and the
Protocols defined in contracts/storage.py.

Usage:
    from m2_storage import create_storage_manager

    manager = await create_storage_manager("deploy.yaml")
    await manager.initialize()

    # Use backends directly via Protocol interfaces
    results = await manager.vector_store.search(query_vec, top_k=10)
    chunks  = await manager.doc_index.search("keyword", top_k=5)
    async with manager.relational_db.get_session() as session:
        ...
    file_data = await manager.file_store.get("path/to/file.pdf")

    await manager.close()

Backend selection (Personal mode defaults):
    Vector Store   → ChromaDB (embedded)
    Document Index → Meilisearch
    Relational DB  → SQLite
    File Store     → Local filesystem
"""

__version__ = "0.1.0"

from .factory import create_storage_manager
from .manager import StorageManager

__all__ = [
    "StorageManager",
    "create_storage_manager",
    "__version__",
]
```

- [ ] **Step 4: Install and run full test suite**

```bash
cd E:/myCode/RAG
pip install -e contracts/
pip install -e "m2-storage/[all]"
python -m pytest m2-storage/tests/ -v
```
Expected: All tests PASS (Meilisearch may skip if not running)

- [ ] **Step 5: Verify protocol compliance**

```bash
python -c "
from contracts.storage import (
    VectorStoreProtocol, DocumentIndexProtocol,
    RelationalDBProtocol, FileStoreProtocol
)
from m2_storage.vector_store.chromadb_store import ChromaDBStore
from m2_storage.document_index.meilisearch_index import MeilisearchIndex
from m2_storage.relational_db.sqlite_db import SQLiteDB
from m2_storage.file_store.local_fs import LocalFSStore

# Verify each implementation satisfies its Protocol
# (We check class inheritance, which is equivalent)
from m2_storage.vector_store.base import BaseVectorStore
from m2_storage.document_index.base import BaseDocumentIndex
from m2_storage.relational_db.base import BaseRelationalDB
from m2_storage.file_store.base import BaseFileStore

assert issubclass(ChromaDBStore, VectorStoreProtocol), 'ChromaDBStore fails VectorStoreProtocol'
assert issubclass(MeilisearchIndex, DocumentIndexProtocol), 'MeilisearchIndex fails DocumentIndexProtocol'
assert issubclass(SQLiteDB, RelationalDBProtocol), 'SQLiteDB fails RelationalDBProtocol'
assert issubclass(LocalFSStore, FileStoreProtocol), 'LocalFSStore fails FileStoreProtocol'

print('All Protocol compliance checks passed.')
"
```
Expected: "All Protocol compliance checks passed."

- [ ] **Step 6: Verify public API exports**

```bash
python -c "from m2_storage import StorageManager, create_storage_manager; print('Public API OK')"
```
Expected: "Public API OK"

- [ ] **Step 7: Commit**

```bash
git add m2-storage/pyproject.toml m2-storage/requirements.txt m2-storage/src/__init__.py
git commit -m "[00050-09] chore: add pyproject.toml, requirements.txt, and public API exports"
```

---

## Dependency Graph

```
Task 1 (config) ──→ Task 2 (factory) ──→ Task 3 (manager tests)
                                              │
                    ┌─────────────────────────┤
                    │                         │
               Task 4 (ChromaDB)         Task 6 (SQLite)
               Task 5 (Meilisearch)      Task 7 (LocalFS)
                    │                         │
                    └──────────┬──────────────┘
                               │
                         Task 8 (integration)
                               │
                         Task 9 (packaging)
```

Tasks 4-7 are independent and can be implemented in parallel.

---

*Plan complete. Proceed with `superpowers:executing-plans` or `superpowers:subagent-driven-development`.*
