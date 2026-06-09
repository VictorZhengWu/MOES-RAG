# -*- coding: utf-8 -*-
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
    PostgreSQLConfig,
    RelationalDBConfig,
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
            "vector_store": {"backend": "pinecone"},
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

    with pytest.raises(ValueError, match="pinecone"):
        load_config(path)


# ---------------------------------------------------------------------------
# Test 4: Missing file raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_missing_file_raises():
    """Passing a non-existent path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("./nonexistent_config.yaml")


# ---------------------------------------------------------------------------
# Test 5: PostgreSQLConfig defaults
# ---------------------------------------------------------------------------

def test_postgresql_config_defaults():
    """PostgreSQLConfig must have sensible defaults for local dev."""
    cfg = PostgreSQLConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 5432
    assert cfg.database == "marine_rag"
    assert cfg.user == "postgres"
    assert cfg.password == ""
    assert cfg.pool_size == 10
    assert cfg.max_overflow == 20
    assert cfg.ssl_mode == "prefer"  # default: prefer SSL, allow plain


def test_postgresql_config_custom_values():
    """All PostgreSQLConfig fields must accept custom values."""
    cfg = PostgreSQLConfig(
        host="pg.internal",
        port=5433,
        database="testdb",
        user="app_user",
        password="secret",
        pool_size=5,
        max_overflow=10,
        ssl_mode="require",
    )
    assert cfg.host == "pg.internal"
    assert cfg.port == 5433
    assert cfg.database == "testdb"
    assert cfg.user == "app_user"
    assert cfg.password == "secret"
    assert cfg.pool_size == 5
    assert cfg.max_overflow == 10
    assert cfg.ssl_mode == "require"


def test_postgresql_config_from_dict_minimal():
    """from_dict() with empty dict must return defaults."""
    cfg = PostgreSQLConfig.from_dict({})
    assert cfg.host == "localhost"
    assert cfg.port == 5432


def test_postgresql_config_from_dict_full():
    """from_dict() with all values must populate all fields."""
    cfg = PostgreSQLConfig.from_dict({
        "host": "pg.prod",
        "port": 5432,
        "database": "prod_db",
        "user": "admin",
        "password": "${PG_PASSWORD}",
        "pool_size": 20,
        "max_overflow": 40,
        "ssl_mode": "require",
    })
    assert cfg.host == "pg.prod"
    assert cfg.database == "prod_db"
    assert cfg.user == "admin"
    assert cfg.password == "${PG_PASSWORD}"
    assert cfg.pool_size == 20
    assert cfg.max_overflow == 40
    assert cfg.ssl_mode == "require"


def test_postgresql_config_from_dict_none():
    """from_dict(None) must return defaults (not crash)."""
    cfg = PostgreSQLConfig.from_dict(None)
    assert cfg.host == "localhost"


# ---------------------------------------------------------------------------
# Test 6: RelationalDBConfig supports PostgreSQL
# ---------------------------------------------------------------------------

def test_relational_db_config_postgresql():
    """RelationalDBConfig.from_dict() must parse postgresql backend."""
    d = {"backend": "postgresql", "postgresql": {
        "host": "pg.local", "port": 5432, "database": "mydb",
        "user": "app", "password": "pw",
    }}
    cfg = RelationalDBConfig.from_dict(d)
    assert cfg.backend == "postgresql"
    assert isinstance(cfg.postgresql, PostgreSQLConfig)
    assert cfg.postgresql.host == "pg.local"
    assert cfg.postgresql.database == "mydb"
    assert cfg.postgresql.user == "app"


# ---------------------------------------------------------------------------
# Test 7: YAML parse with PostgreSQL backend
# ---------------------------------------------------------------------------

def test_load_config_with_postgresql():
    """load_config() must parse a deploy.yaml using PostgreSQL relational DB."""
    import tempfile
    raw = {
        "deployment_mode": "saas",
        "storage": {
            "vector_store": {"backend": "qdrant", "qdrant": {}},
            "document_index": {"backend": "meilisearch"},
            "relational_db": {
                "backend": "postgresql",
                "postgresql": {"host": "pg.prod", "user": "app", "password": "pw"},
            },
            "file_store": {"backend": "local_fs"},
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(raw, f)
        path = f.name

    cfg = load_config(path)
    assert cfg.relational_db.backend == "postgresql"
    assert isinstance(cfg.relational_db.postgresql, PostgreSQLConfig)
    assert cfg.relational_db.postgresql.host == "pg.prod"
